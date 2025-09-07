"""
Clinical Voice Interpreter Package
Privacy-first voice transcription system
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Import main components for easy access
# from .stream_deck_controller import StreamDeckController  # TODO: Fix imports
from .audio_recorder import AudioRecorder
# from .whisper_transcriber import WhisperTranscriber  # TODO: Implement WhisperTranscriber
# from .text_processor import TextProcessor  # TODO: Fix class name
# from .tts_engine import TTSEngine  # TODO: Fix imports
# from .session_manager import SessionManager  # TODO: Fix imports
# from .config_manager import ConfigManager, ClinicalVoiceConfig  # TODO: Fix imports

__all__ = [
    # 'StreamDeckController',  # TODO: Fix imports
    'AudioRecorder', 
    # 'WhisperTranscriber',  # TODO: Implement
    # 'TextProcessor',  # TODO: Fix imports
    # 'TTSEngine',  # TODO: Fix imports
    # 'SessionManager',  # TODO: Fix imports
    # 'ConfigManager',  # TODO: Fix imports
    # 'ClinicalVoiceConfig'  # TODO: Fix imports
]
