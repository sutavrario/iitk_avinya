import pytest
from unittest.mock import patch, MagicMock

from app.services.translation import GoogleTranslationService
from app.core.config import Settings

@pytest.fixture
def mock_settings():
    return Settings(google_cloud_api_key="fake-key")

@pytest.fixture
def service(mock_settings):
    with patch("app.services.translation.get_settings", return_value=mock_settings):
        return GoogleTranslationService()

def test_translate_hindi_and_bengali(service):
    with patch("app.services.translation.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"translations": [{"translatedText": "Hello"}]}}
        mock_post.return_value = mock_response

        # Hindi
        assert service.translate_text("नमस्ते", "en", "hi") == "Hello"
        
        # Bengali
        mock_response.json.return_value = {"data": {"translations": [{"translatedText": "Welcome"}]}}
        assert service.translate_text("স্বাগতম", "en", "bn") == "Welcome"

def test_mixed_language_preservation(service):
    with patch("app.services.translation.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"translations": [{"translatedText": "Invoice INV-2023 is overdue."}]}}
        mock_post.return_value = mock_response

        assert service.translate_text("Invoice INV-2023 overdue है", "en", "hi") == "Invoice INV-2023 is overdue."

def test_numbers_currency_identifiers_preservation(service):
    with patch("app.services.translation.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"translations": [{"translatedText": "The amount is ₹50,000.50 on 2023-10-01."}]}}
        mock_post.return_value = mock_response

        assert service.translate_text("The amount is ₹50,000.50 on 2023-10-01.", "hi", "en") == "The amount is ₹50,000.50 on 2023-10-01."

def test_translation_failure_fallback(service):
    with patch("app.services.translation.requests.post") as mock_post:
        mock_post.side_effect = Exception("API Error")
        
        # Should gracefully fall back to original text
        assert service.translate_text("Fallback test", "hi", "en") == "Fallback test"

def test_same_language_skips_api(service):
    with patch("app.services.translation.requests.post") as mock_post:
        assert service.translate_text("Hello", "en", "en") == "Hello"
        mock_post.assert_not_called()
