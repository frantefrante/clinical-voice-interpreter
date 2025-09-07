"""
Piper TTS backend integration
Uses Piper Python library for local high-quality TTS synthesis.

Environment variables (via ConfigManager):
- TTS_BACKEND=piper
- PIPER_PATH=python (use Python library instead of binary)
- PIPER_MODEL=/path/to/voice.onnx
"""

import logging
import os
import platform
import subprocess
import tempfile
import wave
from typing import List, Dict, Optional

try:
    import piper
    PIPER_AVAILABLE = True
except ImportError:
    piper = None
    PIPER_AVAILABLE = False


class PiperTTS:
    def __init__(self, piper_path: Optional[str] = None, model_path: Optional[str] = None,
                 rate: int = 200, voice: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.piper_path = piper_path or 'python'
        self.model_path = model_path
        self.rate = rate
        self.voice = voice
        self.platform = platform.system().lower()
        self.piper_voice = None
        
        if PIPER_AVAILABLE and self.model_path and os.path.exists(self.model_path):
            try:
                # Check if JSON config file exists
                json_path = self.model_path + ".json"
                if not os.path.exists(json_path):
                    self.logger.error(f"❌ Piper JSON config missing: {json_path}")
                    self.logger.error("Download the corresponding .onnx.json file for this voice model")
                    self.piper_voice = None
                    return
                
                self.piper_voice = piper.PiperVoice.load(self.model_path)
                self.logger.info(f"✅ Piper voice loaded: {os.path.basename(self.model_path)}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load Piper voice: {e}")
                json_path = self.model_path + ".json"
                if not os.path.exists(json_path):
                    self.logger.error(f"💡 Missing config file: {json_path}")
                self.piper_voice = None

    def is_available(self) -> bool:
        try:
            if not PIPER_AVAILABLE:
                self.logger.warning("⚠️  Piper Python library not available")
                return False
            if not self.model_path or not os.path.exists(self.model_path):
                self.logger.warning("⚠️  Piper model not configured or not found")
                return False
            
            # Check JSON config file
            json_path = self.model_path + ".json"
            if not os.path.exists(json_path):
                self.logger.warning(f"⚠️  Piper JSON config missing: {json_path}")
                return False
                
            if not self.piper_voice:
                self.logger.warning("⚠️  Piper voice not loaded")
                return False
            return True
        except Exception as e:
            self.logger.warning(f"⚠️  Piper not available: {e}")
            return False

    def speak(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        if not self.is_available():
            return False
        try:
            # Generate audio using Piper Python library
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                wav_path = tmp.name
            
            # Synthesize audio using Piper library
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.piper_voice.config.sample_rate)
                
                # Write audio chunks as they are generated
                for audio_chunk in self.piper_voice.synthesize(text):
                    wav_file.writeframes(audio_chunk.audio_int16_bytes)
            
            # Play the audio
            self._play_wav(wav_path)
            
            # Cleanup temp file
            try:
                os.unlink(wav_path)
            except Exception:
                pass
                
            return True
        except Exception as e:
            self.logger.error(f"Piper speak error: {e}")
            return False

    def _play_wav(self, path: str):
        try:
            if self.platform == 'darwin':
                subprocess.run(['afplay', path], capture_output=True)
            elif self.platform == 'linux':
                # Try aplay, fallback to paplay
                r = subprocess.run(['aplay', path], capture_output=True)
                if r.returncode != 0:
                    subprocess.run(['paplay', path], capture_output=True)
            elif self.platform == 'windows':
                try:
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME)
                except Exception as e:
                    self.logger.warning(f"winsound playback failed: {e}")
            else:
                self.logger.warning(f"No playback method for platform {self.platform}")
        except Exception as e:
            self.logger.warning(f"Playback error: {e}")

    def get_voices(self) -> List[Dict[str, str]]:
        # Piper voice list is model-based; we can suggest using the configured model
        voices = []
        if self.model_path:
            voices.append({'name': os.path.basename(self.model_path), 'language': '', 'description': 'Piper model'})
        return voices

    def set_voice(self, voice_name: str) -> bool:
        # In Piper, voice selection is equivalent to selecting a model
        # This class expects PIPER_MODEL to be set externally
        self.voice = voice_name
        return True

    def set_model(self, model_path: str) -> bool:
        try:
            if model_path and os.path.exists(model_path):
                self.model_path = model_path
                self.logger.info(f"Piper model set to: {model_path}")
                return True
            else:
                self.logger.warning(f"Piper model does not exist: {model_path}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to set Piper model: {e}")
            return False

    def set_rate(self, rate: int) -> bool:
        # Piper CLI does not directly accept rate; can be emulated via length_scale in models
        # Keep value for future use (e.g., when adding length_scale mapping)
        self.rate = rate
        return True

    def cleanup(self):
        pass
