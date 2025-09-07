"""
Text-to-Speech Engine for Clinical Voice Interpreter
Cross-platform TTS with macOS 'say' command and Windows SAPI/pyttsx3
"""

import logging
import platform
import subprocess
import threading
from typing import Optional, List, Dict
import queue
import time

# Windows TTS
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

class TTSEngine:
    """
    Cross-platform Text-to-Speech engine
    - macOS: Uses built-in 'say' command
    - Windows: Uses pyttsx3/SAPI
    - Linux: Uses espeak as fallback
    """
    
    def __init__(self, enabled: bool = True, voice: Optional[str] = None, rate: int = 200,
                 backend: Optional[str] = None, piper_path: Optional[str] = None,
                 piper_model: Optional[str] = None):
        self.enabled = enabled
        self.voice = voice
        self.rate = rate
        self.platform = platform.system().lower()
        self.backend = (backend or '').lower() if backend else None
        
        # TTS queue for managing speech requests
        self.speech_queue = queue.Queue()
        self.speaking = False
        self.speech_thread = None
        
        # Platform-specific TTS engine
        self.tts_engine = None
        self.piper_engine = None
        self.piper_path = piper_path
        self.piper_model = piper_model
        
        self.logger = logging.getLogger(__name__)
        
        if self.enabled:
            self._init_tts_engine()
            self._start_speech_worker()
            
    def _init_tts_engine(self):
        """Initialize platform-specific TTS engine"""
        try:
            # Piper backend (optional, supersedes platform backends)
            if self.backend == 'piper':
                try:
                    from piper_tts import PiperTTS
                    self.piper_engine = PiperTTS(
                        piper_path=self.piper_path,
                        model_path=self.piper_model,
                        rate=self.rate,
                        voice=self.voice,
                    )
                    if not self.piper_engine.is_available():
                        self.logger.warning("Piper TTS not available. Falling back to system TTS.")
                        self.backend = None
                        self.piper_engine = None
                    else:
                        self.logger.info("Piper TTS initialized")
                        return
                except Exception as e:
                    self.logger.error(f"Failed to initialize Piper TTS: {e}")
                    self.backend = None

            if self.platform == "darwin":  # macOS
                self._init_macos_tts()
            elif self.platform == "windows":  # Windows
                self._init_windows_tts()
            elif self.platform == "linux":  # Linux
                self._init_linux_tts()
            else:
                self.logger.warning(f"Unsupported platform for TTS: {self.platform}")
                self.enabled = False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS engine: {e}")
            self.logger.info("TTS will be disabled, but transcription will still work")
            self.enabled = False
            
    def _init_macos_tts(self):
        """Initialize macOS TTS using 'say' command"""
        try:
            # Test if 'say' command is available by trying to say something silently
            result = subprocess.run(['say', ''], 
                                  capture_output=True, text=True, timeout=5)
            
            # 'say' exists if it runs without major errors
            self.logger.info("macOS 'say' command available")
            
            # Get available voices
            voices = self._get_macos_voices()
            self.logger.info(f"Available macOS voices: {len(voices)}")
            
            # Set default voice to a more natural one
            if not self.voice and voices:
                # Prefer these voices in order of preference for Italian/English
                preferred_voices = ["Samantha", "Alex", "Karen", "Victoria", "Daniel", "Fiona"]
                
                # Try to find a preferred voice
                for pref_voice in preferred_voices:
                    for voice in voices:
                        if pref_voice.lower() in voice['name'].lower():
                            self.voice = voice['name']
                            self.logger.info(f"Selected voice: {self.voice}")
                            break
                    if self.voice:
                        break
                        
                # If no preferred voice found, use first available
                if not self.voice:
                    self.voice = voices[0]['name']
                    self.logger.info(f"Using default voice: {self.voice}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize macOS TTS: {e}")
            raise
            
    def _init_windows_tts(self):
        """Initialize Windows TTS using pyttsx3"""
        try:
            if not PYTTSX3_AVAILABLE:
                raise Exception("pyttsx3 not available")
                
            self.tts_engine = pyttsx3.init()
            
            # Configure voice
            voices = self.tts_engine.getProperty('voices')
            if voices:
                self.logger.info(f"Available Windows voices: {len(voices)}")
                
                # Set voice if specified
                if self.voice:
                    for voice in voices:
                        if self.voice.lower() in voice.name.lower():
                            self.tts_engine.setProperty('voice', voice.id)
                            break
                            
            # Set speech rate
            self.tts_engine.setProperty('rate', self.rate)
            
            self.logger.info("Windows TTS (pyttsx3) initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Windows TTS: {e}")
            raise
            
    def _init_linux_tts(self):
        """Initialize Linux TTS using espeak"""
        try:
            # Test if espeak is available
            result = subprocess.run(['espeak', '--help'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                self.logger.info("Linux espeak available")
            else:
                raise Exception("espeak not available")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Linux TTS: {e}")
            raise
            
    def _start_speech_worker(self):
        """Start background thread for processing speech requests"""
        if self.speech_thread and self.speech_thread.is_alive():
            return
            
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()
        self.logger.info("Speech worker thread started")
        
    def _speech_worker(self):
        """Background worker for processing speech queue"""
        while self.enabled:
            try:
                # Get speech request from queue (with timeout)
                speech_request = self.speech_queue.get(timeout=1.0)
                
                if speech_request is None:  # Shutdown signal
                    break
                    
                text, priority = speech_request
                
                # Skip if already speaking and not high priority
                if self.speaking and not priority:
                    self.logger.debug("Skipping speech request (already speaking)")
                    continue
                    
                self._speak_text_sync(text)
                
                self.speech_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in speech worker: {e}")
                
    def speak(self, text: str, priority: bool = False) -> bool:
        """
        Speak text asynchronously
        
        Args:
            text: Text to speak
            priority: If True, interrupt current speech
            
        Returns:
            True if queued successfully
        """
        if not self.enabled or not text or not text.strip():
            return False
            
        try:
            # Clear queue if priority request
            if priority:
                self._clear_speech_queue()
                
            # Add to queue
            self.speech_queue.put((text.strip(), priority))
            self.logger.info(f"Speech queued: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue speech: {e}")
            return False
            
    def _speak_text_sync(self, text: str):
        """Speak text synchronously (platform-specific implementation)"""
        try:
            self.speaking = True
            
            if self.backend == 'piper' and self.piper_engine:
                self.piper_engine.speak(text)
            elif self.platform == "darwin":
                self._speak_macos(text)
            elif self.platform == "windows":
                self._speak_windows(text)
            elif self.platform == "linux":
                self._speak_linux(text)
                
        except Exception as e:
            self.logger.error(f"Failed to speak text: {e}")
        finally:
            self.speaking = False
            
    def _speak_macos(self, text: str):
        """Speak text on macOS using 'say' command"""
        try:
            cmd = ['say']
            
            if self.voice:
                cmd.extend(['-v', self.voice])
                
            if self.rate != 200:  # Default rate
                cmd.extend(['-r', str(self.rate)])
                
            cmd.append(text)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"macOS TTS error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.warning("macOS TTS timeout")
        except Exception as e:
            self.logger.error(f"macOS TTS error: {e}")
            
    def _speak_windows(self, text: str):
        """Speak text on Windows using pyttsx3"""
        try:
            if not self.tts_engine:
                return
                
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            
        except Exception as e:
            self.logger.error(f"Windows TTS error: {e}")
            
    def _speak_linux(self, text: str):
        """Speak text on Linux using espeak"""
        try:
            cmd = ['espeak']
            
            if self.rate != 200:
                # espeak rate is in words per minute
                wpm = max(80, min(450, self.rate))
                cmd.extend(['-s', str(wpm)])
                
            cmd.append(text)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"Linux TTS error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.warning("Linux TTS timeout")
        except Exception as e:
            self.logger.error(f"Linux TTS error: {e}")
            
    def _clear_speech_queue(self):
        """Clear pending speech requests"""
        try:
            while not self.speech_queue.empty():
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
        except queue.Empty:
            pass
            
    def stop_speaking(self):
        """Stop current speech (if possible) and clear queue"""
        self._clear_speech_queue()
        
        # Platform-specific stop commands
        try:
            if self.backend == 'piper' and self.piper_engine:
                # Piper playback is synchronous; nothing to stop except queue
                pass
            elif self.platform == "darwin":
                subprocess.run(['killall', 'say'], capture_output=True)
            elif self.platform == "windows" and self.tts_engine:
                self.tts_engine.stop()
                
        except Exception as e:
            self.logger.warning(f"Failed to stop TTS: {e}")
            
    def get_voices(self) -> List[Dict[str, str]]:
        """Get available voices for current platform"""
        try:
            if self.backend == 'piper' and self.piper_engine:
                return self.piper_engine.get_voices()
            elif self.platform == "darwin":
                return self._get_macos_voices()
            elif self.platform == "windows":
                return self._get_windows_voices()
            elif self.platform == "linux":
                return self._get_linux_voices()
            else:
                return []
        except Exception as e:
            self.logger.error(f"Failed to get voices: {e}")
            return []
            
    def _get_macos_voices(self) -> List[Dict[str, str]]:
        """Get macOS voices"""
        try:
            result = subprocess.run(['say', '-v', '?'], 
                                  capture_output=True, text=True, timeout=10)
            
            voices = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split()
                    if parts:
                        voice_name = parts[0]
                        language = parts[1] if len(parts) > 1 else "en_US"
                        voices.append({
                            'name': voice_name,
                            'language': language,
                            'description': ' '.join(parts[2:]) if len(parts) > 2 else ""
                        })
            
            return voices
            
        except Exception as e:
            self.logger.error(f"Failed to get macOS voices: {e}")
            return []
            
    def _get_windows_voices(self) -> List[Dict[str, str]]:
        """Get Windows voices"""
        try:
            if not self.tts_engine:
                return []
                
            voices = []
            for voice in self.tts_engine.getProperty('voices'):
                voices.append({
                    'name': voice.name,
                    'id': voice.id,
                    'language': getattr(voice, 'languages', ['en'])[0] if hasattr(voice, 'languages') else 'en'
                })
                
            return voices
            
        except Exception as e:
            self.logger.error(f"Failed to get Windows voices: {e}")
            return []
            
    def _get_linux_voices(self) -> List[Dict[str, str]]:
        """Get Linux voices (limited with espeak)"""
        return [
            {'name': 'default', 'language': 'en', 'description': 'Default espeak voice'}
        ]
        
    def set_voice(self, voice_name: str) -> bool:
        """Set TTS voice"""
        try:
            self.voice = voice_name
            
            if self.backend == 'piper' and self.piper_engine:
                # Piper doesn't support named voices beyond model selection
                # Change is applied by selecting another model externally
                self.voice = voice_name
                self.logger.info(f"Piper voice preference set to: {voice_name}")
                return True
            if self.platform == "windows" and self.tts_engine:
                voices = self.tts_engine.getProperty('voices')
                for voice in voices:
                    if voice_name.lower() in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        self.logger.info(f"Voice set to: {voice.name}")
                        return True
                        
            self.logger.info(f"Voice preference set to: {voice_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set voice: {e}")
            return False
            
    def set_rate(self, rate: int) -> bool:
        """Set speech rate"""
        try:
            self.rate = max(50, min(500, rate))  # Clamp to reasonable range
            
            if self.backend == 'piper' and self.piper_engine:
                self.piper_engine.set_rate(self.rate)
                
            if self.platform == "windows" and self.tts_engine:
                self.tts_engine.setProperty('rate', self.rate)
                
            self.logger.info(f"Speech rate set to: {self.rate}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set speech rate: {e}")
            return False
            
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self.speaking
        
    def get_info(self) -> Dict[str, any]:
        """Get TTS engine information"""
        return {
            'enabled': self.enabled,
            'platform': self.platform,
            'voice': self.voice,
            'rate': self.rate,
            'speaking': self.speaking,
            'queue_size': self.speech_queue.qsize(),
            'available_voices': len(self.get_voices())
        }
        
    def test_speech(self, test_text: str = "This is a test of the text to speech system.") -> bool:
        """Test TTS functionality"""
        try:
            return self.speak(test_text, priority=True)
        except Exception as e:
            self.logger.error(f"TTS test failed: {e}")
            return False
            
    def cleanup(self):
        """Clean up TTS resources"""
        try:
            self.enabled = False
            
            # Stop current speech
            self.stop_speaking()
            
            # Signal speech worker to stop
            if self.speech_thread and self.speech_thread.is_alive():
                self.speech_queue.put(None)  # Shutdown signal
                self.speech_thread.join(timeout=2.0)
                
            # Clean up platform-specific resources
            if self.platform == "windows" and self.tts_engine:
                try:
                    self.tts_engine.stop()
                except:
                    pass
            if self.piper_engine:
                try:
                    self.piper_engine.cleanup()
                except Exception:
                    pass
                
            self.logger.info("TTS engine cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during TTS cleanup: {e}")
