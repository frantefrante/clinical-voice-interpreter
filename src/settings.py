import tkinter as tk
from tkinter import ttk, filedialog


class SettingsWindow:
    def __init__(self, app: "ClinicalVoiceInterpreter"):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Settings")
        self.win.geometry("640x520")
        self.win.transient(app.root)
        self.win.grab_set()

        nb = ttk.Notebook(self.win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Audio tab
        audio = ttk.Frame(nb)
        nb.add(audio, text="Audio")

        # Input device
        ttk.Label(audio, text="Input Device").grid(row=0, column=0, sticky=tk.W, pady=(5, 2))
        self.device_var = tk.StringVar(value="")
        self.device_combo = ttk.Combobox(audio, textvariable=self.device_var, state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, sticky=tk.W, pady=(5, 2))
        self.device_combo.bind('<<ComboboxSelected>>', self._on_device_change)
        self._populate_devices()

        # Input gain
        ttk.Label(audio, text="Input Gain").grid(row=1, column=0, sticky=tk.W, pady=(10, 2))
        gain = ttk.Scale(audio, from_=0.5, to=3.0, orient='horizontal', length=250,
                         command=lambda v: self.app._on_input_gain_change(v))
        gain.set(self.app.input_gain_var.get())
        gain.grid(row=1, column=1, sticky=tk.W)

        # Whisper tab
        whisper = ttk.Frame(nb)
        nb.add(whisper, text="Whisper")

        ttk.Label(whisper, text="Model").grid(row=0, column=0, sticky=tk.W, pady=(5, 2))
        self.model_var = tk.StringVar(value=self.app.model_var.get())
        model_combo = ttk.Combobox(whisper, textvariable=self.model_var, values=["tiny","base","small","medium","large-v3"], state="readonly", width=20)
        model_combo.grid(row=0, column=1, sticky=tk.W, pady=(5, 2))
        model_combo.bind('<<ComboboxSelected>>', self._on_whisper_model_change)

        # TTS tab
        tts = ttk.Frame(nb)
        nb.add(tts, text="TTS")

        ttk.Label(tts, text="Backend").grid(row=0, column=0, sticky=tk.W, pady=(5, 2))
        self.tts_backend_var = tk.StringVar(value=self.app.tts_backend_var.get())
        backend_combo = ttk.Combobox(tts, textvariable=self.tts_backend_var, values=["system","piper"], state="readonly", width=20)
        backend_combo.grid(row=0, column=1, sticky=tk.W)
        backend_combo.bind('<<ComboboxSelected>>', self._on_backend_change)

        # Piper model controls
        self.piper_model_label = ttk.Label(tts, text="Model: (not set)")
        self.piper_model_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8,2))
        ttk.Button(tts, text="Select Piper Model...", command=self._select_piper_model).grid(row=2, column=0, sticky=tk.W)
        ttk.Button(tts, text="Select Models Folder...", command=self._select_piper_models_folder).grid(row=2, column=1, sticky=tk.W)
        self._refresh_piper_label()

        ttk.Label(tts, text="Speech Rate").grid(row=3, column=0, sticky=tk.W, pady=(10, 2))
        rate_scale = ttk.Scale(tts, from_=120, to=240, orient='horizontal', length=250,
                               command=lambda v: self.app._on_tts_rate_change(v))
        rate_scale.set(self.app.tts_rate_var.get())
        rate_scale.grid(row=3, column=1, sticky=tk.W)

        # Close button
        btns = ttk.Frame(self.win)
        btns.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btns, text="Close", command=self.win.destroy).pack(side=tk.RIGHT)

    def _populate_devices(self):
        try:
            devices = self.app.audio_recorder.get_input_devices()
            values = [f"{d['index']}: {d['name']} (Ch:{d['channels']} {int(d['sample_rate'])}Hz)" for d in devices]
            self.device_combo['values'] = values
            if values:
                self.device_var.set(values[0])
        except Exception:
            pass

    def _on_device_change(self, _):
        try:
            sel = self.device_var.get()
            idx = int(sel.split(':', 1)[0])
            self.app.audio_recorder.set_input_device(idx)
            self.app.config_manager.set_env_var('AUDIO_INPUT_INDEX', str(idx))
        except Exception:
            pass

    def _on_whisper_model_change(self, _):
        try:
            m = self.model_var.get()
            self.app.model_var.set(m)
            self.app._save_config_changes()
        except Exception:
            pass

    def _on_backend_change(self, _):
        try:
            self.app.tts_backend_var.set(self.tts_backend_var.get())
            self.app._on_tts_backend_change()
            self._refresh_piper_label()
        except Exception:
            pass

    def _refresh_piper_label(self):
        try:
            model_path = getattr(self.app.config, 'piper_model', None)
            txt = f"Model: {model_path}" if model_path else "Model: (not set)"
            self.piper_model_label.config(text=txt)
        except Exception:
            pass

    def _select_piper_model(self):
        self.app._select_piper_model()
        self._refresh_piper_label()

    def _select_piper_models_folder(self):
        self.app._select_piper_models_folder()
        self._refresh_piper_label()

