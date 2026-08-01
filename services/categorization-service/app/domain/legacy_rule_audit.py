"""Executable TAX-05 disposition of every legacy global mapping."""

from __future__ import annotations

from app.domain.seed_contracts import AuditDisposition, LegacyRuleAudit
from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS

_RETAIN = frozenset(
    {
        "slagter",
        "bager",
        "wolt",
        "just eat.dk",
        "burger king",
        "sunset blvd",
        "sushi",
        "7-eleven",
        "telenor",
        "dsb",
        "rejsekort",
        "metro service a/s",
        "flixbus.com",
        "rejsebillet.dk",
        "q8 service",
        "circle k",
        "shell",
        "vaerksted",
        "mekaniker",
        "bycyklen",
        "spotify",
        "netflix",
        "bodega",
        "biograf",
        "teater",
        "museum",
        "zoo",
        "aquarium",
        "forlystelsespark",
        "sportmaster",
        "intersport",
        "runningshop",
        "matas",
        "frisoer",
        "apotek",
        "ikea",
        "silvan",
        "bauhaus",
        "jem og fix",
        "elgiganten",
        "pengeautomat",
        "nokas atm",
        "atm",
        "airwallet - laundry",
        "loenoverfoersel",
        "boligstoette",
        "fk-feriepenge",
    }
)

_CONSTRAIN = frozenset(
    {
        "netto",
        "lidl",
        "foetex",
        "rema1000",
        "coop365",
        "coop kvickly",
        "superbrugsen",
        "irma",
        "meny",
        "asian market",
        "candy shop",
        "dsb 7-eleven",
        "cph village",
        "telenor a/s",
        "bs betaling telenor a/s",
        "dsb.dk/",
        "dsb service & retail",
        "dsb ungdomskort",
        "bilvask",
        "irish pub",
        "parken",
        "normal",
        "power",
        "koebenhavns kommune",
        "fra opsparing",
        "mobilepay ind",
        "vipps mobilepay",
        "overfoersel mobilepay",
        "mobilepay ud",
        "mobilepay",
        "mobilepay dot app",
        "opsparing",
    }
)

_REPLACE: dict[str, str] = {
    "mcd": "merchant_mcdonalds_takeaway",
    "pizzaria": "pattern_pizzeria_takeaway",
    "kiioskh": "pattern_kiosk_food",
}

_PERSONA_ONLY = frozenset(
    {
        "saffi koebmand",
        "stopn shop",
        "kosem restaurant",
        "den franske cafe",
        "divan aps",
        "cafe grotten",
        "kebabro",
        "istanbul kabab",
        "doener corner",
        "royal bagel",
        "cafe lille peter",
        "international kiosk",
        "scandinavia kiosk",
        "luxor kiosk",
        "raevens bar",
        "10er bar",
        "escobar",
        "torinomilano drinks",
        "bison boulders aps",
        "hair by regina dreyf",
        "hamlets apotek",
        "soeborg apotek",
        "haderslev hjorte apo",
        "tage kristensen",
    }
)

_REMOVE = frozenset(
    {
        "restaurant",
        "cafe",
        "energi",
        "forsikring",
        "benz",
        "tankstation",
        "abonnement",
        "bar",
        "gaming",
        "fitness dk",
        "fitness",
        "klinik",
        "gebyr",
        "investering",
        "aktier",
        "vaskeri",
        "trust",
        "diverse",
        "ukendt",
        "div. overfoersel",
        "su",
        "betaling fra kk",
        "renter",
        "rente",
    }
)

_TARGET_BY_OLD_SUBCATEGORY = {
    "Dagligvarer": "groceries",
    "Restaurant": "restaurant_cafe",
    "Takeaway": "takeaway",
    "Kaffebar": "restaurant_cafe",
    "Kiosk": "kiosk",
    "Husleje": "rent",
    "El/vand/varme": "home_utilities",
    "Forsikring": "insurance",
    "Mobil/internet": "mobile_internet",
    "Offentlig transport": "public_transport",
    "Braendstof": "fuel_charging",
    "Bil/vedligeholdelse": "vehicle_service",
    "Cykel": "cycling_micromobility",
    "Abonnementer": "digital_services",
    "Barer/natteliv": "bar_nightlife",
    "Oplevelser": "culture_events",
    "Fitness/sport": "sport_fitness",
    "Sportstoj/udstyr": "sport_fitness",
    "Pleje/hygiejne": "personal_care",
    "Haarpleje": "hairdresser",
    "Medicin": "pharmacy_medicine",
    "Mobler/DIY": "hardware_diy",
    "Elektronik": "electronics",
    "Gebyrer": "financial_costs_unspecified",
    "Investering": "investment",
    "Kontant/ATM": "cash_withdrawal",
    "Vaskeri": "services_unspecified",
    "Anden": "unknown_transfer",
    "Lon": "salary",
    "Offentlig stotte": "public_benefits",
    "Overforsel fra andre": "person_transfer",
    "Renteindtaegter": "capital_income",
    "Opsparing (ind)": "own_accounts_savings",
    "MobilePay ind": "person_transfer",
    "MobilePay ud": "person_transfer",
    "Opsparing (ud)": "own_accounts_savings",
}

_TARGET_OVERRIDES = {
    "ikea": "furniture_homeware",
    "koebenhavns kommune": "public_unspecified",
    "normal": "shopping_unspecified",
    "power": "shopping_unspecified",
}

_RATIONALE = {
    AuditDisposition.RETAIN: "Specific merchant or purpose evidence remains useful under the target taxonomy.",
    AuditDisposition.CONSTRAIN: "Useful evidence only when field, direction or canonical identity is constrained.",
    AuditDisposition.REPLACE: "Legacy spelling or fragment is replaced by a safer normalized target rule.",
    AuditDisposition.PERSONA_ONLY: "Local or personal evidence has no documented basis as a global default.",
    AuditDisposition.REMOVE: "The fragment is too broad or ambiguous for a safe global categorization.",
}


def _disposition(keyword: str) -> AuditDisposition:
    if keyword in _RETAIN:
        return AuditDisposition.RETAIN
    if keyword in _CONSTRAIN:
        return AuditDisposition.CONSTRAIN
    if keyword in _REPLACE:
        return AuditDisposition.REPLACE
    if keyword in _PERSONA_ONLY:
        return AuditDisposition.PERSONA_ONLY
    if keyword in _REMOVE:
        return AuditDisposition.REMOVE
    raise ValueError(f"legacy keyword has no TAX-05 disposition: {keyword}")


LEGACY_RULE_AUDIT: tuple[LegacyRuleAudit, ...] = tuple(
    LegacyRuleAudit(
        legacy_keyword=keyword,
        old_target=mapping["subcategory"],
        disposition=(disposition := _disposition(keyword)),
        proposed_target_key=_TARGET_OVERRIDES.get(
            keyword,
            _TARGET_BY_OLD_SUBCATEGORY[mapping["subcategory"]],
        ),
        rationale=_RATIONALE[disposition],
        replacement_rule_key=_REPLACE.get(keyword),
    )
    for keyword, mapping in SEED_MERCHANT_MAPPINGS.items()
)
