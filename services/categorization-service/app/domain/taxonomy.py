"""Default taxonomy for dansk privatoekonomi.

Two data structures:
  DEFAULT_TAXONOMY       - Category -> SubCategory hierarchy (seeded at startup)
  SEED_MERCHANT_MAPPINGS - keyword -> subcategory+display (seeds categorization_rules)

Normalisation convention for keywords:
    Danish characters are transliterated as oe->oe, ae->ae, aa->aa.
    The rule engine applies the same transliteration to transaction
    descriptions at match time.
"""

from app.domain.value_objects import CategoryType

DEFAULT_TAXONOMY: dict[str, dict] = {
    "Mad & drikke": {
        "type": CategoryType.EXPENSE,
        "order": 1,
        "subcategories": [
            "Dagligvarer",
            "Restaurant",
            "Takeaway",
            "Kaffebar",
            "Kiosk",
        ],
    },
    "Bolig": {
        "type": CategoryType.EXPENSE,
        "order": 2,
        "subcategories": [
            "Husleje",
            "El/vand/varme",
            "Forsikring",
            "Mobil/internet",
            "Vedligeholdelse",
        ],
    },
    "Transport": {
        "type": CategoryType.EXPENSE,
        "order": 3,
        "subcategories": [
            "Offentlig transport",
            "Braendstof",
            "Bil/vedligeholdelse",
            "Parkering",
            "Cykel",
        ],
    },
    "Underholdning & fritid": {
        "type": CategoryType.EXPENSE,
        "order": 4,
        "subcategories": [
            "Abonnementer",
            "Barer/natteliv",
            "Oplevelser",
            "Fitness/sport",
            "Sportstoj/udstyr",
        ],
    },
    "Personlig": {
        "type": CategoryType.EXPENSE,
        "order": 5,
        "subcategories": [
            "Pleje/hygiejne",
            "Haarpleje",
            "Medicin",
            "Toj",
        ],
    },
    "Hjem": {
        "type": CategoryType.EXPENSE,
        "order": 6,
        "subcategories": [
            "Mobler/DIY",
            "Elektronik",
        ],
    },
    "Finansielt": {
        "type": CategoryType.EXPENSE,
        "order": 7,
        "subcategories": [
            "Gebyrer",
            "Renteudgifter",
            "Investering",
        ],
    },
    "Diverse": {
        "type": CategoryType.EXPENSE,
        "order": 8,
        "subcategories": [
            "Kontant/ATM",
            "Vaskeri",
            "Anden",
        ],
    },
    "Indkomst": {
        "type": CategoryType.INCOME,
        "order": 10,
        "subcategories": [
            "Lon",
            "Offentlig stotte",
            "Overforsel fra andre",
            "Renteindtaegter",
            "Opsparing (ind)",
        ],
    },
    "Overfoersler": {
        "type": CategoryType.TRANSFER,
        "order": 20,
        "subcategories": [
            "MobilePay ind",
            "MobilePay ud",
            "Kontooverforsel",
            "Opsparing (ud)",
        ],
    },
}


SEED_MERCHANT_MAPPINGS: dict[str, dict[str, str]] = {
    # ── Mad & drikke -> Dagligvarer
    "netto": {"subcategory": "Dagligvarer", "display": "Netto"},
    "lidl": {"subcategory": "Dagligvarer", "display": "Lidl"},
    "foetex": {"subcategory": "Dagligvarer", "display": "Foetex"},
    "rema1000": {"subcategory": "Dagligvarer", "display": "Rema 1000"},
    "coop365": {"subcategory": "Dagligvarer", "display": "Coop 365"},
    "coop kvickly": {"subcategory": "Dagligvarer", "display": "Kvickly"},
    "saffi koebmand": {"subcategory": "Dagligvarer", "display": "Saffi Koebmand"},
    "stopn shop": {"subcategory": "Dagligvarer", "display": "Stop'n'Shop"},
    "superbrugsen": {"subcategory": "Dagligvarer", "display": "SuperBrugsen"},
    "irma": {"subcategory": "Dagligvarer", "display": "Irma"},
    "meny": {"subcategory": "Dagligvarer", "display": "Meny"},
    "asian market": {"subcategory": "Dagligvarer", "display": "Asian Market"},
    "slagter": {"subcategory": "Dagligvarer", "display": "Slagter"},
    "bager": {"subcategory": "Dagligvarer", "display": "Bager"},
    # ── Mad & drikke -> Restaurant
    "restaurant": {"subcategory": "Restaurant", "display": "Restaurant"},
    "kosem restaurant": {"subcategory": "Restaurant", "display": "Kosem Restaurant"},
    "den franske cafe": {"subcategory": "Restaurant", "display": "Den Franske Cafe"},
    "divan aps": {"subcategory": "Restaurant", "display": "Divan"},
    "cafe grotten": {"subcategory": "Restaurant", "display": "Cafe Grotten"},
    # ── Mad & drikke -> Takeaway
    "wolt": {"subcategory": "Takeaway", "display": "Wolt"},
    "just eat.dk": {"subcategory": "Takeaway", "display": "Just Eat"},
    "mcd": {"subcategory": "Takeaway", "display": "McDonald's"},
    "burger king": {"subcategory": "Takeaway", "display": "Burger King"},
    "sunset blvd": {"subcategory": "Takeaway", "display": "Sunset Boulevard"},
    "kebabro": {"subcategory": "Takeaway", "display": "Kebabro"},
    "istanbul kabab": {"subcategory": "Takeaway", "display": "Istanbul Kebab"},
    "doener corner": {"subcategory": "Takeaway", "display": "Doener Corner"},
    "pizzaria": {"subcategory": "Takeaway", "display": "Pizzaria"},
    "sushi": {"subcategory": "Takeaway", "display": "Sushi"},
    # ── Mad & drikke -> Kaffebar
    "cafe": {"subcategory": "Kaffebar", "display": "Cafe"},
    "royal bagel": {"subcategory": "Kaffebar", "display": "Royal Bagel"},
    "cafe lille peter": {"subcategory": "Kaffebar", "display": "Cafe Lille Peter"},
    # ── Mad & drikke -> Kiosk
    "7-eleven": {"subcategory": "Kiosk", "display": "7-Eleven"},
    "dsb 7-eleven": {"subcategory": "Kiosk", "display": "DSB 7-Eleven"},
    "international kiosk": {"subcategory": "Kiosk", "display": "International Kiosk"},
    "scandinavia kiosk": {"subcategory": "Kiosk", "display": "Scandinavia Kiosk"},
    "luxor kiosk": {"subcategory": "Kiosk", "display": "Luxor Kiosk"},
    "candy shop": {"subcategory": "Kiosk", "display": "Candy Shop"},
    "kiioskh": {"subcategory": "Kiosk", "display": "Kiosk"},
    # ── Bolig
    "cph village": {"subcategory": "Husleje", "display": "CPH Village"},
    "energi": {"subcategory": "El/vand/varme", "display": "Energi"},
    "forsikring": {"subcategory": "Forsikring", "display": "Forsikring"},
    "telenor": {"subcategory": "Mobil/internet", "display": "Telenor"},
    "telenor a/s": {"subcategory": "Mobil/internet", "display": "Telenor"},
    "bs betaling telenor a/s": {"subcategory": "Mobil/internet", "display": "Telenor"},
    # ── Transport
    "dsb": {"subcategory": "Offentlig transport", "display": "DSB"},
    "dsb.dk/": {"subcategory": "Offentlig transport", "display": "DSB"},
    "dsb service & retail": {"subcategory": "Offentlig transport", "display": "DSB"},
    "dsb ungdomskort": {"subcategory": "Offentlig transport", "display": "DSB Ungdomskort"},
    "rejsekort": {"subcategory": "Offentlig transport", "display": "Rejsekort"},
    "metro service a/s": {"subcategory": "Offentlig transport", "display": "Metro"},
    "flixbus.com": {"subcategory": "Offentlig transport", "display": "FlixBus"},
    "rejsebillet.dk": {"subcategory": "Offentlig transport", "display": "Rejsebillet"},
    "q8 service": {"subcategory": "Braendstof", "display": "Q8"},
    "circle k": {"subcategory": "Braendstof", "display": "Circle K"},
    "shell": {"subcategory": "Braendstof", "display": "Shell"},
    "benz": {"subcategory": "Braendstof", "display": "Benzin"},
    "tankstation": {"subcategory": "Braendstof", "display": "Tankstation"},
    "bilvask": {"subcategory": "Bil/vedligeholdelse", "display": "Bilvask"},
    "vaerksted": {"subcategory": "Bil/vedligeholdelse", "display": "Vaerksted"},
    "mekaniker": {"subcategory": "Bil/vedligeholdelse", "display": "Mekaniker"},
    "bycyklen": {"subcategory": "Cykel", "display": "Bycyklen"},
    # ── Underholdning & fritid
    "spotify": {"subcategory": "Abonnementer", "display": "Spotify"},
    "netflix": {"subcategory": "Abonnementer", "display": "Netflix"},
    "abonnement": {"subcategory": "Abonnementer", "display": "Abonnement"},
    "irish pub": {"subcategory": "Barer/natteliv", "display": "Irish Pub"},
    "raevens bar": {"subcategory": "Barer/natteliv", "display": "Raevens Bar"},
    "10er bar": {"subcategory": "Barer/natteliv", "display": "10'er Bar"},
    "escobar": {"subcategory": "Barer/natteliv", "display": "Escobar"},
    "bodega": {"subcategory": "Barer/natteliv", "display": "Bodega"},
    "bar": {"subcategory": "Barer/natteliv", "display": "Bar"},
    "torinomilano drinks": {"subcategory": "Barer/natteliv", "display": "TorinoMilano Drinks"},
    "biograf": {"subcategory": "Oplevelser", "display": "Biograf"},
    "parken": {"subcategory": "Oplevelser", "display": "Parken"},
    "teater": {"subcategory": "Oplevelser", "display": "Teater"},
    "museum": {"subcategory": "Oplevelser", "display": "Museum"},
    "zoo": {"subcategory": "Oplevelser", "display": "Zoo"},
    "aquarium": {"subcategory": "Oplevelser", "display": "Aquarium"},
    "forlystelsespark": {"subcategory": "Oplevelser", "display": "Forlystelsespark"},
    "gaming": {"subcategory": "Oplevelser", "display": "Gaming"},
    "fitness dk": {"subcategory": "Fitness/sport", "display": "Fitness DK"},
    "fitness": {"subcategory": "Fitness/sport", "display": "Fitness"},
    "bison boulders aps": {"subcategory": "Fitness/sport", "display": "Bison Boulders"},
    "sportmaster": {"subcategory": "Sportstoj/udstyr", "display": "Sportmaster"},
    "intersport": {"subcategory": "Sportstoj/udstyr", "display": "Intersport"},
    "runningshop": {"subcategory": "Sportstoj/udstyr", "display": "Running Shop"},
    # ── Personlig
    "normal": {"subcategory": "Pleje/hygiejne", "display": "Normal"},
    "matas": {"subcategory": "Pleje/hygiejne", "display": "Matas"},
    "klinik": {"subcategory": "Pleje/hygiejne", "display": "Klinik"},
    "frisoer": {"subcategory": "Haarpleje", "display": "Frisoer"},
    "hair by regina dreyf": {"subcategory": "Haarpleje", "display": "Hair by Regina Dreyf"},
    "apotek": {"subcategory": "Medicin", "display": "Apotek"},
    "hamlets apotek": {"subcategory": "Medicin", "display": "Hamlets Apotek"},
    "soeborg apotek": {"subcategory": "Medicin", "display": "Soeborg Apotek"},
    "haderslev hjorte apo": {"subcategory": "Medicin", "display": "Haderslev Hjorteapotek"},
    # ── Hjem
    "ikea": {"subcategory": "Mobler/DIY", "display": "IKEA"},
    "silvan": {"subcategory": "Mobler/DIY", "display": "Silvan"},
    "bauhaus": {"subcategory": "Mobler/DIY", "display": "Bauhaus"},
    "jem og fix": {"subcategory": "Mobler/DIY", "display": "Jem & Fix"},
    "elgiganten": {"subcategory": "Elektronik", "display": "Elgiganten"},
    "power": {"subcategory": "Elektronik", "display": "Power"},
    # ── Finansielt
    "gebyr": {"subcategory": "Gebyrer", "display": "Gebyr"},
    "investering": {"subcategory": "Investering", "display": "Investering"},
    "aktier": {"subcategory": "Investering", "display": "Aktier"},
    # ── Diverse
    "pengeautomat": {"subcategory": "Kontant/ATM", "display": "Pengeautomat"},
    "nokas atm": {"subcategory": "Kontant/ATM", "display": "Nokas ATM"},
    "atm": {"subcategory": "Kontant/ATM", "display": "ATM"},
    "airwallet - laundry": {"subcategory": "Vaskeri", "display": "Airwallet"},
    "vaskeri": {"subcategory": "Vaskeri", "display": "Vaskeri"},
    "koebenhavns kommune": {"subcategory": "Anden", "display": "Koebenhavns Kommune"},
    "trust": {"subcategory": "Anden", "display": "Trust"},
    "diverse": {"subcategory": "Anden", "display": "Diverse"},
    "ukendt": {"subcategory": "Anden", "display": "Ukendt"},
    "div. overfoersel": {"subcategory": "Anden", "display": "Div. Overfoersel"},
    # ── Indkomst
    "loenoverfoersel": {"subcategory": "Lon", "display": "Lonoverfoersel"},
    "su": {"subcategory": "Offentlig stotte", "display": "SU"},
    "boligstoette": {"subcategory": "Offentlig stotte", "display": "Boligstotte"},
    "fk-feriepenge": {"subcategory": "Offentlig stotte", "display": "Feriepenge"},
    "betaling fra kk": {"subcategory": "Overforsel fra andre", "display": "Betaling fra KK"},
    "tage kristensen": {"subcategory": "Overforsel fra andre", "display": "Tage Kristensen"},
    "renter": {"subcategory": "Renteindtaegter", "display": "Renter"},
    "rente": {"subcategory": "Renteindtaegter", "display": "Rente"},
    "fra opsparing": {"subcategory": "Opsparing (ind)", "display": "Fra Opsparing"},
    # ── Overfoersler
    "mobilepay ind": {"subcategory": "MobilePay ind", "display": "MobilePay Ind"},
    "vipps mobilepay": {"subcategory": "MobilePay ind", "display": "Vipps MobilePay"},
    "overfoersel mobilepay": {"subcategory": "MobilePay ind", "display": "MobilePay"},
    "mobilepay ud": {"subcategory": "MobilePay ud", "display": "MobilePay Ud"},
    "mobilepay": {"subcategory": "MobilePay ud", "display": "MobilePay"},
    "mobilepay dot app": {"subcategory": "MobilePay ud", "display": "MobilePay"},
    "opsparing": {"subcategory": "Opsparing (ud)", "display": "Opsparing"},
}
