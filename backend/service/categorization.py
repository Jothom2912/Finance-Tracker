# app/services/categorization.py

# category_rules ordbogen indeholder keywords og deres tilhørende kategorinavne.
# Disse keywords bruges til at matche mod transaktionsbeskrivelser.
# Rækkefølgen af reglerne i ordbogen er ikke kritisk, da funktionen assign_category_automatically
# har en specifik prioriteret logik.
category_rules = {
    # Madvarer/Dagligvarer - Generelle supermarkeder og kiosker
    "netto": "Madvarer/Dagligvarer",
    "lidl": "Madvarer/Dagligvarer",
    "foetex": "Madvarer/Dagligvarer",
    "rema1000": "Madvarer/Dagligvarer",
    "coop365": "Madvarer/Dagligvarer",
    "coop kvickly": "Madvarer/Dagligvarer",
    "saffi kobmand": "Madvarer/Dagligvarer",
    "stopn shop": "Madvarer/Dagligvarer",
    "international kiosk": "Madvarer/Dagligvarer",
    "scandinavia kiosk": "Madvarer/Dagligvarer",
    "luxor kiosk": "Madvarer/Dagligvarer",
    "candy shop": "Madvarer/Dagligvarer",
    "kiioskh": "Madvarer/Dagligvarer",
    "superbrugsen": "Madvarer/Dagligvarer",
    "irma": "Madvarer/Dagligvarer",
    "meny": "Madvarer/Dagligvarer",
    "asian market": "Madvarer/Dagligvarer",
    "slagter": "Madvarer/Dagligvarer", # Generisk for slagtere
    "bager": "Madvarer/Dagligvarer", # Generisk for bagere

    # Restauranter/Takeaway/Café - Specifikke steder og delivery services
    "istanbul kabab": "Restauranter/Takeaway",
    "kosem restaurant": "Restauranter/Takeaway",
    "cafe grotten": "Restauranter/Takeaway",
    "royal bagel": "Restauranter/Takeaway",
    "torinomilano drinks": "Restauranter/Takeaway",
    "wolt": "Restauranter/Takeaway",
    "just eat.dk": "Restauranter/Takeaway",
    "cafe lille peter": "Restauranter/Takeaway",
    "kebabro": "Restauranter/Takeaway",
    "divan aps": "Restauranter/Takeaway",
    "den franske cafe": "Restauranter/Takeaway",
    "doener corner": "Restauranter/Takeaway",
    "mcd": "Restauranter/Takeaway",
    "burger king": "Restauranter/Takeaway",
    "pizzaria": "Restauranter/Takeaway",
    "sushi": "Restauranter/Takeaway",
    "restaurant": "Restauranter/Takeaway",
    "cafe": "Restauranter/Takeaway", # Generisk for cafeer

    # Transport - Offentlig transport og lignende
    "dsb.dk/": "Transport",
    "dsb service & retail": "Transport",
    "dsb ungdomskort": "Transport",
    "flixbus.com": "Transport",
    "metro service a/s": "Transport",
    "rejsekort": "Transport",
    "bycyklen": "Transport", # Hvis du bruger bycykler

    # Regninger/Faste udgifter - Specifikke udbydere
    "cph village": "Husleje/Bolig",
    "telenor a/s": "Mobil/Internet",
    "bs betaling telenor a/s": "Mobil/Internet",
    "energi": "El/Vand/Varme",
    "forsikring": "Forsikringer",
    "abonnement": "Abonnementer",
    "spotify": "Abonnementer", # Eksempel på specifikt abonnement
    "netflix": "Abonnementer", # Eksempel på specifikt abonnement
    "fitness dk": "Abonnementer", # Fitness abonnement kan også være her, eller under Fitness/Sport

    # Indkomst - Specifikke indkomstkilder
    # Disse vil blive matchet afhængigt af beløbet i funktionen
    "su": "Offentlig Støtte",
    "boligstøtte": "Offentlig Støtte",
    "fk-feriepenge": "Offentlig Støtte",
    "betaling fra kk": "Betalinger fra andre",
    "tage kristensen": "Betalinger fra andre",

    # Opsparing/Investering - Flytning mellem egne konti
    # Disse vil blive matchet afhængigt af beløbet i funktionen
    "fra opsparing": "Opsparing (Ind)",
    "opsparing": "Opsparing (Ud)",
    "investering": "Investering",
    "aktier": "Investering",

    # Kontanter - Hævninger
    "pengeautomat": "Hæveautomat",
    "nokas atm": "Hæveautomat",
    "atm": "Hæveautomat", # Mere generisk

    # Personlig pleje - Butikker og services
    "hair by regina dreyf": "Hårpleje/Personlig Pleje",
    "normal": "Personlig Pleje",
    "matas": "Personlig Pleje",
    "frisør": "Hårpleje/Personlig Pleje",
    "klinik": "Personlig Pleje", # Generisk for klinikker (f.eks. fodklinik, massage)

    # Medicinalvarer - Apoteker
    "hamlets apotek": "Medicinalvarer",
    "soeborg apotek": "Medicinalvarer",
    "haderslev hjorte apo": "Medicinalvarer",
    "apotek": "Medicinalvarer",

    # Hjem/DIY - Butikker til boligforbedring
    "silvan": "Møbler/Interiør/DIY",
    "bauhaus": "Møbler/Interiør/DIY",
    "ikea": "Møbler/Interiør/DIY",
    "jem og fix": "Møbler/Interiør/DIY",
    "elgiganten": "Elektronik/Hjem", # Tilføjet, da de også sælger husholdningsapparater
    "power": "Elektronik/Hjem",

    # Øl/Barer/Natteliv - Steder at gå ud
    "irish pub": "Øl/Barer",
    "raevens bar": "Øl/Barer",
    "10er bar": "Øl/Barer",
    "escobar": "Øl/Barer",
    "bodega": "Øl/Barer",
    "bar": "Øl/Barer", # Generisk

    # Fritid/Oplevelser - Aktiviteter og underholdning
    "bison boulders aps": "Underholdning/Fritid",
    "biograf": "Underholdning/Fritid",
    "parken": "Underholdning/Fritid", # For f.eks. koncert- eller eventbilletter
    "teater": "Underholdning/Fritid",
    "museum": "Underholdning/Fritid",
    "zoo": "Underholdning/Fritid",
    "aquarium": "Underholdning/Fritid",
    "forlystelsespark": "Underholdning/Fritid",
    "gaming": "Underholdning/Fritid", # For spil eller spilbutikker

    # Sport/Fitness
    "fitness": "Fitness/Sport",
    "sportmaster": "Sportstøj/Udstyr",
    "intersport": "Sportstøj/Udstyr",
    "runningshop": "Sportstøj/Udstyr",

    # Vaskeri
    "airwallet - laundry": "Vaskeri",
    "vaskeri": "Vaskeri",

    # Bil/Benzin - Tankstationer og bilrelaterede udgifter
    "q8 service": "Bil/Benzin",
    "circle k": "Bil/Benzin",
    "shell": "Bil/Benzin",
    "benz": "Bil/Benzin",
    "tankstation": "Bil/Benzin",
    "bilvask": "Bil/Benzin",
    "vaerksted": "Bil/Vedligeholdelse", # Generisk for bilværksted
    "mekaniker": "Bil/Vedligeholdelse",

    # Finansielle udgifter/indtægter
    "gebyr": "Gebyrer",
    "renter": "Renter", # Vil primært fange positive renter i den nye funktion

    # Ukategoriseret/Diverse - Standard fallback
    # "anden": "Anden", # Denne kategori tildeles, hvis intet andet matcher i funktionen
    "koebenhavns kommune": "Anden", # Kan være mange ting, uklar ud fra beskrivelsen
    "trust": "Anden", # Uklar butik/service
    "diverse": "Anden",
    "ukendt": "Anden",
    "div. overførsel": "Anden", # Hvis der er standardtekster for diverse overførsler

    "mobilepay ind": "MobilePay (Ind)",  # Til indgående MobilePay-transaktioner
    "mobilepay ud": "MobilePay (Ud)",    # Til udgående MobilePay-transaktioner
    "vipps mobilepay": "MobilePay (Ind)",
}


def assign_category_automatically(transaction_description: str, amount: float, category_name_to_id: dict):
    """
    Tildeler en kategori baseret på transaktionsbeskrivelsen og beløbet.
    Funktionen prioriterer kategorisering i en bestemt rækkefølge:
    1. MobilePay indgående og andre specifikke indkomstkilder (baseret på positivt beløb).
    2. MobilePay udgående (baseret på negativt beløb).
    3. Specifikke gebyrer og renter.
    4. Generelle matches fra 'category_rules' ordbogen.
    5. Opsparing ud (baseret på negativt beløb).
    6. Hæveautomater.
    7. Fallback til "Anden" kategori.

    Forventer category_name_to_id som en dict af formatet {"kategorinavn": kategori_id}.
    """
    description_lower = transaction_description.lower().strip()
    search_string = description_lower # Bruges til at søge i beskrivelsen

    # --- Trin 1: Håndter MobilePay og Indkomst (med prioritering af beløb) ---

    # Specifikke MobilePay-indtægter og andre indkomstkilder (positive beløb)
    if amount > 0:
        if "su" in search_string and category_name_to_id.get("offentlig støtte"):
            return category_name_to_id["offentlig støtte"]
        if "boligstøtte" in search_string and category_name_to_id.get("offentlig støtte"):
            return category_name_to_id["offentlig støtte"]
        if "fk-feriepenge" in search_string and category_name_to_id.get("offentlig støtte"):
            return category_name_to_id["offentlig støtte"]
        if "betaling fra kk" in search_string and category_name_to_id.get("betalinger fra andre"):
            return category_name_to_id["betalinger fra andre"]
        if "tage kristensen" in search_string and category_name_to_id.get("betalinger fra andre"):
            return category_name_to_id["betalinger fra andre"]
        if "fra opsparing" in search_string and category_name_to_id.get("opsparing (ind)"):
            return category_name_to_id["opsparing (ind)"]
        if "renter" in search_string and category_name_to_id.get("renter"): # Positiv rente
            return category_name_to_id["renter"]
        # Meget specifikke MobilePay-indtægter
        if "overførsel mobilepay" in search_string and category_name_to_id.get("mobilepay ind"):
            return category_name_to_id["mobilepay ind"]
        # "Vipps MobilePay" kan være både ind og ud. Hvis positiv, så ind.
        if "vipps mobilepay" in search_string and category_name_to_id.get("mobilepay ind"):
            return category_name_to_id["mobilepay ind"]

    # Generel MobilePay ud (negative beløb) - tjek efter de positive mobilepay-regler
    if amount < 0:
        if "mobilepay" in search_string and category_name_to_id.get("mobilepay ud"):
            return category_name_to_id["mobilepay ud"]
        # "Vipps MobilePay" kan være både ind og ud. Hvis negativ, så ud.
        if "vipps mobilepay" in search_string and category_name_to_id.get("mobilepay ud"):
            return category_name_to_id["mobilepay ud"]
        if "mobilepay dot app" in search_string and category_name_to_id.get("mobilepay ud"):
            return category_name_to_id["mobilepay ud"]

    # --- Trin 2: Specifikke finansielle udgifter (kan være positive/negative) ---
    if "gebyr" in search_string and category_name_to_id.get("gebyrer"):
        return category_name_to_id["gebyrer"]
    # Negative renter (udgifter)
    if "renter" in search_string and amount < 0 and category_name_to_id.get("renter"):
        return category_name_to_id["renter"]

    # --- Trin 3: Gennemgå de almindelige category_rules ---
    # Keywords i ordbogen matcher mod beskrivelsen.
    for keyword, category_name in category_rules.items():
        if keyword in search_string:
            # Returner kategoriens ID, hvis et match findes.
            # Fallback til 'anden' hvis kategorinavnet fra reglen ikke findes i db_kategorierne.
            return category_name_to_id.get(category_name.lower(), category_name_to_id.get("anden"))
    
    # --- Trin 4: Opsparing (Ud) - skal være negativt beløb ---
    # Placeret her for at undgå at fange "fra opsparing" (som er ind)
    if "opsparing" in search_string and amount < 0 and category_name_to_id.get("opsparing (ud)"):
        return category_name_to_id["opsparing (ud)"]

    # --- Trin 5: Hæveautomater ---
    if "pengeautomat" in search_string and category_name_to_id.get("hæveautomat"):
        return category_name_to_id["hæveautomat"]
    if "nokas atm" in search_string and category_name_to_id.get("hæveautomat"):
        return category_name_to_id["hæveautomat"]
    if "atm" in search_string and category_name_to_id.get("hæveautomat"):
        return category_name_to_id["hæveautomat"]

    # --- Trin 6: Hvis intet matcher, tildel "Anden" ---
    return category_name_to_id.get("anden")