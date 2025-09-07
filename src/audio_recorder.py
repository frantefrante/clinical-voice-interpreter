"""
Audio Recorder for Clinical Voice Interpreter
Handles audio recording with configurable parameters
"""

import logging
import threading
import tempfile
import wave
import time
from typing import Optional
import os
from array import array
import math

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio not available. Audio recording will be disabled.")

class AudioRecorder:
    """
    Audio recorder with configurable sample rate, channels, and chunk size
    """
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        self.audio = None
        self.stream = None
        self.recording = False
        self.frames = []
        self.record_thread = None
        self.input_device_index = None  # default system input
        self.input_gain = 1.0  # software gain multiplier (0.5x - 3.0x)
        # Live level meters
        self.level_rms = 0.0
        self.level_peak = 0.0
        
        self.logger = logging.getLogger(__name__)
        
        if not PYAUDIO_AVAILABLE:
            self.logger.error("PyAudio not available")
            return
            
        self._init_audio()
        
    def _init_audio(self):
        """Initialize PyAudio"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # Log available audio devices for debugging
            self._log_audio_devices()
            
            self.logger.info(f"Audio initialized - Rate: {self.sample_rate}Hz, "
                           f"Channels: {self.channels}, Chunk: {self.chunk_size}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize PyAudio: {e}")
            self.audio = None
            
    def _log_audio_devices(self):
        """Log available audio input devices"""
        try:
            self.logger.info("Available audio input devices:")
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    self.logger.info(f"  {i}: {device_info['name']} "
                                   f"(Channels: {device_info['maxInputChannels']}, "
                                   f"Rate: {device_info['defaultSampleRate']})")
        except Exception as e:
            self.logger.warning(f"Could not enumerate audio devices: {e}")
            
    def start_recording(self) -> bool:
        """Start audio recording"""
        if not self.audio:
            self.logger.error("Audio not initialized")
            return False
            
        if self.recording:
            self.logger.warning("Already recording")
            return False
            
        try:
            # Clear previous frames
            self.frames = []
            self.level_rms = 0.0
            self.level_peak = 0.0
            
            # Open audio stream
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.input_device_index  # Use selected/default input device
            )
            
            self.recording = True
            
            # Start recording thread
            self.record_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.record_thread.start()
            
            self.logger.info("Audio recording started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self._cleanup_stream()
            return False
            
    def stop_recording(self) -> Optional[str]:
        """Stop recording and return path to saved audio file"""
        if not self.recording:
            self.logger.warning("Not currently recording")
            return None
            
        try:
            self.recording = False
            
            # Wait for recording thread to finish
            if self.record_thread and self.record_thread.is_alive():
                self.record_thread.join(timeout=1.0)
                
            # Close stream
            self._cleanup_stream()
            
            # Save recorded audio to temporary file
            if self.frames:
                audio_file = self._save_audio()
                self.logger.info(f"Recording saved to: {audio_file}")
                return audio_file
            else:
                self.logger.warning("No audio data recorded")
                return None
                
        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            return None
            
    def _record_audio(self):
        """Audio recording loop (runs in separate thread)"""
        self.logger.info("Recording thread started")
        
        try:
            while self.recording and self.stream:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    # Apply software gain if set
                    if abs(self.input_gain - 1.0) > 1e-3:
                        data = self._apply_gain(data, self.input_gain)

                    # Update VU levels (RMS, peak) normalized to 0..1
                    try:
                        samples = array('h')
                        samples.frombytes(data)
                        if samples:
                            peak = max(abs(s) for s in samples)
                            acc = 0
                            for s in samples:
                                acc += s * s
                            rms = math.sqrt(acc / len(samples))
                            self.level_peak = min(1.0, peak / 32768.0)
                            self.level_rms = min(1.0, rms / 32768.0)
                    except Exception:
                        pass

                    self.frames.append(data)
                except Exception as e:
                    self.logger.error(f"Error reading audio data: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Recording thread error: {e}")
        finally:
            self.logger.info("Recording thread finished")
            
    def _apply_gain(self, data: bytes, gain: float) -> bytes:
        """Apply software gain to 16-bit PCM little-endian frames"""
        try:
            samples = array('h')
            samples.frombytes(data)
            # Scale with clipping
            g = max(0.0, min(5.0, float(gain)))
            for i in range(len(samples)):
                v = int(samples[i] * g)
                if v > 32767:
                    v = 32767
                elif v < -32768:
                    v = -32768
                samples[i] = v
            return samples.tobytes()
        except Exception:
            return data

    def _save_audio(self) -> str:
        """Save recorded frames to a temporary WAV file"""
        try:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix='.wav', prefix='clinical_voice_'
            )
            temp_filename = temp_file.name
            temp_file.close()
            
            # Write WAV file
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(self.frames))
                
            # Get file size for logging
            file_size = os.path.getsize(temp_filename)
            duration = len(self.frames) * self.chunk_size / self.sample_rate
            
            self.logger.info(f"Audio saved: {temp_filename} "
                           f"({file_size} bytes, {duration:.1f}s)")
            
            return temp_filename
            
        except Exception as e:
            self.logger.error(f"Failed to save audio: {e}")
            raise
            
    def _cleanup_stream(self):
        """Clean up audio stream"""
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                
        except Exception as e:
            self.logger.warning(f"Error cleaning up audio stream: {e}")
            
    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self.recording
        
    def get_audio_info(self) -> dict:
        """Get current audio configuration"""
        return {
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'chunk_size': self.chunk_size,
            'recording': self.recording,
            'available': PYAUDIO_AVAILABLE and self.audio is not None
        }
        
    def test_audio_input(self) -> bool:
        """Test if audio input is working"""
        if not self.audio:
            return False
            
        try:
            # Try to open and immediately close a stream
            test_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # Read a small amount of data
            test_stream.read(self.chunk_size, exception_on_overflow=False)
            
            test_stream.close()
            
            self.logger.info("Audio input test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Audio input test failed: {e}")
            return False
            
    def get_input_devices(self) -> list:
        """Get list of available input devices"""
        devices = []
        
        if not self.audio:
            return devices
            
        try:
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': device_info['defaultSampleRate']
                    })
        except Exception as e:
            self.logger.error(f"Failed to enumerate input devices: {e}")
            
        return devices
        
    def set_input_device(self, device_index: Optional[int]):
        """Set specific input device (None for default)"""
        # Note: This would require reopening the stream if recording
        # For now, we store the preference for next recording session
        self.input_device_index = device_index
        self.logger.info(f"Input device set to: {device_index}")
        
    def set_input_gain(self, gain: float):
        """Set software input gain multiplier"""
        try:
            g = max(0.1, min(5.0, float(gain)))
            self.input_gain = g
            self.logger.info(f"Input gain set to: x{g:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to set input gain: {e}")
        
    def cleanup(self):
        """Clean up audio resources"""
        try:
            if self.recording:
                self.stop_recording()
                
            self._cleanup_stream()
            
            if self.audio:
                self.audio.terminate()
                self.audio = None
                
            self.logger.info("Audio recorder cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during audio recorder cleanup: {e}")

    def get_level(self) -> dict:
        """Return current input level {'rms': float, 'peak': float} in 0..1"""
        return {'rms': float(self.level_rms), 'peak': float(self.level_peak)}
