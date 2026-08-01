"""Approved TAX-01 target taxonomy as an inactive TAX-04 seed manifest."""

from __future__ import annotations

from app.domain.seed_contracts import TaxonomyDefinition
from app.domain.value_objects import CategoryType

SEED_VERSION = "taxonomy-2026-08-01-v1"

_PARENTS: tuple[tuple[str, str, CategoryType, str], ...] = (
    ("food_drink", "Mad & drikke", CategoryType.EXPENSE, "Food, groceries and prepared meals."),
    ("housing", "Bolig", CategoryType.EXPENSE, "Cost of occupying, supplying and maintaining a home."),
    ("transport", "Transport", CategoryType.EXPENSE, "Daily mobility and vehicle operation."),
    (
        "services_insurance",
        "Tjenester & forsikring",
        CategoryType.EXPENSE,
        "Contracted services and insurance premiums.",
    ),
    (
        "health_personal_care",
        "Sundhed & personlig pleje",
        CategoryType.EXPENSE,
        "Treatment, medicine and personal care.",
    ),
    ("shopping", "Shopping", CategoryType.EXPENSE, "Durable and discretionary physical goods."),
    (
        "leisure_experiences",
        "Fritid & oplevelser",
        CategoryType.EXPENSE,
        "Leisure, culture, nightlife, games and sport.",
    ),
    ("travel", "Rejser", CategoryType.EXPENSE, "Purchases whose purpose is a trip."),
    (
        "family_education",
        "Familie & uddannelse",
        CategoryType.EXPENSE,
        "Dependants, gifts, pets, donations and learning.",
    ),
    ("public_tax", "Offentligt & skat", CategoryType.EXPENSE, "Taxes and mandatory public-authority payments."),
    (
        "financial_costs",
        "Finansielle omkostninger",
        CategoryType.EXPENSE,
        "Fees and interest paid for financial services.",
    ),
    ("income", "Indkomst", CategoryType.INCOME, "External inflows that increase disposable income."),
    (
        "transfers_wealth",
        "Overførsler & formue",
        CategoryType.TRANSFER,
        "Asset, liability and account-placement movements.",
    ),
)

_CHILDREN: dict[str, tuple[tuple[str, str], ...]] = {
    "food_drink": (
        ("groceries", "Dagligvarer"),
        ("restaurant_cafe", "Restaurant & café"),
        ("takeaway", "Takeaway"),
        ("kiosk", "Kiosk"),
        ("food_drink_unspecified", "Mad & drikke — uspecificeret"),
    ),
    "housing": (
        ("rent", "Husleje"),
        ("home_utilities", "Energi & forsyning"),
        ("housing_association", "Ejer-/boligforening"),
        ("home_maintenance", "Vedligeholdelse & reparation"),
        ("housing_unspecified", "Bolig — uspecificeret"),
    ),
    "transport": (
        ("public_transport", "Offentlig transport"),
        ("fuel_charging", "Brændstof & opladning"),
        ("parking_tolls", "Parkering & vejafgifter"),
        ("vehicle_service", "Bilservice & reparation"),
        ("cycling_micromobility", "Cykel & mikromobilitet"),
        ("transport_unspecified", "Transport — uspecificeret"),
    ),
    "services_insurance": (
        ("mobile_internet", "Mobil & internet"),
        ("digital_services", "Digitale tjenester"),
        ("memberships", "Medlemskaber"),
        ("insurance", "Forsikring"),
        ("services_unspecified", "Tjenester — uspecificeret"),
    ),
    "health_personal_care": (
        ("pharmacy_medicine", "Apotek & medicin"),
        ("treatment", "Behandling"),
        ("hairdresser", "Frisør"),
        ("personal_care", "Personlig pleje"),
        ("health_care_unspecified", "Sundhed & pleje — uspecificeret"),
    ),
    "shopping": (
        ("clothing_footwear", "Tøj & sko"),
        ("electronics", "Elektronik"),
        ("furniture_homeware", "Møbler & boligudstyr"),
        ("hardware_diy", "Byggemarked & DIY"),
        ("shopping_unspecified", "Shopping — uspecificeret"),
    ),
    "leisure_experiences": (
        ("bar_nightlife", "Bar & natteliv"),
        ("culture_events", "Kultur & arrangementer"),
        ("sport_fitness", "Sport & fitness"),
        ("gaming_hobby", "Gaming & hobby"),
        ("leisure_unspecified", "Fritid — uspecificeret"),
    ),
    "travel": (
        ("flight_long_distance", "Fly & langdistance"),
        ("accommodation", "Overnatning"),
        ("package_travel", "Pakkerejse"),
        ("travel_unspecified", "Rejser — uspecificeret"),
    ),
    "family_education": (
        ("children_childcare", "Børn & institution"),
        ("education_materials", "Uddannelse & materialer"),
        ("gifts_donations", "Gaver & donationer"),
        ("pets", "Kæledyr"),
        ("family_education_unspecified", "Familie & uddannelse — uspecificeret"),
    ),
    "public_tax": (
        ("tax", "Skat"),
        ("fines", "Bøder"),
        ("public_fees", "Offentlige gebyrer"),
        ("public_unspecified", "Offentligt — uspecificeret"),
    ),
    "financial_costs": (
        ("bank_fees", "Bankgebyrer"),
        ("interest_expense", "Renteudgifter"),
        ("loan_fx_fees", "Låne- & valutagebyrer"),
        ("financial_costs_unspecified", "Finansielle omkostninger — uspecificeret"),
    ),
    "income": (
        ("salary", "Løn"),
        ("self_employment", "Selvstændig & freelance"),
        ("public_benefits", "Offentlig støtte"),
        ("pension_holiday_pay", "Pension & feriepenge"),
        ("capital_income", "Kapitalindkomst"),
        ("refund", "Refusion"),
        ("other_income", "Anden indkomst"),
    ),
    "transfers_wealth": (
        ("own_accounts_savings", "Egne konti & opsparing"),
        ("investment", "Investering"),
        ("loan_principal", "Låneafdrag"),
        ("credit_card_settlement", "Kreditkortbetaling"),
        ("cash_withdrawal", "Kontanthævning"),
        ("person_transfer", "Personoverførsel"),
        ("unknown_transfer", "Ukendt overførsel"),
    ),
}

_FALLBACK_KEYS = {
    "food_drink_unspecified",
    "housing_unspecified",
    "transport_unspecified",
    "services_unspecified",
    "health_care_unspecified",
    "shopping_unspecified",
    "leisure_unspecified",
    "travel_unspecified",
    "family_education_unspecified",
    "public_unspecified",
    "financial_costs_unspecified",
    "other_income",
    "unknown_transfer",
}

TAXONOMY_DEFINITIONS: tuple[TaxonomyDefinition, ...] = tuple(
    TaxonomyDefinition(key, name, category_type, description, SEED_VERSION)
    for key, name, category_type, description in _PARENTS
) + tuple(
    TaxonomyDefinition(
        key,
        name,
        next(category_type for parent_key, _, category_type, _ in _PARENTS if parent_key == parent),
        f"Approved leaf: {name}.",
        SEED_VERSION,
        parent_key=parent,
        is_fallback=key in _FALLBACK_KEYS,
    )
    for parent, children in _CHILDREN.items()
    for key, name in children
)

TAXONOMY_KEYS = frozenset(definition.semantic_key for definition in TAXONOMY_DEFINITIONS)
SUBCATEGORY_KEYS = frozenset(
    definition.semantic_key for definition in TAXONOMY_DEFINITIONS if definition.parent_key is not None
)
