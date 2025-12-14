from unittest.mock import patch
from backend.services.currency_service import get_rate, convert_currency


def test_get_latest_rate_mocked():
    mock_response = {
        "base": "EUR",
        "rates": {
            "USD": "1.08"
        }
    }

    with patch("backend.services.currency_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None

        rate = get_rate("EUR", "USD")

        assert rate == 1.08
        
def test_convert_currency_mocked():
    mock_response = {
        "query": {
            "from": "USD",
            "to": "EUR",
            "amount": 100
        },
        "result": "92.50"
    }

    with patch("backend.services.currency_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None

        result = convert_currency("USD", "EUR", 100)

        assert result == 92.5