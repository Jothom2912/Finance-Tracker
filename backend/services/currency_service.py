import requests

API_URL = "https://api.currencyfreaks.com/v2.0/rates/latest"
API_KEY = "YOUR_APIKEY"

def get_rate(base: str, symbol: str) -> float:
    response = requests.get(
        API_URL,
        params={
            "apikey": API_KEY,
            "base": base,
            "symbols": symbol
        },
        timeout=5
    )
    response.raise_for_status()
    data = response.json()
    return float(data["rates"][symbol])

def convert_currency(from_currency: str, to_currency: str, amount: float) -> float:
    response = requests.get(
        API_URL,
        params={
            "apikey": API_KEY,
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
        },
        timeout=5
    )
    response.raise_for_status()
    data = response.json()
    return float(data["result"])

API_URLConversion='https://api.currencyfreaks.com/v2.0/convert/latest?apikey=YOUR_APIKEY&from=USD&to=PKR&amount=500'