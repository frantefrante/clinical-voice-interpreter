"""
Whisper Transcriber for Clinical Voice Interpreter
Provides local transcription using OpenAI Whisper with graceful fallbacks
"""

import logging
import os
import re
from typing import Optional

try:
    import whisper  # openai-whisper
    WHISPER_AVAILABLE = True
except Exception:
    whisper = None
    WHISPER_AVAILABLE = False


class WhisperTranscriber:
    """Thin wrapper around openai-whisper with safe fallbacks"""

    def __init__(self, model_name: str = "small", language: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name or "small"
        self.language = language
        self.model = None

        if not WHISPER_AVAILABLE:
            self.logger.warning("Whisper library not available. Transcription disabled.")
        else:
            self._load_model(self.model_name)

    def _load_model(self, model_name: str):
        try:
            self.logger.info(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name)
            self.model_name = model_name
            self.logger.info("Whisper model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model '{model_name}': {e}")
            self.model = None

    def update_model(self, model_name: Optional[str] = None, language: Optional[str] = None):
        """Update model name and language, reloading model if needed"""
        if language is not None:
            self.language = language
        if model_name and model_name != self.model_name:
            if WHISPER_AVAILABLE:
                self._load_model(model_name)
            else:
                self.model_name = model_name

    def transcribe(self, audio_file: str) -> str:
        """Transcribe an audio file and return text (empty on failure)"""
        if not WHISPER_AVAILABLE or self.model is None:
            self.logger.warning("Transcription unavailable (Whisper missing or model not loaded)")
            return ""
        
        # Check if audio file is too small (less than 0.2 seconds of audio at 16kHz)
        try:
            file_size = os.path.getsize(audio_file)
            min_size = 16000 * 2 * 0.2  # 16kHz * 2 bytes * 0.2 seconds = ~6.4KB
            if file_size < min_size:
                self.logger.warning(f"Audio file too small ({file_size} bytes), skipping transcription")
                return ""
        except Exception as e:
            self.logger.warning(f"Could not check audio file size: {e}")
        
        try:
            result = self.model.transcribe(
                audio_file,
                language=self.language,
                fp16=False,                   # CPU-friendly
                temperature=0.0,              # conservative decoding
                no_speech_threshold=0.8,      # avoid false positives on silence
                condition_on_previous_text=False,
            )
            text = (result or {}).get("text", "").strip()
            
            # Filter out unwanted subtitle/caption text
            text = self._filter_unwanted_text(text)
            
            return text
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            return ""
    
    def _filter_unwanted_text(self, text: str) -> str:
        """Filter out unwanted subtitle/caption hallucinatory text"""
        if not text:
            return ""
            
        text_lower = text.lower().strip()
        # Filter if it looks like a QTSS caption regardless of exact match
        bad_markers = [
            "qtss",
            "sottotitoli",
            "subtitles",
            "captions",
        ]
        if any(m in text_lower for m in bad_markers):
            self.logger.info(f"Filtered out subtitle text: {text}")
            return ""
        return text

    def cleanup(self):
        """Cleanup resources (no-op for whisper)"""
        self.model = None
