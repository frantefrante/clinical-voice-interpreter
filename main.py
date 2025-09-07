#!/usr/bin/env python3
"""
Clinical Voice Interpreter - Privacy-First Push-to-Talk Voice Transcription
Based on Stream Deck controls with local Whisper processing and extensible text processing.

This application provides:
- Stream Deck button control for push-to-talk
- Local Whisper transcription (multiple model sizes)
- Extensible text processing (LLM, DeepL, pass-through)
- Cross-platform TTS
- Local persistence with privacy focus
"""

import os
import sys
import logging
import threading
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# Aggiungi il percorso src al PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Core components - IMPORT CORRETTI
from stream_deck_controller import StreamDeckController
from audio_recorder import AudioRecorder
from whisper_transcriber import WhisperTranscriber
from text_processor import TextProcessor
from tts_engine import TTSEngine
from session_manager import SessionManager
from config_manager import ConfigManager, ClinicalVoiceConfig
from llm_processor import LLMProcessor

# Load environment configuration
from dotenv import load_dotenv
load_dotenv()

@dataclass
class AppConfig:
    """Application configuration data class"""
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    
    # Whisper settings
    whisper_model: str = "small"  # tiny/base/small/medium/large-v3
    whisper_language: Optional[str] = None  # Auto-detect if None
    
    # Stream Deck settings
    deck_button_index: int = 0
    
    # Text processing
    enable_llm: bool = False
    llm_endpoint: Optional[str] = None
    enable_deepl: bool = False
    deepl_api_key: Optional[str] = None
    
    # TTS settings
    enable_tts: bool = True
    tts_voice: Optional[str] = None
    
    # Storage settings
    output_dir: str = "./output"
    enable_persistence: bool = True
    
    # Privacy settings
    privacy_mode: bool = True  # No cloud calls without explicit consent

class ClinicalVoiceInterpreter:
    """Main application class for the Clinical Voice Interpreter"""
    
    def __init__(self, config: Optional[AppConfig] = None):
        # Initialize logging first
        self._setup_logging()
        
        # Use ConfigManager for proper environment variable handling
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.running = False
        self.recording = False
        self.current_translation_mode = 'it_to_en'  # Default mode
        # PTT session and timing tracking
        self._key_pressed = False
        self._press_time = 0.0
        self._last_press_time = 0.0
        self._ptt_active = False
        self._stop_timer_id = None
        try:
            self._min_press_ms = int(os.getenv('MIN_PRESS_MS', '350'))
        except Exception:
            self._min_press_ms = 350
        
        # Initialize components
        self.logger.info("Initializing Clinical Voice Interpreter...")
        self._init_components()
        
        # Setup directories
        self._setup_directories()
        
        # Initialize GUI
        self._init_gui()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('clinical_voice_interpreter.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _init_components(self):
        """Initialize all application components"""
        try:
            # Configuration manager
            self.config_manager = ConfigManager()
            
            # Stream Deck controller
            self.stream_deck = StreamDeckController(
                button_index=self.config.deck_button_index,
                on_press=self._on_button_press,
                on_release=self._on_button_release
            )
            
            # Audio recorder
            self.audio_recorder = AudioRecorder(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                chunk_size=self.config.chunk_size
            )
            # Optionally set a specific input device via env var
            try:
                env_input_idx = os.getenv('AUDIO_INPUT_INDEX')
                if env_input_idx is not None:
                    self.audio_recorder.set_input_device(int(env_input_idx))
                    self.logger.info(f"Audio input device set from env: {env_input_idx}")
            except Exception as e:
                self.logger.warning(f"Could not set audio input from env: {e}")
            
            # Whisper transcriber
            self.transcriber = WhisperTranscriber(
                model_name=self.config.whisper_model,
                language=self.config.whisper_language
            )
            
            # Text processor (extensible for LLM/DeepL)
            self.text_processor = TextProcessor(
                enable_llm=self.config.enable_llm,
                llm_endpoint=self.config.llm_endpoint,
                enable_deepl=self.config.enable_deepl,
                deepl_api_key=self.config.deepl_api_key,
                privacy_mode=self.config.privacy_mode
            )
            
            # TTS engine (supports system or Piper backend)
            self.tts_engine = TTSEngine(
                enabled=self.config.enable_tts,
                voice=self.config.tts_voice,
                rate=self.config.tts_rate,
                backend=getattr(self.config, 'tts_backend', None),
                piper_path=getattr(self.config, 'piper_path', None),
                piper_model=getattr(self.config, 'piper_model', None),
            )
            
            # Session manager for persistence
            self.session_manager = SessionManager(
                output_dir=self.config.output_dir,
                enabled=self.config.enable_persistence
            )
            
            # LLM processor for AI analysis
            self.llm_processor = LLMProcessor(
                openai_api_key=self.config.openai_api_key,
                anthropic_api_key=getattr(self.config, 'anthropic_api_key', None),
                llm_endpoint=self.config.llm_endpoint,
                privacy_mode=self.config.privacy_mode
            )
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
            
    def _setup_directories(self):
        """Create necessary directories"""
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Output directory ready: {self.config.output_dir}")
        
    def _init_gui(self):
        """Initialize the minimal GUI interface"""
        self.root = tk.Tk()
        self.root.title("Clinical Voice Interpreter")
        # Larger default size to show translation box without resizing
        self.root.geometry("1000x800")
        try:
            self.root.minsize(900, 700)
        except Exception:
            pass
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Ready to start")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.recording_indicator = ttk.Label(status_frame, text="●", foreground="gray")
        self.recording_indicator.grid(row=0, column=1, sticky=tk.E)
        
        # VU (volume) indicator
        self.vu_bar = ttk.Progressbar(status_frame, orient='horizontal', mode='determinate', maximum=100, length=200)
        self.vu_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(4, 0))
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="5")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Whisper model selection
        ttk.Label(config_frame, text="Whisper Model:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.model_var = tk.StringVar(value=self.config.whisper_model)
        model_combo = ttk.Combobox(config_frame, textvariable=self.model_var, 
                                 values=["tiny", "base", "small", "medium", "large-v3"],
                                 state="readonly", width=15)
        model_combo.grid(row=0, column=1, sticky=tk.W)
        
        # Auto-save configuration when model changes
        model_combo.bind('<<ComboboxSelected>>', lambda e: self._save_config_changes())
        
        # Input Language selection  
        ttk.Label(config_frame, text="Input Language:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.language_var = tk.StringVar(value=self.config.whisper_language or "auto")
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var,
                                    values=["auto", "en", "it", "es", "fr", "de", "zh", "ar", "bn", "sq"],
                                    state="readonly", width=15)
        language_combo.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # Translation Target Language selection
        ttk.Label(config_frame, text="Translate to:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.target_language_var = tk.StringVar(value="en")  # Default to English
        target_combo = ttk.Combobox(config_frame, textvariable=self.target_language_var,
                                   values=["en", "it", "es", "fr", "de", "zh", "ar", "bn", "sq"],
                                   state="readonly", width=15)
        target_combo.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))

        # Input Device selection
        ttk.Label(config_frame, text="Input Device:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.input_device_var = tk.StringVar(value="")
        self.input_device_combo = ttk.Combobox(
            config_frame,
            textvariable=self.input_device_var,
            values=[],
            state="readonly",
            width=40,
        )
        self.input_device_combo.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))
        self.input_device_combo.bind('<<ComboboxSelected>>', lambda e: self._on_input_device_change())

        # Input Gain selection
        ttk.Label(config_frame, text="Input Gain:").grid(row=4, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.input_gain_var = tk.DoubleVar(value=float(os.getenv('INPUT_GAIN', '1.0') or 1.0))
        self.input_gain_scale = ttk.Scale(
            config_frame,
            from_=0.5,
            to=3.0,
            orient='horizontal',
            variable=self.input_gain_var,
            command=lambda v: self._on_input_gain_change(v),
            length=200
        )
        self.input_gain_scale.grid(row=4, column=1, sticky=tk.W, pady=(5, 0))
        # Numeric label for gain value
        self.input_gain_value_label = ttk.Label(config_frame, text=f"x{self.input_gain_var.get():.2f}")
        self.input_gain_value_label.grid(row=4, column=2, sticky=tk.W, padx=(10, 0))
        
        # Text processing options
        processing_frame = ttk.LabelFrame(main_frame, text="Text Processing", padding="5")
        processing_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.llm_var = tk.BooleanVar(value=self.config.enable_llm)
        ttk.Checkbutton(processing_frame, text="Enable LLM Processing", 
                       variable=self.llm_var).grid(row=0, column=0, sticky=tk.W)
        
        self.deepl_var = tk.BooleanVar(value=self.config.enable_deepl)
        ttk.Checkbutton(processing_frame, text="Enable DeepL Translation", 
                       variable=self.deepl_var).grid(row=1, column=0, sticky=tk.W)
        
        # DeepL usage counter
        self.usage_label = ttk.Label(processing_frame, text="DeepL: 0/500,000 chars (0%)", 
                                    font=('TkDefaultFont', 8))
        self.usage_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        
        self.tts_var = tk.BooleanVar(value=self.config.enable_tts)
        ttk.Checkbutton(processing_frame, text="Enable Text-to-Speech", 
                       variable=self.tts_var).grid(row=2, column=0, sticky=tk.W)

        # TTS Backend selection
        ttk.Label(processing_frame, text="TTS Backend:").grid(row=0, column=1, sticky=tk.W, padx=(10, 5))
        self.tts_backend_var = tk.StringVar(value=(getattr(self.config, 'tts_backend', None) or 'system'))
        self.tts_backend_combo = ttk.Combobox(processing_frame, textvariable=self.tts_backend_var,
                                              values=['system', 'piper'], state='readonly', width=12)
        self.tts_backend_combo.grid(row=0, column=2, sticky=tk.W)
        self.tts_backend_combo.bind('<<ComboboxSelected>>', lambda e: self._on_tts_backend_change())

        # TTS Voice selection
        ttk.Label(processing_frame, text="TTS Voice:").grid(row=2, column=1, sticky=tk.W, padx=(10, 5))
        self.tts_voice_var = tk.StringVar(value=self.config.tts_voice or "")
        self.tts_voice_combo = ttk.Combobox(processing_frame, textvariable=self.tts_voice_var,
                                            values=[], state="readonly", width=28)
        self.tts_voice_combo.grid(row=2, column=2, sticky=tk.W)
        self.tts_voice_combo.bind('<<ComboboxSelected>>', lambda e: self._on_tts_voice_change())

        # TTS Rate control
        ttk.Label(processing_frame, text="TTS Rate:").grid(row=3, column=0, sticky=tk.W)
        self.tts_rate_var = tk.IntVar(value=getattr(self.config, 'tts_rate', 200))
        tts_rate = ttk.Scale(processing_frame, from_=120, to=240, orient='horizontal', length=180,
                             command=lambda v: self._on_tts_rate_change(v), variable=self.tts_rate_var)
        tts_rate.grid(row=3, column=1, sticky=tk.W)
        self.tts_rate_value = ttk.Label(processing_frame, text=f"{self.tts_rate_var.get()} WPM")
        self.tts_rate_value.grid(row=3, column=2, sticky=tk.W, padx=(10, 0))

        # Piper model selection controls (visible only when backend=piper)
        self.piper_model_label = ttk.Label(processing_frame, text="Model: (not set)")
        self.piper_model_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 5))
        self.piper_model_button = ttk.Button(processing_frame, text="Select Piper Model...",
                                             command=self._select_piper_model)
        self.piper_model_button.grid(row=4, column=2, sticky=tk.W)
        
        # Keyboard instructions
        instructions_frame = ttk.LabelFrame(main_frame, text="Keyboard Controls", padding="5")
        instructions_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(instructions_frame, text="• Hold SPACEBAR for Italian→English", 
                 font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(instructions_frame, text="• Hold F2 for English→Italian", 
                 font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W)
        ttk.Label(instructions_frame, text="• Release key to stop and transcribe", 
                 font=('TkDefaultFont', 9)).grid(row=2, column=0, sticky=tk.W)
        ttk.Label(instructions_frame, text="• Works from anywhere in the window", 
                 font=('TkDefaultFont', 9, 'italic')).grid(row=3, column=0, sticky=tk.W)
        
        # Test button for hotkeys
        test_button = ttk.Button(instructions_frame, text="Test Hotkeys", 
                               command=self._test_hotkeys)
        test_button.grid(row=4, column=0, sticky=tk.W, pady=(5, 0))

        # Microphone test button (records 2s and reports file size/duration)
        mic_test_button = ttk.Button(instructions_frame, text="🎙️ Test Mic (2s)",
                                   command=lambda: self._test_microphone(2))
        mic_test_button.grid(row=4, column=1, sticky=tk.W, pady=(5, 0))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        
        self.start_button = ttk.Button(button_frame, text="Start Service", 
                                     command=self._start_service)
        self.start_button.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="Stop Service", 
                                    command=self._stop_service, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(5, 0))
        
        # LLM Analysis buttons (second row)
        self.review_button = ttk.Button(button_frame, text="🔍 Review Conversation", 
                                      command=self._review_conversation)
        self.review_button.grid(row=1, column=0, padx=(0, 5), pady=(5, 0))
        
        self.query_button = ttk.Button(button_frame, text="💬 LLM Query", 
                                     command=self._show_query_dialog)
        self.query_button.grid(row=1, column=1, padx=(5, 0), pady=(5, 0))
        
        # Output display
        output_frame = ttk.LabelFrame(main_frame, text="Latest Transcription", padding="5")
        output_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        self.output_text = tk.Text(output_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind Enter key for manual text translation - DISABLED FOR NOW
        # self.output_text.bind('<Return>', self._on_manual_text_entry)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        # Keyboard controls
        self._setup_keyboard_controls()
        # Populate input devices list
        self._populate_input_devices()
        # Apply initial input gain to recorder
        try:
            self.audio_recorder.set_input_gain(self.input_gain_var.get())
        except Exception:
            pass
        # Populate TTS voices and backend UI
        self._populate_tts_voices()
        self._update_tts_backend_ui()
        
        # Start VU updates
        self._schedule_vu_update()
        
    def _setup_keyboard_controls(self):
        """Setup keyboard controls to replace Stream Deck functionality"""
        # Bind keyboard events for bidirectional translation
        # Only activate when focus is NOT on the text widget
        self.root.bind('<KeyPress-space>', self._on_global_key_press)
        self.root.bind('<KeyRelease-space>', self._on_global_key_release)
        self.root.bind('<KeyPress-F2>', self._on_global_key_press)
        self.root.bind('<KeyRelease-F2>', self._on_global_key_release)
        
        # Make sure window can receive keyboard events and stays on top when recording
        self.root.focus_set()
        self.root.focus_force()
        
        # Bind focus events to ensure keyboard capture works
        self.root.bind('<FocusIn>', self._on_focus_in)
        self.root.bind('<FocusOut>', self._on_focus_out)
    
    def _on_global_key_press(self, event):
        """Handle global keyboard press - check if text widget has focus"""
        # Don't interfere if text widget has focus (user is typing)
        if self.root.focus_get() == self.output_text:
            return
            
        # Determine translation mode from key
        if event.keysym == 'space':
            self._on_key_press(event, 'it_to_en')
        elif event.keysym == 'F2':
            self._on_key_press(event, 'en_to_it')
    
    def _on_global_key_release(self, event):
        """Handle global keyboard release - check if text widget has focus"""
        # Don't interfere if text widget has focus (user is typing)
        if self.root.focus_get() == self.output_text:
            return
            
        # Determine translation mode from key
        if event.keysym == 'space':
            self._on_key_release(event, 'it_to_en')
        elif event.keysym == 'F2':
            self._on_key_release(event, 'en_to_it')
    
    def _on_key_press(self, event, translation_mode):
        """Handle keyboard key press (start recording)"""
        if not self.running:
            return
            
        now = time.time()
        self._last_press_time = now
        # If a PTT session is already active, just update timestamp and ignore repeats
        if self._ptt_active:
            return

        # Start a new PTT session
        self._ptt_active = True
        self._key_pressed = True
        self._press_time = now
        self.current_translation_mode = translation_mode

        # Cancel any pending stop timer
        if self._stop_timer_id is not None:
            try:
                self.root.after_cancel(self._stop_timer_id)
            except Exception:
                pass
            self._stop_timer_id = None

        # Update status to show current mode
        mode_text = "IT→EN" if translation_mode == 'it_to_en' else "EN→IT"
        self.status_label.config(text=f"Recording - {mode_text} mode...")
        self.logger.info(f"Starting recording in {mode_text} mode")

        # Force Whisper language by mode to reduce hallucinations
        try:
            if translation_mode == 'it_to_en':
                # Forward: from Italian (fixed) to selected target
                forced_lang = 'it'
            else:
                # Reverse: from selected target back to Italian
                forced_lang = self.target_language_var.get() or 'en'
            self.transcriber.update_model(language=forced_lang)
        except Exception:
            pass
        
        self._on_button_press()
    
    def _on_key_release(self, event, translation_mode):
        """Handle keyboard key release (stop recording)"""
        if not self.running:
            return
            
        if not self._ptt_active:
            return
        self._key_pressed = False
        # Schedule a guarded stop that will be canceled if we get a new press soon (auto-repeat)
        def try_stop():
            # If we received a press recently, delay stop again
            gap_ms = (time.time() - self._last_press_time) * 1000.0
            if gap_ms < self._min_press_ms:
                # Reschedule until key is truly released
                self._stop_timer_id = self.root.after(int(self._min_press_ms - gap_ms), try_stop)
                self.logger.info(f"Key released early ({gap_ms:.0f}ms); delaying stop by {int(self._min_press_ms - gap_ms)}ms")
                return
            # Proceed to stop
            self._ptt_active = False
            self._stop_timer_id = None
            self._on_button_release()
        # Start the guarded stop timer
        self._stop_timer_id = self.root.after(0, try_stop)
    
    def _on_focus_in(self, event):
        """Handle window gaining focus"""
        self.status_label.config(text="Service running - SPACEBAR(IT→EN) | F2(EN→IT) [READY]")
        
    def _on_focus_out(self, event):
        """Handle window losing focus"""
        if self.running:
            self.status_label.config(text="Service running - Click window first [FOCUS NEEDED]")
        
    def _start_service(self):
        """Start the voice interpretation service"""
        try:
            # Update configuration from GUI
            self._update_config_from_gui()
            
            # Start Stream Deck
            self.stream_deck.start()
            
            # Update UI
            self.running = True
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text="Service running - SPACEBAR(IT→EN) | F2(EN→IT) [READY]")
            
            self.logger.info("Service started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            messagebox.showerror("Error", f"Failed to start service: {e}")
            
    def _stop_service(self):
        """Stop the voice interpretation service"""
        try:
            self.running = False
            
            # Stop recording if active
            if self.recording:
                self._stop_recording()
            
            # Stop Stream Deck
            self.stream_deck.stop()
            
            # Update UI
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.status_label.config(text="Service stopped")
            self.recording_indicator.config(foreground="gray")
            
            self.logger.info("Service stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}")
            
    def _update_config_from_gui(self):
        """Update configuration from GUI values"""
        self.config.whisper_model = self.model_var.get()
        self.config.whisper_language = None if self.language_var.get() == "auto" else self.language_var.get()
        self.config.enable_llm = self.llm_var.get()
        self.config.enable_deepl = self.deepl_var.get()
        self.config.enable_tts = self.tts_var.get()
        
        # Save configuration changes
        self.config_manager.config = self.config
        self.config_manager.save_config()
        
        # Update components with new config
        self.transcriber.update_model(self.config.whisper_model, self.config.whisper_language)
        self.text_processor.update_config(
            enable_llm=self.config.enable_llm,
            enable_deepl=self.config.enable_deepl,
            target_language=self.target_language_var.get()
        )
        self.tts_engine.enabled = self.config.enable_tts
        # Apply TTS voice/rate
        try:
            if self.tts_voice_var.get():
                self.tts_engine.set_voice(self.tts_voice_var.get())
            if self.tts_rate_var.get():
                self.tts_engine.set_rate(int(self.tts_rate_var.get()))
        except Exception:
            pass
    
    def _save_config_changes(self):
        """Save configuration changes immediately"""
        try:
            self.config.whisper_model = self.model_var.get()
            self.config.whisper_language = None if self.language_var.get() == "auto" else self.language_var.get()
            
            # Update config manager and save
            self.config_manager.config = self.config  
            self.config_manager.save_config()
            
            self.logger.info(f"Configuration saved: model={self.config.whisper_model}, lang={self.config.whisper_language}")
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
        
    def _on_button_press(self):
        """Handle Stream Deck button press - start recording"""
        if not self.running or self.recording:
            return
            
        try:
            # Stop any ongoing TTS to avoid echo in mic
            if hasattr(self, 'tts_engine'):
                try:
                    self.tts_engine.stop_speaking()
                except Exception:
                    pass

            self.recording = True
            self.recording_indicator.config(foreground="red")
            self.status_label.config(text="Recording... (release button to stop)")
            
            # Start audio recording
            self.audio_recorder.start_recording()
            self.logger.info("Recording started")
            
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self.recording = False
            self.recording_indicator.config(foreground="gray")
            
    def _on_button_release(self):
        """Handle Stream Deck button release - stop recording and process"""
        if not self.recording:
            return
            
        try:
            self.recording = False
            self.recording_indicator.config(foreground="orange")
            self.status_label.config(text="Processing...")
            
            # Stop recording and get audio file
            audio_file = self.audio_recorder.stop_recording()
            
            if audio_file:
                # Quick size-based gate to avoid sending near-empty clips
                try:
                    file_size = os.path.getsize(audio_file)
                    min_bytes = int(os.getenv('MIN_WAV_BYTES', '10000'))  # default ~0.31s @16kHz mono 16-bit
                    if file_size < min_bytes:
                        self.logger.warning(f"Audio file too small ({file_size} bytes), skipping transcription")
                        self.root.after(0, self._update_output, "(no speech detected)", "(no speech detected)")
                        self.root.after(0, self._reset_status)
                        return
                except Exception as e:
                    self.logger.debug(f"Could not stat audio file: {e}")

                # Process in background thread to avoid blocking GUI
                threading.Thread(target=self._process_audio, 
                               args=(audio_file,), daemon=True).start()
            else:
                self._reset_status()
                
        except Exception as e:
            self.logger.error(f"Failed to stop recording: {e}")
            self._reset_status()
            
    def _process_audio(self, audio_file: str):
        """Process the recorded audio file"""
        try:
            start_time = time.time()
            
            # Transcribe with Whisper
            self.logger.info("Starting transcription...")
            transcription = self.transcriber.transcribe(audio_file)
            
            # Additional guard against known hallucinated subtitles
            if transcription:
                tl = transcription.lower()
                if any(m in tl for m in ("qtss", "sottotitoli", "subtitles")):
                    self.logger.warning("Filtered hallucinated subtitle content in post-check")
                    transcription = ""

            if not transcription:
                self.logger.warning("Empty transcription result")
                self.root.after(0, self._update_output, "(no speech detected)", "(no speech detected)")
                self._reset_status()
                return
                
            self.logger.info(f"Transcription completed in {time.time() - start_time:.2f}s")
            
            # Process text with bidirectional translation
            if hasattr(self, 'current_translation_mode'):
                if self.current_translation_mode == 'it_to_en':
                    # Forward: Italian to selected target language
                    tgt = self.target_language_var.get() or 'en'
                    processed_text = self.text_processor.process_text(transcription, target_lang=tgt)
                    self.logger.info(f"Translation: Italian → {tgt}")
                elif self.current_translation_mode == 'en_to_it':
                    # Reverse: from selected target language back to Italian
                    processed_text = self.text_processor.process_text(transcription, target_lang='it')
                    self.logger.info("Translation: Target → Italian")
                else:
                    # Default fallback
                    processed_text = self.text_processor.process_text(transcription)
            else:
                # Default fallback
                processed_text = self.text_processor.process_text(transcription)
            
            # Add to conversation tracking
            translation_part = ""
            if "→" in processed_text:
                translation_part = processed_text.split("→", 1)[1].strip()
                # Remove service tags
                translation_part = translation_part.split("[")[0].strip()
            
            # Determine speaker based on translation direction
            speaker = "patient" if self.current_translation_mode == 'it_to_en' else "doctor"
            
            # Add to conversation
            self.session_manager.add_to_conversation(
                speaker=speaker,
                text=transcription,
                translation=translation_part if translation_part else None,
                translation_direction=self.current_translation_mode
            )
            
            # Update GUI with results
            self.root.after(0, self._update_output, transcription, processed_text)
            
            # TTS output - only speak the translation, not original
            if self.config.enable_tts and processed_text:
                # Extract just the translated part if it contains "→"
                if "→" in processed_text:
                    # Get text after the arrow (translated part)
                    translated_part = processed_text.split("→", 1)[1].strip()
                    # Remove service tags like [DeepL], [Google], [Local]
                    translated_part = translated_part.split("[")[0].strip()
                    self.tts_engine.speak(translated_part)
                else:
                    self.tts_engine.speak(processed_text)
            
            # Save to session
            if self.config.enable_persistence:
                self.session_manager.save_transcription(
                    original_text=transcription,
                    processed_text=processed_text,
                    audio_file=audio_file,
                    model=self.config.whisper_model,
                    processing_config={
                        'llm_enabled': self.config.enable_llm,
                        'deepl_enabled': self.config.enable_deepl
                    }
                )
            
            # Clean up temporary audio file
            try:
                os.unlink(audio_file)
            except OSError:
                pass
                
            self.root.after(0, self._reset_status)
            
        except Exception as e:
            self.logger.error(f"Failed to process audio: {e}")
            self.root.after(0, self._reset_status)
            
    def _on_manual_text_entry(self, event):
        """Handle manual text entry with Enter key"""
        if not self.running:
            return "break"
            
        # Get text from the widget
        text = self.output_text.get(1.0, tk.END).strip()
        if not text:
            return "break"
            
        self.logger.info(f"Manual text entry: '{text}'")
        
        # Process the text (translate it)
        try:
            # Determine translation direction based on current target language
            target_lang = self.target_language_var.get()
            translation_mode = 'it_to_en' if target_lang == 'en' else 'en_to_it'
            
            processed_text = self.text_processor.process_text(
                text, 
                target_lang=target_lang,
                translation_mode=translation_mode
            )
            
            # Add to conversation
            speaker = "patient" if translation_mode == 'it_to_en' else "doctor"
            self.session_manager.add_to_conversation(
                speaker=speaker,
                text=text,
                translation=processed_text,
                translation_direction=translation_mode
            )
            
            # Speak the result
            if self.config.enable_tts and processed_text != text:
                self.tts_engine.speak(processed_text)
                
            # Update display
            self._update_output(text, processed_text)
            
        except Exception as e:
            self.logger.error(f"Failed to process manual text: {e}")
            
        return "break"  # Prevent default Enter behavior
    
    def _update_output(self, original_text: str, processed_text: str):
        """Update the GUI output display"""
        self.logger.info(f"Updating GUI with: '{original_text}'")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Clear and update text widget
        self.output_text.delete(1.0, tk.END)
        
        output = f"[{timestamp}] Original: {original_text}\n"
        if processed_text != original_text:
            output += f"[{timestamp}] Processed: {processed_text}\n"
        
        self.output_text.insert(tk.END, output)
        self.output_text.see(tk.END)
        
        # Update DeepL usage counter
        self._update_usage_counter()
    
    def _update_usage_counter(self):
        """Update DeepL usage counter display"""
        try:
            stats = self.text_processor.get_usage_stats()
            chars_used = stats['characters_used']
            max_chars = stats['max_characters'] 
            percentage = stats['percentage_used']
            using_google = stats['using_google_fallback']
            
            if using_google:
                status_text = f"DeepL: LIMIT REACHED → Using Google"
                self.usage_label.config(text=status_text, foreground="red")
            elif percentage > 80:
                status_text = f"DeepL: {chars_used:,}/{max_chars:,} chars ({percentage:.1f}%)"
                self.usage_label.config(text=status_text, foreground="orange")
            else:
                status_text = f"DeepL: {chars_used:,}/{max_chars:,} chars ({percentage:.1f}%)"
                self.usage_label.config(text=status_text, foreground="green")
                
        except Exception as e:
            self.logger.warning(f"Could not update usage counter: {e}")
            self.usage_label.config(text="DeepL: Usage unavailable", foreground="gray")
        
    def _reset_status(self):
        """Reset UI status after processing"""
        self.recording_indicator.config(foreground="green")
        if self.running:
            self.status_label.config(text="Service running - SPACEBAR(IT→EN) | F2(EN→IT) [READY]")
        else:
            self.status_label.config(text="Service stopped")
        
        # Return to green after a short delay
        self.root.after(2000, lambda: self.recording_indicator.config(foreground="gray"))

    def _populate_input_devices(self):
        """Populate the input device combobox with available devices"""
        try:
            devices = self.audio_recorder.get_input_devices()
            values = [f"{d['index']}: {d['name']} (Ch:{d['channels']} {int(d['sample_rate'])}Hz)" for d in devices]
            self.input_device_combo['values'] = values
            if values:
                # Prefer env-selected index if present
                env_idx = os.getenv('AUDIO_INPUT_INDEX')
                selected = values[0]
                if env_idx is not None:
                    for d, v in zip(devices, values):
                        if str(d['index']) == str(env_idx):
                            selected = v
                            break
                self.input_device_var.set(selected)
        except Exception as e:
            self.logger.warning(f"Could not populate input devices: {e}")

    def _on_input_device_change(self):
        """Handle change of selected input device"""
        try:
            sel = self.input_device_var.get()
            idx = int(sel.split(':', 1)[0])
            self.audio_recorder.set_input_device(idx)
            # Persist selection to .env via ConfigManager
            self.config_manager.set_env_var('AUDIO_INPUT_INDEX', str(idx))
            self.logger.info(f"Audio input device set to index {idx}")
        except Exception as e:
            self.logger.error(f"Failed to set input device: {e}")

    def _on_input_gain_change(self, value):
        """Update recorder input gain when slider changes"""
        try:
            gain = float(value)
            self.audio_recorder.set_input_gain(gain)
            self.input_gain_value_label.config(text=f"x{gain:.2f}")
            # Persist to .env so it sticks next run
            self.config_manager.set_env_var('INPUT_GAIN', f"{gain:.2f}")
        except Exception as e:
            self.logger.warning(f"Failed to apply input gain: {e}")

    def _populate_tts_voices(self):
        """Populate the TTS voice list and select a sensible default"""
        try:
            backend = (self.tts_backend_var.get() or 'system').lower()
            names = []
            display_names = []
            if backend == 'piper':
                model_path = getattr(self.config, 'piper_model', None)
                if model_path and os.path.exists(model_path):
                    base = os.path.basename(model_path)
                    names = [base]
                    display_names = [f"Piper: {base}"]
                else:
                    names = []
                    display_names = []
            else:
                voices = self.tts_engine.get_voices() if hasattr(self, 'tts_engine') else []
                all_names = [v.get('name') for v in voices if v.get('name')]
                curated = {
                    'Samantha','Alex','Victoria','Daniel','Fiona','Karen',
                    'Alice','Federica',
                    'Thomas','Amelie','Marine',
                    'Anna','Markus','Petra','Steffi',
                    'Jorge','Monica','Paulina','Diego',
                    'Luciana','Joana',
                    'Ting-Ting','Mei-Jia','Li-mu',
                    'Maged','Tarik','Laila'
                }
                names = [n for n in all_names if n in curated]
                if not names:
                    names = all_names[:10]
                display_names = [f"System: {n}" for n in names]

            self.tts_voice_combo['values'] = display_names
            current = self.config.tts_voice
            if current and any(current in dn for dn in display_names):
                for dn in display_names:
                    if current in dn:
                        self.tts_voice_var.set(dn)
                        break
            elif display_names:
                self.tts_voice_var.set(display_names[0])
        except Exception as e:
            self.logger.warning(f"Could not populate TTS voices: {e}")

    def _on_tts_voice_change(self):
        """Apply selected TTS voice and persist"""
        try:
            backend = (self.tts_backend_var.get() or 'system').lower()
            sel = self.tts_voice_var.get() or ''
            voice = sel.replace('Piper: ', '').replace('System: ', '')
            if backend == 'piper':
                # Persist display-only voice name (model basename)
                self.config.tts_voice = voice
            else:
                if voice:
                    self.tts_engine.set_voice(voice)
                    self.config.tts_voice = voice
                    self.config_manager.set_env_var('TTS_VOICE', voice)
        except Exception as e:
            self.logger.warning(f"Failed to set TTS voice: {e}")

    def _on_tts_backend_change(self):
        try:
            backend = (self.tts_backend_var.get() or 'system').lower()
            self.config.tts_backend = backend
            self.config_manager.set_env_var('TTS_BACKEND', backend)
            self._reinit_tts_engine()
            self._update_tts_backend_ui()
            self._populate_tts_voices()
        except Exception as e:
            self.logger.warning(f"Failed to change TTS backend: {e}")

    def _update_tts_backend_ui(self):
        backend = (self.tts_backend_var.get() or 'system').lower()
        show_piper = backend == 'piper'
        try:
            if show_piper:
                model_path = getattr(self.config, 'piper_model', None)
                txt = f"Model: {os.path.basename(model_path)}" if model_path else "Model: (not set)"
                self.piper_model_label.config(text=txt)
                self.piper_model_label.grid()
                self.piper_model_button.grid()
            else:
                self.piper_model_label.grid_remove()
                self.piper_model_button.grid_remove()
        except Exception:
            pass

    def _select_piper_model(self):
        try:
            path = filedialog.askopenfilename(title="Select Piper Model", filetypes=[("Piper model", "*.onnx"), ("All files", "*.*")])
            if not path:
                return
            self.config.piper_model = path
            self.config_manager.set_env_var('PIPER_MODEL', path)
            self._reinit_tts_engine()
            self._update_tts_backend_ui()
            self._populate_tts_voices()
        except Exception as e:
            self.logger.error(f"Failed to set Piper model: {e}")

    def _reinit_tts_engine(self):
        try:
            if hasattr(self, 'tts_engine') and self.tts_engine:
                try:
                    self.tts_engine.cleanup()
                except Exception:
                    pass
            self.tts_engine = TTSEngine(
                enabled=self.config.enable_tts,
                voice=self.config.tts_voice,
                rate=self.config.tts_rate,
                backend=getattr(self.config, 'tts_backend', None),
                piper_path=getattr(self.config, 'piper_path', None),
                piper_model=getattr(self.config, 'piper_model', None),
            )
        except Exception as e:
            self.logger.error(f"Failed to reinitialize TTS engine: {e}")

    def _on_tts_rate_change(self, value):
        """Apply TTS rate updates and persist"""
        try:
            rate = int(float(value))
            self.tts_rate_value.config(text=f"{rate} WPM")
            self.tts_engine.set_rate(rate)
            self.config.tts_rate = rate
            self.config_manager.set_env_var('TTS_RATE', str(rate))
        except Exception as e:
            self.logger.warning(f"Failed to set TTS rate: {e}")

    def _schedule_vu_update(self):
        """Periodic UI update for the VU bar based on input level"""
        try:
            level = {'rms': 0.0}
            if hasattr(self, 'audio_recorder') and self.audio_recorder:
                level = self.audio_recorder.get_level()
            # Map RMS (0..1) to 0..100; apply simple curve to emphasize mid range
            rms = max(0.0, min(1.0, float(level.get('rms', 0.0))))
            # gamma curve for better UX
            gamma = 0.6
            vu_value = int((rms ** gamma) * 100)
            # If not recording, set to 0
            if not self.recording:
                vu_value = 0
            self.vu_bar['value'] = vu_value
        except Exception:
            pass
        finally:
            # Schedule next update
            self.root.after(80, self._schedule_vu_update)
    
    def _test_hotkeys(self):
        """Test hotkey functionality"""
        import tkinter.messagebox as mb
        
        msg = """Test dei controlli tastiera:

1. Clicca OK
2. Prova SPACEBAR (IT→EN) 
3. Prova F2 (EN→IT)

La text box è ora read-only quindi i tasti funzioneranno sempre!"""
        
        mb.showinfo("Test Hotkeys", msg)
        
        # Set focus to text box to test hotkeys work even when focused there
        self.output_text.focus_set()

    def _test_microphone(self, seconds: int = 2):
        """Record a short test clip and report stats (non-blocking)."""
        try:
            if self.recording:
                messagebox.showinfo("Recording Busy", "Recording already in progress. Please stop first.")
                return

            # Stop any ongoing TTS to avoid feedback
            if hasattr(self, 'tts_engine'):
                try:
                    self.tts_engine.stop_speaking()
                except Exception:
                    pass

            self.status_label.config(text=f"Testing mic... recording {seconds}s")
            self.recording_indicator.config(foreground="red")
            
            if not self.audio_recorder.start_recording():
                messagebox.showerror("Mic Test Failed", "Could not start audio recording. Check input device and permissions.")
                self._reset_status()
                return

            def finish_test():
                try:
                    audio_file = self.audio_recorder.stop_recording()
                    if not audio_file:
                        self.root.after(0, lambda: messagebox.showwarning("Mic Test", "No audio captured."))
                        return
                    
                    # Compute basic stats
                    try:
                        size = os.path.getsize(audio_file)
                    except Exception:
                        size = -1
                    approx_duration = 0.0
                    if size and size > 44:
                        approx_duration = max(0.0, (size - 44) / (self.config.sample_rate * self.config.channels * 2))
                    
                    def show_result():
                        kb = size/1024.0 if size >= 0 else 0
                        msg = f"File: {audio_file}\nSize: {kb:.1f} KB\nApprox duration: {approx_duration:.2f} s\nSample rate: {self.config.sample_rate} Hz, Channels: {self.config.channels}"
                        messagebox.showinfo("Mic Test Result", msg)
                        # Clean up temp file
                        try:
                            os.unlink(audio_file)
                        except Exception:
                            pass
                        self._reset_status()
                    
                    self.root.after(0, show_result)
                except Exception as e:
                    self.logger.error(f"Mic test failed: {e}")
                    self.root.after(0, lambda: messagebox.showerror("Mic Test Failed", str(e)))
                    self.root.after(0, self._reset_status)

            # Schedule stop after requested seconds without blocking UI
            self.root.after(int(seconds * 1000), lambda: threading.Thread(target=finish_test, daemon=True).start())
        except Exception as e:
            self.logger.error(f"Error during mic test: {e}")
            messagebox.showerror("Mic Test Error", str(e))
    
    def _review_conversation(self):
        """Review current conversation with LLM analysis"""
        if not self.llm_processor.is_available():
            messagebox.showwarning("LLM Not Available", 
                                 "LLM service not configured. Please set OPENAI_API_KEY in .env file.")
            return
            
        if not self.session_manager.current_conversation:
            messagebox.showinfo("No Conversation", 
                              "No conversation to analyze yet. Start recording some dialogue first.")
            return
            
        # Show processing dialog
        self.status_label.config(text="Analyzing conversation with AI...")
        self.root.update()
        
        # Get conversation summary and analyze
        conversation_summary = self.session_manager.get_conversation_summary()
        
        def analyze_in_background():
            try:
                result = self.llm_processor.review_conversation(conversation_summary)
                
                # Show results in GUI thread
                def show_results():
                    if result.get("success"):
                        self._show_llm_response("🔍 Analisi Conversazione", result["analysis"])
                    else:
                        messagebox.showerror("Analysis Error", f"Failed to analyze: {result.get('error', 'Unknown error')}")
                    
                    self._reset_status()
                
                self.root.after(0, show_results)
                
            except Exception as e:
                self.logger.error(f"Conversation analysis failed: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {str(e)}"))
                self.root.after(0, self._reset_status)
        
        # Run analysis in background thread
        threading.Thread(target=analyze_in_background, daemon=True).start()
    
    def _show_query_dialog(self):
        """Show dialog for direct LLM queries"""
        if not self.llm_processor.is_available():
            messagebox.showwarning("LLM Not Available", 
                                 "LLM service not configured. Please set OPENAI_API_KEY in .env file.")
            return
        
        # Create query dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("LLM Query - Ask AI Assistant")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Query input
        ttk.Label(dialog, text="Ask the AI assistant:", font=('TkDefaultFont', 10, 'bold')).pack(pady=(10, 5))
        
        query_text = tk.Text(dialog, height=4, wrap=tk.WORD)
        query_text.pack(fill=tk.BOTH, padx=10, pady=(0, 10))
        query_text.focus()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def submit_query():
            query = query_text.get("1.0", tk.END).strip()
            if not query:
                messagebox.showwarning("Empty Query", "Please enter a question.")
                return
                
            dialog.destroy()
            
            def process_query():
                try:
                    conversation_context = self.session_manager.get_conversation_summary()
                    result = self.llm_processor.process_query(query, conversation_context)
                    
                    def update_response():
                        if result.get("success"):
                            self._show_llm_response("💬 AI Response", result["response"])
                            
                            # Speak the response if TTS enabled
                            if self.config.enable_tts:
                                self.tts_engine.speak(result["response"])
                        else:
                            messagebox.showerror("Query Error", f"Error: {result.get('error', 'Unknown error')}")
                    
                    self.root.after(0, update_response)
                    
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Query failed: {str(e)}"))
            
            threading.Thread(target=process_query, daemon=True).start()
        
        ttk.Button(button_frame, text="Submit Query", command=submit_query).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def _show_llm_response(self, title: str, response: str):
        """Show LLM response in a dedicated window"""
        # Create response window
        response_window = tk.Toplevel(self.root)
        response_window.title(title)
        response_window.geometry("600x400")
        response_window.transient(self.root)
        
        # Response display
        response_text = tk.Text(response_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(response_window, orient="vertical", command=response_text.yview)
        response_text.configure(yscrollcommand=scrollbar.set)
        
        response_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        response_text.insert(tk.END, response)
        response_text.config(state=tk.DISABLED)
        
    def run(self):
        """Run the application"""
        try:
            self.logger.info("Starting Clinical Voice Interpreter GUI")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        finally:
            self._cleanup()
            
    def _cleanup(self):
        """Clean up resources"""
        try:
            if self.running:
                self._stop_service()
            
            # Clean up components
            if hasattr(self, 'stream_deck'):
                self.stream_deck.cleanup()
            if hasattr(self, 'audio_recorder'):
                self.audio_recorder.cleanup()
            if hasattr(self, 'transcriber'):
                self.transcriber.cleanup()
            if hasattr(self, 'tts_engine'):
                self.tts_engine.cleanup()
            if hasattr(self, 'session_manager'):
                self.session_manager.cleanup()
            if hasattr(self, 'llm_processor'):
                self.llm_processor.cleanup()
                
            self.logger.info("Application cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

def main():
    """Main entry point"""
    try:
        # Load configuration from environment/config file
        config = AppConfig()
        
        # Override with environment variables if present
        config.whisper_model = os.getenv('WHISPER_MODEL', config.whisper_model)
        config.whisper_language = os.getenv('WHISPER_LANGUAGE', config.whisper_language)
        config.enable_deepl = bool(os.getenv('DEEPL_API_KEY'))
        config.deepl_api_key = os.getenv('DEEPL_API_KEY')
        config.enable_llm = bool(os.getenv('LLM_ENDPOINT'))
        config.llm_endpoint = os.getenv('LLM_ENDPOINT')
        
        # Create and run application
        app = ClinicalVoiceInterpreter(config)
        app.run()
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
