"""
Unit tests for RuleEngine — Tier 1 keyword matching.

Tests:
  - Longest-match-first behavior
  - Sign-dependent keyword overrides (renter, mobilepay, opsparing)
  - Case insensitivity
  - No match returns None
  - Missing subcategory in lookup is skipped
"""

import pytest
from backend.category.adapters.outbound.rule_engine import (
    RuleEngine,
    _normalize_for_matching,
)
from backend.category.domain.value_objects import (
    CategorizationTier,
    Confidence,
)

# Subcategory lookup: name -> (subcategory_id, category_id)
LOOKUP = {
    "Dagligvarer": (10, 1),
    "Restaurant": (11, 1),
    "Kaffebar": (12, 1),
    "Kiosk": (13, 1),
    "Offentlig transport": (30, 3),
    "Renteindtaegter": (91, 9),
    "Renteudgifter": (71, 7),
    "MobilePay ind": (101, 10),
    "MobilePay ud": (102, 10),
    "Opsparing (ind)": (93, 9),
    "Opsparing (ud)": (104, 10),
    "Fitness/sport": (41, 4),
    "Barer/natteliv": (42, 4),
    "Abonnementer": (43, 4),
    "Gebyrer": (72, 7),
    "Anden": (80, 8),
    "Lon": (110, 11),
    "Offentlig stotte": (111, 11),
}

# Keyword mappings matching a subset of SEED_MERCHANT_MAPPINGS
KEYWORDS: list[tuple[str, str]] = [
    ("netto", "Dagligvarer"),
    ("restaurant", "Restaurant"),
    ("kosem restaurant", "Restaurant"),
    ("cafe", "Kaffebar"),
    ("cafe grotten", "Restaurant"),
    ("den franske cafe", "Restaurant"),
    ("7-eleven", "Kiosk"),
    ("dsb 7-eleven", "Kiosk"),
    ("dsb", "Offentlig transport"),
    ("dsb service & retail", "Offentlig transport"),
    ("dsb ungdomskort", "Offentlig transport"),
    ("renter", "Renteindtaegter"),
    ("rente", "Renteindtaegter"),
    ("mobilepay", "MobilePay ud"),
    ("mobilepay ind", "MobilePay ind"),
    ("mobilepay ud", "MobilePay ud"),
    ("opsparing", "Opsparing (ud)"),
    ("fra opsparing", "Opsparing (ind)"),
    ("fitness dk", "Fitness/sport"),
    ("fitness", "Fitness/sport"),
    ("bar", "Barer/natteliv"),
    ("escobar", "Barer/natteliv"),
    ("spotify", "Abonnementer"),
    ("gebyr", "Gebyrer"),
]


@pytest.fixture
def engine() -> RuleEngine:
    return RuleEngine(keyword_mappings=KEYWORDS, subcategory_lookup=LOOKUP)


# ──────────────────────────────────────────────
# Longest-match-first
# ──────────────────────────────────────────────


class TestLongestMatchFirst:
    def test_dsb_7eleven_matches_kiosk_not_dsb(self, engine: RuleEngine) -> None:
        """'dsb 7-eleven' (13 chars) beats 'dsb' (3 chars) and '7-eleven' (8 chars)."""
        result = engine.match("DSB 7-Eleven Koebenhavn", amount=-42.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Kiosk"][0]

    def test_dsb_alone_matches_transport(self, engine: RuleEngine) -> None:
        result = engine.match("DSB Billet app", amount=-89.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig transport"][0]

    def test_dsb_service_retail_matches_transport(self, engine: RuleEngine) -> None:
        """'dsb service & retail' (20 chars) is longer than 'dsb' (3 chars)."""
        result = engine.match("DSB SERVICE & RETAIL Noerreport", amount=-35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig transport"][0]

    def test_cafe_grotten_matches_restaurant_not_kaffebar(self, engine: RuleEngine) -> None:
        """'cafe grotten' (12 chars) beats 'cafe' (4 chars)."""
        result = engine.match("CAFE GROTTEN 2100 Koebenhavn", amount=-150.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Restaurant"][0]

    def test_bare_cafe_matches_kaffebar(self, engine: RuleEngine) -> None:
        result = engine.match("Cafe Nero", amount=-45.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Kaffebar"][0]

    def test_fitness_dk_matches_before_fitness(self, engine: RuleEngine) -> None:
        """'fitness dk' (10 chars) beats 'fitness' (7 chars)."""
        result = engine.match("FITNESS DK Vesterbro", amount=-299.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Fitness/sport"][0]

    def test_escobar_matches_before_bar(self, engine: RuleEngine) -> None:
        """'escobar' (7 chars) beats 'bar' (3 chars)."""
        result = engine.match("Escobar Vestergade", amount=-85.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Barer/natteliv"][0]

    def test_kosem_restaurant_matches_before_restaurant(self, engine: RuleEngine) -> None:
        """'kosem restaurant' (16 chars) beats 'restaurant' (10 chars)."""
        result = engine.match("Kosem Restaurant Noerrebro", amount=-125.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Restaurant"][0]


# ──────────────────────────────────────────────
# Sign-dependent overrides
# ──────────────────────────────────────────────


class TestSignOverrides:
    def test_renter_positive_maps_to_income(self, engine: RuleEngine) -> None:
        result = engine.match("Renter kreditkonto", amount=12.50)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteindtaegter"][0]
        assert result.category_id == LOOKUP["Renteindtaegter"][1]

    def test_renter_negative_maps_to_expense(self, engine: RuleEngine) -> None:
        result = engine.match("Renter kreditkonto", amount=-12.50)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteudgifter"][0]
        assert result.category_id == LOOKUP["Renteudgifter"][1]

    def test_rente_positive_maps_to_income(self, engine: RuleEngine) -> None:
        result = engine.match("Rente opgoer Q4", amount=35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteindtaegter"][0]

    def test_rente_negative_maps_to_expense(self, engine: RuleEngine) -> None:
        result = engine.match("Rente opgoer Q4", amount=-35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteudgifter"][0]

    def test_mobilepay_positive_maps_to_ind(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay betaling", amount=200.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ind"][0]

    def test_mobilepay_negative_maps_to_ud(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay betaling", amount=-200.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ud"][0]

    def test_mobilepay_ind_explicit_always_ind(self, engine: RuleEngine) -> None:
        """Explicit 'mobilepay ind' keyword is longer, matches regardless of amount sign."""
        result = engine.match("MobilePay ind fra person", amount=-50.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ind"][0]

    def test_opsparing_positive_maps_to_ind(self, engine: RuleEngine) -> None:
        result = engine.match("Opsparing automatisk", amount=500.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ind)"][0]

    def test_opsparing_negative_maps_to_ud(self, engine: RuleEngine) -> None:
        result = engine.match("Opsparing automatisk", amount=-500.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ud)"][0]

    def test_fra_opsparing_always_ind(self, engine: RuleEngine) -> None:
        """'fra opsparing' (14 chars) beats 'opsparing' (9 chars)."""
        result = engine.match("Fra opsparing konto", amount=-100.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ind)"][0]


# ──────────────────────────────────────────────
# Case insensitivity
# ──────────────────────────────────────────────


class TestCaseInsensitivity:
    def test_uppercase_description(self, engine: RuleEngine) -> None:
        result = engine.match("NETTO KOEBENHAVN S", amount=-150.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]

    def test_mixed_case_description(self, engine: RuleEngine) -> None:
        result = engine.match("Spotify Premium", amount=-99.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Abonnementer"][0]


# ──────────────────────────────────────────────
# No match / edge cases
# ──────────────────────────────────────────────


class TestNoMatch:
    def test_no_keyword_match_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("Random unknown store xyz", amount=-50.0)
        assert result is None

    def test_empty_description_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("", amount=-50.0)
        assert result is None


# ──────────────────────────────────────────────
# Result metadata
# ──────────────────────────────────────────────


class TestResultMetadata:
    def test_tier_is_rule(self, engine: RuleEngine) -> None:
        result = engine.match("Netto", amount=-50.0)

        assert result is not None
        assert result.tier == CategorizationTier.RULE

    def test_confidence_is_high(self, engine: RuleEngine) -> None:
        result = engine.match("Netto", amount=-50.0)

        assert result is not None
        assert result.confidence == Confidence.HIGH


# ──────────────────────────────────────────────
# Missing subcategory in lookup
# ──────────────────────────────────────────────


class TestMissingLookup:
    def test_unknown_subcategory_is_skipped(self) -> None:
        """If keyword maps to subcategory not in lookup, skip and try next."""
        keywords = [
            ("phantom", "NonexistentCategory"),
            ("netto", "Dagligvarer"),
        ]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("phantom netto", amount=-50.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]

    def test_all_unknown_returns_none(self) -> None:
        keywords = [("phantom", "NonexistentCategory")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("phantom transaction", amount=-50.0)
        assert result is None


# ──────────────────────────────────────────────
# Danish character normalisation (ø/æ/å → oe/ae/aa)
# ──────────────────────────────────────────────


class TestDanishCharacterNormalisation:
    """
    The rule engine transliterates ø→oe, æ→ae, å→aa on both the
    keyword catalogue and the transaction description before
    substring matching.  These tests cover the three shapes that
    surfaced in the 2026-04-22 baseline (commit 3aad8b0):

      * Positive: raw Danish description matches an ASCII keyword.
      * Negative: a description that shares a substring with the
        normalised keyword but is not the intended match.
      * Sanity: keywords that were already ASCII keep working.
    """

    # ── Indkomst -> Lon ──────────────────────────────────────
    def test_loenoverfoersel_matches_raw_danish_description(self) -> None:
        """LØNOVERFØRSEL (raw) should resolve to Lon subcategory."""
        keywords = [("loenoverfoersel", "Lon")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("LØNOVERFØRSEL 32154.00 KR", amount=32154.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Lon"][0]
        assert result.category_id == LOOKUP["Lon"][1]

    def test_single_strip_description_does_not_match_oe_keyword(self) -> None:
        """
        Convention guard: the keyword catalogue uses ø→oe (Danish
        traditional).  A description that was pre-transliterated with
        the alternative single-letter strip (ø→o) will NOT match —
        that form is outside the contract.  Real bank descriptions
        come with raw Danish characters, so this asymmetry is
        acceptable; this test exists so a future reader understands
        the convention is one-way.
        """
        keywords = [("loenoverfoersel", "Lon")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("Lonoverfoersel", amount=32154.0)

        assert result is None

    def test_loen_substring_does_not_match_loenoverfoersel(self) -> None:
        """
        Negative control: a description containing 'LØN' as a short
        substring (e.g. a company name that happens to start with it)
        must not be categorised as Lon.  Only the full compound word
        'loenoverfoersel' is a keyword — there is intentionally no
        bare 'loen' keyword because it would over-match on unrelated
        Danish text.
        """
        keywords = [("loenoverfoersel", "Lon")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("LØN-ASTRO PRODUCTS APS", amount=-499.0)

        assert result is None

    def test_london_does_not_match_removed_lon_keyword(self) -> None:
        """
        Regression guard: an earlier version of the catalogue held a
        bare 'lon' keyword that matched 'LONDON', 'KOLONIAL',
        'DANNELON' etc. as Lon/salary.  The keyword was removed when
        normalisation landed — this test fails if someone reintroduces
        it.
        """
        from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS

        assert "lon" not in SEED_MERCHANT_MAPPINGS, (
            "Bare 'lon' keyword removed because it produced false positives "
            "on descriptions like LONDON/KOLONIAL/DANNELON. Use the full "
            "compound 'loenoverfoersel' instead."
        )

    # ── Indkomst -> Offentlig stotte ─────────────────────────
    def test_boligstoette_matches_raw_danish_description(self) -> None:
        """Boligstøtte (raw) should resolve to Offentlig stotte."""
        keywords = [("boligstoette", "Offentlig stotte")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("Boligstøtte", amount=820.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig stotte"][0]

    def test_boligstoette_matches_ascii_description(self) -> None:
        keywords = [("boligstoette", "Offentlig stotte")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("BOLIGSTOETTE udbetaling", amount=820.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig stotte"][0]

    # ── Cross-keyword normalisation invariants ───────────────
    def test_foetex_keyword_matches_raw_danish_description(self) -> None:
        """Existing foetex keyword must keep matching Føtex descriptions."""
        keywords = [("foetex", "Dagligvarer")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("Føtex Noerrebro 2200", amount=-187.50)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]

    def test_ae_and_aa_characters_normalise(self) -> None:
        """Coverage for æ→ae and å→aa on the description side."""
        keywords = [("faellesbo", "Dagligvarer"), ("aarhus", "Dagligvarer")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        assert engine.match("Fællesbo Supermarked", amount=-50.0) is not None
        assert engine.match("Aarhus Købmand", amount=-50.0) is not None
        assert engine.match("Århus Købmand", amount=-50.0) is not None

    def test_catalogue_matches_saffi_koebmand_raw_description(self) -> None:
        """
        End-to-end regression: the SEED_MERCHANT_MAPPINGS catalogue
        must classify a raw "SAFFI KØBMAND" bank description as
        Dagligvarer.  Earlier the catalogue entry was "saffi kobmand"
        (single-letter strip), which was statically ASCII but silently
        unreachable after normalisation — same class of bug as
        lonoverfoersel / boligstoette before commit 86b3489.

        Uses the real catalogue rather than a local keyword list so
        the test fails if the entry is ever reverted to the wrong
        transliteration convention.
        """
        from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS

        keyword_mappings = [(kw, m["subcategory"]) for kw, m in SEED_MERCHANT_MAPPINGS.items()]
        engine = RuleEngine(keyword_mappings=keyword_mappings, subcategory_lookup=LOOKUP)

        result = engine.match("SAFFI KØBMAND 2200", amount=-187.50)

        assert result is not None, "Catalogue must match raw Danish 'SAFFI KØBMAND' description"
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]


# ──────────────────────────────────────────────
# Catalogue convention guard
# ──────────────────────────────────────────────


class TestTaxonomyConventionGuard:
    """
    Static tripwire over the full SEED_MERCHANT_MAPPINGS catalogue.

    What the guard catches
    ----------------------
    Keywords that are not yet in the form ``_normalize_for_matching``
    would produce at match time.  In practice this means:

      * raw Danish characters (ø, æ, å — any case)
      * uppercase letters anywhere in the keyword
      * leading or trailing whitespace

    Any of those make a keyword *statically unreachable*: the
    normalised description is compared as a substring to the
    normalised keyword, so an un-normalised keyword never matches.

    What the guard does NOT catch
    -----------------------------
    Keywords that are syntactically normalised but were transliterated
    with the wrong convention, e.g. ``"saffi kobmand"`` (single-letter
    strip, ø→o) instead of the project's ø→oe.  Both forms look
    identical to a static lowercase/ASCII check; only a dictionary
    would reveal that ``kobmand`` was meant as ``købmand``.

    This class of bug surfaced three times during baseline work
    (loenoverfoersel, boligstoette, saffi koebmand) and is left to
    code review plus the baseline-rerun fallback-rate signal —
    a keyword that should match but doesn't will show up as a Q3
    fallback in ``docs/categorization-baseline.md`` eventually.
    """

    def test_every_keyword_is_pre_normalised(self) -> None:
        """Each catalogue keyword must equal its own normalised form."""
        from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS

        offenders = [kw for kw in SEED_MERCHANT_MAPPINGS if kw != _normalize_for_matching(kw)]

        assert not offenders, (
            "The following keywords are not in normalised form (expected "
            "lowercase with ø→oe, æ→ae, å→aa).  They are statically "
            f"unreachable at match time: {offenders}"
        )

    def test_no_keyword_has_whitespace_boundary(self) -> None:
        """Leading/trailing whitespace would silently prevent substring match."""
        from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS

        offenders = [kw for kw in SEED_MERCHANT_MAPPINGS if kw != kw.strip()]

        assert not offenders, f"Keywords with whitespace boundary: {offenders}"

    def test_no_keyword_is_empty(self) -> None:
        """An empty keyword would substring-match every description."""
        from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS

        offenders = [kw for kw in SEED_MERCHANT_MAPPINGS if not kw]

        assert not offenders, "Empty keyword detected — would match every description."
