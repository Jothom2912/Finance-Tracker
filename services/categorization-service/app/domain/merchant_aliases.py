"""Inactive TAX-04 canonical merchant and alias manifest."""

from __future__ import annotations

from app.domain.seed_contracts import MatchField, MerchantAlias, MerchantSeed
from app.domain.taxonomy_definitions import SEED_VERSION


def _merchant(key: str, display: str, *aliases: str) -> MerchantSeed:
    return MerchantSeed(
        merchant_key=key,
        display_name=display,
        aliases=tuple(MerchantAlias(alias, MatchField.MERCHANT, country="DK") for alias in aliases),
        provenance="legacy-seed-reviewed:TAX-05",
        seed_version=SEED_VERSION,
    )


MERCHANTS: tuple[MerchantSeed, ...] = (
    _merchant("netto", "Netto", "netto"),
    _merchant("lidl", "Lidl", "lidl"),
    _merchant("foetex", "Føtex", "foetex"),
    _merchant("rema_1000", "Rema 1000", "rema1000"),
    _merchant("coop_365", "Coop 365", "coop365"),
    _merchant("kvickly", "Kvickly", "coop kvickly"),
    _merchant("superbrugsen", "SuperBrugsen", "superbrugsen"),
    _merchant("irma", "Irma", "irma"),
    _merchant("meny", "Meny", "meny"),
    _merchant("wolt", "Wolt", "wolt"),
    _merchant("just_eat", "Just Eat", "just eat.dk"),
    _merchant("mcdonalds", "McDonald's", "mcdonalds", "mcdonald's"),
    _merchant("burger_king", "Burger King", "burger king"),
    _merchant("sunset_boulevard", "Sunset Boulevard", "sunset blvd"),
    _merchant("seven_eleven", "7-Eleven", "7-eleven", "dsb 7-eleven"),
    _merchant("telenor", "Telenor", "telenor", "telenor a/s", "bs betaling telenor a/s"),
    _merchant("dsb", "DSB", "dsb", "dsb.dk/", "dsb service & retail", "dsb ungdomskort"),
    _merchant("rejsekort", "Rejsekort", "rejsekort"),
    _merchant("metro", "Metro", "metro service a/s"),
    _merchant("flixbus", "FlixBus", "flixbus.com"),
    _merchant("rejsebillet", "Rejsebillet", "rejsebillet.dk"),
    _merchant("q8", "Q8", "q8 service"),
    _merchant("circle_k", "Circle K", "circle k"),
    _merchant("shell", "Shell", "shell"),
    _merchant("spotify", "Spotify", "spotify"),
    _merchant("netflix", "Netflix", "netflix"),
    _merchant("sportmaster", "Sportmaster", "sportmaster"),
    _merchant("intersport", "Intersport", "intersport"),
    _merchant("normal", "Normal", "normal"),
    _merchant("matas", "Matas", "matas"),
    _merchant("ikea", "IKEA", "ikea"),
    _merchant("silvan", "Silvan", "silvan"),
    _merchant("bauhaus", "Bauhaus", "bauhaus"),
    _merchant("jem_og_fix", "Jem & Fix", "jem og fix"),
    _merchant("elgiganten", "Elgiganten", "elgiganten"),
    _merchant("power", "Power", "power"),
)

ALIAS_TO_MERCHANT = {
    alias.normalized_value: merchant.merchant_key for merchant in MERCHANTS for alias in merchant.aliases
}
