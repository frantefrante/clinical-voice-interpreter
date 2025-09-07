"""
Piper TTS backend integration
Requires Piper binary and a voice model (.onnx) installed locally.

Environment variables (via ConfigManager):
- TTS_BACKEND=piper
- PIPER_PATH=/usr/local/bin/piper (or 'piper' in PATH)
- PIPER_MODEL=/path/to/voice.onnx
"""

import logging
import os
import platform
import subprocess
import tempfile
from typing import List, Dict, Optional


class PiperTTS:
    def __init__(self, piper_path: Optional[str] = None, model_path: Optional[str] = None,
                 rate: int = 200, voice: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.piper_path = piper_path or 'piper'
        self.model_path = model_path
        self.rate = rate
        self.voice = voice
        self.platform = platform.system().lower()

    def is_available(self) -> bool:
        try:
            if not self.model_path or not os.path.exists(self.model_path):
                self.logger.warning("Piper model not configured or not found")
                return False
            # Check piper binary
            result = subprocess.run([self.piper_path, '--help'], capture_output=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.warning(f"Piper not available: {e}")
            return False

    def speak(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        if not self.is_available():
            return False
        try:
            # Generate WAV to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                wav_path = tmp.name
            cmd = [
                self.piper_path,
                '-m', self.model_path,
                '--output_file', wav_path,
            ]
            # Piper accepts text on stdin
            proc = subprocess.run(cmd, input=text, text=True, capture_output=True)
            if proc.returncode != 0:
                self.logger.error(f"Piper synthesis failed: {proc.stderr}")
                return False
            # Play the audio once
            self._play_wav(wav_path)
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

    def set_rate(self, rate: int) -> bool:
        # Piper CLI does not directly accept rate; can be emulated via length_scale in models
        # Keep value for future use (e.g., when adding length_scale mapping)
        self.rate = rate
        return True

    def cleanup(self):
        pass

