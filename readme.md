# Clinical Voice Interpreter

A privacy-first, push-to-talk voice transcription system designed for clinical environments. Features local Whisper transcription, Stream Deck integration, extensible text processing, and cross-platform TTS support.

## 🎯 Features

- **Privacy-First**: Local processing by default, no cloud data without explicit consent
- **Stream Deck Integration**: Physical push-to-talk control with visual feedback
- **Local Whisper**: Multiple model sizes (tiny/base/small/medium/large-v3)
- **Extensible Processing**: Hook for LLM refinement, DeepL translation, or custom processing
- **Cross-Platform TTS**: macOS `say`, Windows SAPI/pyttsx3, Linux espeak
- **Session Management**: Local persistence with .txt and .json outputs
- **Real-time Performance**: 2-3 second transcription with Whisper 'small' on M2

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Stream Deck   │───▶│  Audio Recorder  │───▶│ Whisper (Local) │
│ Button Control  │    │   (16kHz/Mono)   │    │  Transcription  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐             │
│   TTS Engine    │◀───│ Text Processor   │◀────────────┘
│ (Cross-platform)│    │ (LLM/DeepL/Pass) │
└─────────────────┘    └──────────────────┘
                                │
                        ┌──────────────────┐
                        │ Session Manager  │
                        │ (Local Storage)  │
                        └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Stream Deck device
- Microphone access
- FFmpeg (for audio processing)

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd clinical-voice-interpreter
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install Dependencies**
   ```bash
   # Core dependencies
   pip install streamdeck pillow pyaudio whisper python-dotenv

   # Platform-specific TTS
   # Windows: pip install pyttsx3
   # macOS/Linux: TTS is built-in

   # Optional: Text processing
   pip install openai deepl
   ```

3. **Setup Configuration**
   ```bash
   # Copy sample configuration
   cp .env.sample .env
   
   # Edit .env with your preferences
   nano .env
   ```

4. **Run Application**
   ```bash
   python main.py
   ```

## 📋 Detailed Setup Instructions

### macOS Setup

1. **Install Python Dependencies**
   ```bash
   # Using pip
   pip install -r requirements.txt

   # Or using brew + pip
   brew install python@3.11 ffmpeg portaudio
   pip install pyaudio whisper streamdeck
   ```

2. **Grant Microphone Permissions**
   - System Settings > Privacy & Security > Microphone
   - Add Terminal/Python to allowed applications

3. **Install Stream Deck Software (Optional)**
   - Download from Elgato website for device configuration
   - Not required for basic functionality

4. **Test Audio Input**
   ```bash
   python -c "import pyaudio; print('PyAudio available')"
   ```

### Windows Setup

1. **Install Python and Dependencies**
   ```bash
   # Install Python 3.8+ from python.org
   # Install Visual C++ Build Tools (for PyAudio)
   
   pip install -r requirements.txt
   pip install pyttsx3  # Windows TTS
   ```

2. **Install FFmpeg**
   - Download from https://ffmpeg.org/download.html
   - Add to system PATH
   - Or use: `winget install FFmpeg`

3. **Grant Microphone Permissions**
   - Settings > Privacy > Microphone
   - Allow desktop apps to access microphone

4. **Stream Deck Drivers**
   - Install Elgato Stream Deck software
   - Connect device and verify recognition

### Linux Setup

1. **Install System Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3-pip python3-venv ffmpeg portaudio19-dev espeak

   # Arch Linux
   sudo pacman -S python-pip ffmpeg portaudio espeak

   # CentOS/RHEL
   sudo yum install python3-pip ffmpeg-devel portaudio-devel espeak
   ```

2. **Install Python Dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Setup Audio Permissions**
   ```bash
   # Add user to audio group
   sudo usermod -a -G audio $USER
   
   # May require logout/login
   ```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Whisper Configuration
WHISPER_MODEL=small                    # tiny/base/small/medium/large-v3
WHISPER_LANGUAGE=auto                  # auto/en/it/es/fr/de

# Stream Deck Configuration  
DECK_BUTTON_INDEX=0                    # Button index (0-based)

# Text Processing (Optional)
LLM_ENDPOINT=http://localhost:11434    # Local LLM endpoint
OPENAI_API_KEY=your_key_here          # OpenAI API key
DEEPL_API_KEY=your_key_here           # DeepL API key
DEEPL_TARGET_LANG=EN-US               # Translation target

# TTS Configuration
ENABLE_TTS=true                       # Enable text-to-speech
TTS_VOICE=Alex                        # Voice name (system-specific)
TTS_RATE=200                          # Speech rate (WPM)

# Storage Configuration
OUTPUT_DIR=./output                   # Output directory
ENABLE_PERSISTENCE=true               # Save transcriptions

# Privacy Configuration
PRIVACY_MODE=true                     # Require explicit consent
CONSENT_LLM=false                     # Allow LLM processing
CONSENT_DEEPL=false                   # Allow DeepL translation
```

### GUI Configuration

The application provides a minimal GUI for runtime configuration:

- **Whisper Model Selection**: Choose model size vs. speed tradeoff
- **Language Selection**: Set transcription language or auto-detect
- **Text Processing Toggles**: Enable/disable LLM and DeepL
- **TTS Control**: Toggle text-to-speech output

## 🎤 Usage

### Basic Operation

1. **Start Service**: Click "Start Service" in GUI
2. **Record**: Press and hold configured Stream Deck button
3. **Release**: Release button to stop recording and process
4. **View Results**: Transcription appears in GUI output panel

### Stream Deck Visual Feedback

- **Gray Circle**: Service ready
- **Red Circle**: Recording active
- **Orange Circle**: Processing transcription
- **Green Circle**: Processing complete

### Text Processing Pipeline

1. **Whisper Transcription**: Local or API-based speech-to-text
2. **Text Processing Hook**: `process_text(original_text)` function
   - **Pass-through**: Return text unchanged
   - **LLM Processing**: Refine/reformat with language model
   - **DeepL Translation**: Translate to target language
   - **Custom Processing**: User-defined text transformations

3. **TTS Output**: Speak processed text (optional)
4. **Local Storage**: Save to `./output/` with timestamp

## 🔧 Advanced Configuration

### Custom Text Processors

Create custom text processing functions:

```python
from src.text_processor import TextProcessor

def clinical_abbreviation_expander(text: str) -> str:
    """Expand clinical abbreviations"""
    abbreviations = {
        'pt': 'patient',
        'hx': 'history',
        'dx': 'diagnosis',
        'bp': 'blood pressure'
    }
    
    for abbrev, full in abbreviations.items():
        text = text.replace(f' {abbrev} ', f' {full} ')
    return text

# Set custom processor
text_processor = TextProcessor()
text_processor.set_custom_processor(clinical_abbreviation_expander)
```

### Local LLM Integration

For local LLM processing (e.g., Ollama):

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama2

# Set endpoint in .env
LLM_ENDPOINT=http://localhost:11434/api/generate
CONSENT_LLM=true
```

### Multiple Stream Deck Buttons

Configure multiple buttons for different functions:

```python
# In config
DECK_BUTTON_INDEX=0  # Primary recording
# Additional buttons can be configured for:
# - Emergency recording (button 1)
# - Translation mode (button 2)  
# - Quick notes (button 3)
```

## 📁 Output Structure

```
output/
├── sessions/
│   └── session_20241206_143022_abc123def/
├── transcriptions/
│   ├── trans_20241206_143045_123.json
│   ├── trans_20241206_143045_123.txt
│   └── ...
├── exports/
│   ├── session_export_20241206.json
│   └── session_export_20241206.txt
└── index.json
```

### Data Formats

**JSON Output** (`transcription_id.json`):
```json
{
  "transcription_id": "trans_20241206_143045_123",
  "timestamp": "2024-12-06T14:30:45.123456",
  "original_text": "Patient presents with chest pain",
  "processed_text": "Patient presents with chest pain",
  "whisper_model": "small",
  "processing_config": {
    "llm_enabled": false,
    "deepl_enabled": false
  },
  "audio_metadata": {
    "duration_seconds": 3.2,
    "file_size_bytes": 102400
  },
  "privacy_info": {
    "stored_locally": true,
    "cloud_services_used": [],
    "data_retention": "indefinite_local"
  }
}
```

**Text Output** (`transcription_id.txt`):
```
Timestamp: 2024-12-06 14:30:45
Model: small
Processing: {'llm_enabled': False, 'deepl_enabled': False}
Duration: 3.2s
--------------------------------------------------
Original: Patient presents with chest pain
```

## 🔒 Privacy & Security

### Privacy-First Design

- **Local Processing**: Whisper runs locally by default
- **No Cloud by Default**: External APIs require explicit consent
- **Consent Management**: Environment flags for each external service
- **Local Storage Only**: All data stored in `./output/` directory
- **No Telemetry**: No usage data sent anywhere

### Data Retention

- **Local Files**: Indefinite retention under user control
- **Cleanup Tools**: Built-in functions to remove old data
- **Export Functions**: JSON, CSV, and text export for data portability

### External Service Usage

| Service | Purpose | Privacy Impact | Consent Required |
|---------|---------|----------------|------------------|
| OpenAI Whisper API | Transcription fallback | Audio sent to OpenAI | Yes |
| Local Whisper | Primary transcription | Fully local | No |
| OpenAI GPT | Text refinement | Text sent to OpenAI | Yes |
| DeepL API | Translation | Text sent to DeepL | Yes |
| Custom LLM | Text processing | Depends on endpoint | Yes |

## 🚨 Troubleshooting

### Common Issues

**Stream Deck Not Detected**
```bash
# Check USB connection
lsusb  # Linux
system_profiler SPUSBDataType  # macOS

# Verify permissions
sudo chmod 666 /dev/hidraw*  # Linux

# Install drivers
# Download from Elgato website
```

**PyAudio Installation Fails**
```bash
# macOS
brew install portaudio
pip install pyaudio

# Windows
# Install Visual C++ Build Tools
pip install pipwin
pipwin install pyaudio

# Linux
sudo apt-get install portaudio19-dev
pip install pyaudio
```

**Whisper Model Download Issues**
```bash
# Manual download
python -c "import whisper; whisper.load_model('small')"

# Check disk space (models are large)
du -sh ~/.cache/whisper/

# Clear cache if needed
rm -rf ~/.cache/whisper/
```

**Audio Input Not Working**
```bash
# Test microphone
python -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]}')
"

# Check permissions (macOS)
# System Settings > Privacy & Security > Microphone
```

**TTS Not Working**

*macOS:*
```bash
# Test say command
say "Hello world"

# Check available voices
say -v ?
```

*Windows:*
```bash
# Test pyttsx3
python -c "
import pyttsx3
engine = pyttsx3.init()
engine.say('Hello world')
engine.runAndWait()
"
```

*Linux:*
```bash
# Test espeak
espeak "Hello world"

# Install if missing
sudo apt-get install espeak
```

### Performance Optimization

**Whisper Model Selection**
- `tiny`: Fastest, lowest quality (~32x realtime on M2)
- `base`: Fast, acceptable quality (~16x realtime on M2)  
- `small`: **Recommended balance** (~6x realtime on M2)
- `medium`: Better quality, slower (~3x realtime on M2)
- `large-v3`: Best quality, slowest (~1x realtime on M2)

**Audio Settings Optimization**
```bash
# Optimal for speech recognition
SAMPLE_RATE=16000
CHANNELS=1
CHUNK_SIZE=1024
```

**Memory Usage**
- `tiny`: ~39 MB VRAM
- `base`: ~74 MB VRAM
- `small`: ~244 MB VRAM
- `medium`: ~769 MB VRAM
- `large-v3`: ~1550 MB VRAM

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd clinical-voice-interpreter

# Create development environment
python -m venv venv-dev
source venv-dev/bin/activate

# Install with development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Code formatting
black src/
flake8 src/
```

### Adding Custom Processors

1. Create processor function in `src/text_processor.py`
2. Add configuration options to `config_manager.py`
3. Update GUI controls in `main.py`
4. Add tests in `tests/test_text_processor.py`
5. Update documentation

### Architecture Notes

- **Modular Design**: Each component is independently testable
- **Threading**: Audio recording and TTS run in separate threads
- **Error Handling**: Graceful degradation when components fail
- **Configuration**: Environment-first configuration with GUI overrides

## 📄 License

[Specify your license here]

## 🙏 Acknowledgments

- Base project inspiration: [yixin0829/push-to-talk](https://github.com/yixin0829/push-to-talk)
- Stream Deck integration: [python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck)
- OpenAI Whisper for speech recognition
- Elgato for Stream Deck hardware

## 📞 Support

For issues and questions:

1. Check troubleshooting section above
2. Review [GitHub Issues](repository-url/issues)
3. Create new issue with:
   - Operating system and version
   - Python version
   - Complete error logs
   - Configuration (without API keys)
   - Steps to reproduce

---

*Privacy-first voice transcription for clinical environments*