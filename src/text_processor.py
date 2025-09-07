"""
Text Processor for Clinical Voice Interpreter
Extensible processing: pass-through, optional LLM and DeepL translation
"""

import logging
from typing import Optional

# Try to import translation libraries
try:
    import deepl
    DEEPL_AVAILABLE = True
except ImportError:
    DEEPL_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False

import json
import os


class TextProcessor:
    """Minimal text processor with safe defaults"""

    def __init__(
        self,
        enable_llm: bool = False,
        llm_endpoint: Optional[str] = None,
        enable_deepl: bool = False,
        deepl_api_key: Optional[str] = None,
        privacy_mode: bool = True,
        target_language: str = "en"
    ):
        self.logger = logging.getLogger(__name__)
        self.enable_llm = enable_llm
        self.llm_endpoint = llm_endpoint
        self.enable_deepl = enable_deepl
        self.deepl_api_key = deepl_api_key
        self.privacy_mode = privacy_mode
        self.target_language = target_language
        
        # Translation services setup
        self.deepl_translator = None
        self.google_translator = None
        self.character_count_file = "deepl_usage.json"
        self.max_deepl_chars = 450000  # Switch to Google at 450k chars (safety margin)
        
        # Initialize translation services
        self._init_translation_services()
        
        # Load character usage counter
        self.deepl_chars_used = self._load_character_count()

    def update_config(self, enable_llm: Optional[bool] = None, enable_deepl: Optional[bool] = None, target_language: Optional[str] = None):
        if enable_llm is not None:
            self.enable_llm = enable_llm
        if enable_deepl is not None:
            self.enable_deepl = enable_deepl
        if target_language is not None:
            self.target_language = target_language
        self.logger.info(
            f"TextProcessor config updated: LLM={'on' if self.enable_llm else 'off'}, "
            f"DeepL={'on' if self.enable_deepl else 'off'}, Target: {self.target_language}"
        )

    def process_text(self, text: str, target_lang: str = None, target_language: str = None, **kwargs) -> str:
        """Process text with optional translation."""
        if not text:
            return ""

        processed = text.strip()
        
        # Use provided target language or default (support both arg names)
        translation_target = target_lang or target_language or self.target_language

        # Simple translation when DeepL is enabled
        if self.enable_deepl:
            translated = self._translate_text(processed, translation_target)
            if translated and translated != processed:
                processed = f"{processed} → {translated}"

        if self.enable_llm and not self.privacy_mode and self.llm_endpoint:
            self.logger.info("LLM processing enabled but not implemented; returning original text")

        return processed
    
    def _init_translation_services(self):
        """Initialize DeepL and Google Translate services"""
        self.logger.info(f"Initializing translation services...")
        self.logger.info(f"DEEPL_AVAILABLE: {DEEPL_AVAILABLE}")
        self.logger.info(f"deepl_api_key present: {bool(self.deepl_api_key)}")
        self.logger.info(f"privacy_mode: {self.privacy_mode}")
        
        # Initialize DeepL if available and API key provided
        if DEEPL_AVAILABLE and self.deepl_api_key and not self.privacy_mode:
            try:
                self.deepl_translator = deepl.Translator(self.deepl_api_key)
                self.logger.info("DeepL translator initialized successfully!")
            except Exception as e:
                self.logger.error(f"Failed to initialize DeepL: {e}")
        else:
            self.logger.warning(f"DeepL not initialized. Reasons: DEEPL_AVAILABLE={DEEPL_AVAILABLE}, has_api_key={bool(self.deepl_api_key)}, privacy_mode={self.privacy_mode}")
                
        # Initialize Google Translate as fallback
        if GOOGLETRANS_AVAILABLE:
            try:
                self.google_translator = GoogleTranslator(source='auto', target='en')
                self.logger.info("Google Translate initialized as fallback")
            except Exception as e:
                self.logger.error(f"Failed to initialize Google Translate: {e}")
    
    def _load_character_count(self) -> int:
        """Load DeepL character usage count from file"""
        try:
            if os.path.exists(self.character_count_file):
                with open(self.character_count_file, 'r') as f:
                    data = json.load(f)
                    return data.get('characters_used', 0)
        except Exception as e:
            self.logger.warning(f"Could not load character count: {e}")
        return 0
    
    def _save_character_count(self):
        """Save DeepL character usage count to file"""
        try:
            data = {
                'characters_used': self.deepl_chars_used,
                'max_characters': 500000,
                'percentage_used': (self.deepl_chars_used / 500000) * 100
            }
            with open(self.character_count_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save character count: {e}")
    
    def get_usage_stats(self) -> dict:
        """Get current DeepL usage statistics"""
        return {
            'characters_used': self.deepl_chars_used,
            'max_characters': 500000,
            'percentage_used': (self.deepl_chars_used / 500000) * 100,
            'remaining_characters': 500000 - self.deepl_chars_used,
            'using_google_fallback': self.deepl_chars_used >= self.max_deepl_chars
        }
    
    def _translate_text(self, text: str, target_lang: str = "en") -> str:
        """Smart translation using DeepL -> Google -> Local fallback"""
        if not text:
            return ""
            
        # Try DeepL first (if available and under limit)
        if (self.deepl_translator and 
            self.deepl_chars_used < self.max_deepl_chars and
            not self.privacy_mode):
            try:
                # Map language codes for DeepL API
                deepl_lang_map = {
                    "en": "EN-US", "it": "IT", "es": "ES", 
                    "fr": "FR", "de": "DE", "pt": "PT-PT"
                }
                deepl_target = deepl_lang_map.get(target_lang.lower(), "EN-US")
                
                result = self.deepl_translator.translate_text(
                    text, 
                    target_lang=deepl_target
                )
                translated = result.text
                
                # Update character count
                chars_used = len(text)
                self.deepl_chars_used += chars_used
                self._save_character_count()
                
                self.logger.info(f"DeepL translation: {chars_used} chars used "
                               f"(Total: {self.deepl_chars_used}/500000)")
                return f"{translated} [DeepL]"
                
            except Exception as e:
                self.logger.warning(f"DeepL translation failed: {e}")
        
        # Try Google Translate as fallback
        if self.google_translator:
            try:
                # Map language codes for Google Translate
                lang_map = {"it": "italian", "en": "english", "es": "spanish", "fr": "french", "de": "german"}
                target_lang_name = lang_map.get(target_lang.lower(), "english")
                
                # Create new translator for specific target language
                translator = GoogleTranslator(source='auto', target=target_lang_name)
                translated = translator.translate(text)
                
                self.logger.info(f"Google Translate used as fallback")
                return f"{translated} [Google]"
                
            except Exception as e:
                self.logger.warning(f"Google Translate failed: {e}")
        
        # Final fallback: Local dictionary (simplified)
        self.logger.info("Using local dictionary fallback")
        return self._local_translate(text, target_lang)
    
    def _local_translate(self, text: str, target_lang: str) -> str:
        """Local dictionary translation (basic fallback)"""
        # Simplified local dictionary for common words
        basic_translations = {
            "ciao": "hello", "grazie": "thank you", "si": "yes", "no": "no",
            "dottore": "doctor", "paziente": "patient", "dolore": "pain",
            "bene": "well", "male": "bad", "oggi": "today"
        }
        
        words = text.lower().split()
        translated_words = []
        found_translations = 0
        
        for word in words:
            clean_word = word.strip(".,!?")
            if clean_word in basic_translations:
                translated_words.append(basic_translations[clean_word])
                found_translations += 1
            else:
                translated_words.append(word)
        
        if found_translations > 0:
            return " ".join(translated_words) + " [Local]"
        else:
            return f"[No translation available to {target_lang.upper()}]"

    def cleanup(self):
        """Cleanup resources"""
        pass
