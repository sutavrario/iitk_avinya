import logging
import re
import requests
from typing import Protocol

from google.cloud import translate_v2 as translate

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class TranslationService(Protocol):
    def translate_text(self, text: str, target_language: str, source_language: str | None = None) -> str:
        """Translate text to the target language."""
        ...


class GoogleTranslationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.google_cloud_api_key.get_secret_value() if self.settings.google_cloud_api_key else None
        
        if not self.api_key:
            # Fall back to Application Default Credentials (Cloud Run / GCE)
            self.client = translate.Client()
        else:
            self.client = None

    def _replace_preserve_entities(self, text: str) -> tuple[str, dict[str, str]]:
        # Regex for amounts (e.g. ₹40,022.56, $100), invoice IDs (#B-117, INV-123), and dates (2026-09-01)
        pattern = re.compile(r'([₹$€£]\s*[\d,.]+)|(#[a-zA-Z0-9-]+)|([a-zA-Z]+-\d{4}-\d{3,})|(\b\d{4}-\d{2}-\d{2}\b)|(\b\d{1,2}/\d{1,2}/\d{2,4}\b)')
        
        placeholders = {}
        counter = 0
        
        def replacer(match):
            nonlocal counter
            val = match.group(0)
            placeholder = f"__VAR{counter}__"
            placeholders[placeholder] = val
            counter += 1
            return placeholder
            
        new_text = pattern.sub(replacer, text)
        return new_text, placeholders

    def _restore_preserve_entities(self, text: str, placeholders: dict[str, str]) -> str:
        for placeholder, original in placeholders.items():
            text = text.replace(placeholder, original)
        return text

    def translate_text(self, text: str, target_language: str, source_language: str | None = None) -> str:
        if not text.strip() or target_language == source_language:
            return text
            
        try:
            logger.debug(f"Translating text to {target_language} (source={source_language})")
            
            # Extract and mask entities to preserve
            masked_text, placeholders = self._replace_preserve_entities(text)
            
            if self.api_key:
                # Use REST API directly for API keys to avoid DefaultCredentialsError
                url = f"https://translation.googleapis.com/language/translate/v2?key={self.api_key}"
                data = {
                    "q": masked_text,
                    "target": target_language,
                    "format": "text",
                }
                if source_language:
                    data["source"] = source_language
                    
                resp = requests.post(url, json=data, timeout=10.0)
                resp.raise_for_status()
                translated = str(resp.json()["data"]["translations"][0]["translatedText"])
            else:
                # Use ADC client
                if source_language:
                    result = self.client.translate(masked_text, target_language=target_language, source_language=source_language, format_="text")
                else:
                    result = self.client.translate(masked_text, target_language=target_language, format_="text")
                translated = str(result["translatedText"])
                
            return self._restore_preserve_entities(translated, placeholders)
                
        except Exception as e:
            logger.exception("Translation API failed. Falling back to original text.")
            # Graceful fallback on failure as requested
            return text

def get_translation_service() -> TranslationService:
    return GoogleTranslationService()

