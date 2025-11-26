# backend/services/categorization.py

# Denne fil kræver ingen top-level imports fra andre services eller models, 
# hvilket er godt og hjælper med at undgå cirkulære imports.

# category_rules ordbogen indeholder keywords og deres tilhørende kategorinavne.
# Brug kun lowercase navne i kategorierne, da opslaget fra DB er lowercase.
category_rules = {
    # Madvarer/Dagligvarer - Generelle supermarkeder og kiosker
    "netto": "madvarer/dagligvarer",
    "lidl": "madvarer/dagligvarer",
    "foetex": "madvarer/dagligvarer",
    "rema1000": "madvarer/dagligvarer",
    "coop365": "madvarer/dagligvarer",
    "coop kvickly": "madvarer/dagligvarer",
    "saffi kobmand": "madvarer/dagligvarer",
    "stopn shop": "madvarer/dagligvarer",
    "international kiosk": "madvarer/dagligvarer",
    "scandinavia kiosk": "madvarer/dagligvarer",
    "luxor kiosk": "madvarer/dagligvarer",
    "candy shop": "madvarer/dagligvarer",
    "kiioskh": "madvarer/dagligvarer",
    "superbrugsen": "madvarer/dagligvarer",
    "irma": "madvarer/dagligvarer",
    "meny": "madvarer/dagligvarer",
    "asian market": "madvarer/dagligvarer",
    "slagter": "madvarer/dagligvarer", 
    "bager": "madvarer/dagligvarer", 

    # Restauranter/Takeaway/Café - Specifikke steder og delivery services
    "istanbul kabab": "restauranter/takeaway",
    "kosem restaurant": "restauranter/takeaway",
    "cafe grotten": "restauranter/takeaway",
    "royal bagel": "restauranter/takeaway",
    "torinomilano drinks": "restauranter/takeaway",
    "wolt": "restauranter/takeaway",
    "just eat.dk": "restauranter/takeaway",
    "cafe lille peter": "restauranter/takeaway",
    "kebabro": "restauranter/takeaway",
    "divan aps": "restauranter/takeaway",
    "den franske cafe": "restauranter/takeaway",
    "doener corner": "restauranter/takeaway",
    "mcd": "restauranter/takeaway",
    "burger king": "restauranter/takeaway",
    "pizzaria": "restauranter/takeaway",
    "sushi": "restauranter/takeaway",
    "restaurant": "restauranter/takeaway",
    "cafe": "restauranter/takeaway", 

    # Transport
    "dsb.dk/": "transport",
    "dsb service & retail": "transport",
    "dsb ungdomskort": "transport",
    "flixbus.com": "transport",
    "metro service a/s": "transport",
    "rejsekort": "transport",
    "bycyklen": "transport", 

    # Regninger/Faste udgifter
    "cph village": "husleje/bolig",
    "telenor a/s": "mobil/internet",
    "bs betaling telenor a/s": "mobil/internet",
    "energi": "el/vand/varme",
    "forsikring": "forsikringer",
    "abonnement": "abonnementer",
    "spotify": "abonnementer", 
    "netflix": "abonnementer", 
    "fitness dk": "abonnementer", 

    # Indkomst
    "su": "offentlig støtte",
    "boligstøtte": "offentlig støtte",
    "fk-feriepenge": "offentlig støtte",
    "betaling fra kk": "betalinger fra andre",
    "tage kristensen": "betalinger fra andre",

    # Opsparing/Investering
    "fra opsparing": "opsparing (ind)",
    "opsparing": "opsparing (ud)",
    "investering": "investering",
    "aktier": "investering",

    # Kontanter
    "pengeautomat": "hæveautomat",
    "nokas atm": "hæveautomat",
    "atm": "hæveautomat", 

    # Personlig pleje
    "hair by regina dreyf": "hårpleje/personlig pleje",
    "normal": "personlig pleje",
    "matas": "personlig pleje",
    "frisør": "hårpleje/personlig pleje",
    "klinik": "personlig pleje", 

    # Medicinalvarer
    "hamlets apotek": "medicinalvarer",
    "soeborg apotek": "medicinalvarer",
    "haderslev hjorte apo": "medicinalvarer",
    "apotek": "medicinalvarer",

    # Hjem/DIY
    "silvan": "møbler/interiør/diy",
    "bauhaus": "møbler/interiør/diy",
    "ikea": "møbler/interiør/diy",
    "jem og fix": "møbler/interiør/diy",
    "elgiganten": "elektronik/hjem", 
    "power": "elektronik/hjem",

    # Øl/Barer/Natteliv
    "irish pub": "øl/barer",
    "raevens bar": "øl/barer",
    "10er bar": "øl/barer",
    "escobar": "øl/barer",
    "bodega": "øl/barer",
    "bar": "øl/barer", 

    # Fritid/Oplevelser
    "bison boulders aps": "underholdning/fritid",
    "biograf": "underholdning/fritid",
    "parken": "underholdning/fritid", 
    "teater": "underholdning/fritid",
    "museum": "underholdning/fritid",
    "zoo": "underholdning/fritid",
    "aquarium": "underholdning/fritid",
    "forlystelsespark": "underholdning/fritid",
    "gaming": "underholdning/fritid", 

    # Sport/Fitness
    "fitness": "fitness/sport",
    "sportmaster": "sportstøj/udstyr",
    "intersport": "sportstøj/udstyr",
    "runningshop": "sportstøj/udstyr",

    # Vaskeri
    "airwallet - laundry": "vaskeri",
    "vaskeri": "vaskeri",

    # Bil/Benzin
    "q8 service": "bil/benzin",
    "circle k": "bil/benzin",
    "shell": "bil/benzin",
    "benz": "bil/benzin",
    "tankstation": "bil/benzin",
    "bilvask": "bil/benzin",
    "vaerksted": "bil/vedligeholdelse", 
    "mekaniker": "bil/vedligeholdelse",

    # Finansielle udgifter/indtægter
    "gebyr": "gebyrer",
    "renter": "renter", 

    # Ukategoriseret/Diverse
    "koebenhavns kommune": "anden", 
    "trust": "anden", 
    "diverse": "anden",
    "ukendt": "anden",
    "div. overførsel": "anden", 

    "mobilepay ind": "mobilepay ind", 
    "mobilepay ud": "mobilepay ud", 
    "vipps mobilepay": "mobilepay ind",
}


def assign_category_automatically(transaction_description: str, amount: float, category_name_to_id: dict) -> int:
    """
    Tildeler en kategori baseret på transaktionsbeskrivelsen og beløbet.
    """
    # Vi antager, at category_name_to_id allerede er i lowercase (hvilket det var i din service-kode)
    description_lower = transaction_description.lower().strip()
    search_string = description_lower 
    
    # Standard fallback kategori ID
    fallback_id = category_name_to_id.get("anden")

    # Hvis "anden" ikke findes, er der en databasefejl, som transaction_service fanger.
    if fallback_id is None:
         # I praksis bør transaction_service håndtere denne fejl, som du allerede har gjort.
         # Returner None for at signalere en fejl, hvis det er nødvendigt, men din nuværende
         # transaction_service forventer et int.
         return -1 # Antager en ikke-eksisterende ID som fejlsignal, men din service kaster ValueError.

    # --- Trin 1: Håndter MobilePay og Indkomst (med prioritering af beløb) ---

    if amount > 0:
        # Tjek for specifikke indkomstkilder
        for keyword, category_name in [
            ("su", "offentlig støtte"),
            ("boligstøtte", "offentlig støtte"),
            ("fk-feriepenge", "offentlig støtte"),
            ("betaling fra kk", "betalinger fra andre"),
            ("tage kristensen", "betalinger fra andre"),
            ("fra opsparing", "opsparing (ind)"),
            ("renter", "renter"),
            ("overførsel mobilepay", "mobilepay ind"),
            ("vipps mobilepay", "mobilepay ind"),
        ]:
            if keyword in search_string:
                return category_name_to_id.get(category_name, fallback_id)

    if amount < 0:
        # Tjek for MobilePay ud (efter positivt tjek)
        for keyword, category_name in [
            ("mobilepay", "mobilepay ud"),
            ("vipps mobilepay", "mobilepay ud"),
            ("mobilepay dot app", "mobilepay ud"),
        ]:
            if keyword in search_string:
                return category_name_to_id.get(category_name, fallback_id)

    # --- Trin 2: Specifikke finansielle udgifter (kan være positive/negative) ---
    if "gebyr" in search_string:
        return category_name_to_id.get("gebyrer", fallback_id)
    
    # Negative renter (udgifter)
    if "renter" in search_string and amount < 0:
        return category_name_to_id.get("renter", fallback_id)

    # --- Trin 3: Gennemgå de almindelige category_rules ---
    for keyword, category_name in category_rules.items():
        if keyword in search_string:
            # Returner kategoriens ID, hvis et match findes, ellers fallback til "anden".
            return category_name_to_id.get(category_name, fallback_id)
    
    # --- Trin 4 & 5: Opsparing (Ud) og Hæveautomater (håndteres allerede i category_rules) ---
    # Da du har "opsparing" og "pengeautomat" i category_rules, vil disse matche i trin 3.

    # --- Trin 6: Hvis intet matcher, tildel "Anden" ---
    return fallback_id