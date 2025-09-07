#!/usr/bin/env python3
"""
Clinical Voice Interpreter - Setup Script
Automated setup and configuration for first-time installation
"""

import os
import sys
import platform
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

class ClinicalVoiceSetup:
    """Automated setup for Clinical Voice Interpreter"""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.python_version = sys.version_info
        self.setup_dir = Path(__file__).parent
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def run_setup(self):
        """Run complete setup process"""
        print("🎤 Clinical Voice Interpreter - Setup")
        print("=" * 50)
        
        try:
            # Check system requirements
            if not self.check_python_version():
                return False
                
            if not self.check_system_dependencies():
                return False
                
            # Install Python dependencies
            if not self.install_python_dependencies():
                return False
                
            # Setup configuration
            if not self.setup_configuration():
                return False
                
            # Create directories
            if not self.create_directories():
                return False
                
            # Test installation
            if not self.test_installation():
                return False
                
            print("\n✅ Setup completed successfully!")
            print("\nNext steps:")
            print("1. Connect your Stream Deck device")
            print("2. Configure your .env file with API keys (optional)")
            print("3. Run: python main.py")
            print("4. Click 'Start Service' and test with Stream Deck button")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            return False
            
    def check_python_version(self) -> bool:
        """Check Python version compatibility"""
        print("🐍 Checking Python version...")
        
        if self.python_version < (3, 8):
            print(f"❌ Python 3.8+ required, found {sys.version}")
            print("Please upgrade Python and try again.")
            return False
            
        print(f"✅ Python {sys.version.split()[0]} is compatible")
        return True
        
    def check_system_dependencies(self) -> bool:
        """Check platform-specific system dependencies"""
        print(f"🔧 Checking system dependencies for {self.platform}...")
        
        missing_deps = []
        
        if self.platform == "darwin":  # macOS
            missing_deps.extend(self.check_macos_dependencies())
        elif self.platform == "windows":  # Windows
            missing_deps.extend(self.check_windows_dependencies())
        elif self.platform == "linux":  # Linux
            missing_deps.extend(self.check_linux_dependencies())
        else:
            print(f"⚠️  Platform {self.platform} not officially supported")
            
        if missing_deps:
            print("❌ Missing system dependencies:")
            for dep in missing_deps:
                print(f"   - {dep}")
            print("\nPlease install missing dependencies and try again.")
            return False
            
        print("✅ System dependencies OK")
        return True
        
    def check_macos_dependencies(self) -> List[str]:
        """Check macOS-specific dependencies"""
        missing = []
        
        # Check for FFmpeg
        if not self.command_exists("ffmpeg"):
            missing.append("FFmpeg (install with: brew install ffmpeg)")
            
        # Check for PortAudio (needed for PyAudio)
        if not self.command_exists("pkg-config"):
            missing.append("pkg-config (install with: brew install pkg-config)")
            
        # Check if brew is available for easy installation
        if missing and not self.command_exists("brew"):
            missing.append("Homebrew (install from: https://brew.sh)")
            
        return missing
        
    def check_windows_dependencies(self) -> List[str]:
        """Check Windows-specific dependencies"""
        missing = []
        
        # Check for FFmpeg
        if not self.command_exists("ffmpeg"):
            missing.append("FFmpeg (download from: https://ffmpeg.org/download.html)")
            
        # Note: Visual C++ Build Tools check is complex, will be caught during pip install
        
        return missing
        
    def check_linux_dependencies(self) -> List[str]:
        """Check Linux-specific dependencies"""
        missing = []
        
        # Check for FFmpeg
        if not self.command_exists("ffmpeg"):
            missing.append("FFmpeg (install with: sudo apt-get install ffmpeg)")
            
        # Check for espeak
        if not self.command_exists("espeak"):
            missing.append("espeak (install with: sudo apt-get install espeak)")
            
        # Check for PortAudio development files
        portaudio_paths = [
            "/usr/include/portaudio.h",
            "/usr/local/include/portaudio.h"
        ]
        if not any(Path(p).exists() for p in portaudio_paths):
            missing.append("portaudio19-dev (install with: sudo apt-get install portaudio19-dev)")
            
        return missing
        
    def command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, 
                         check=True, 
                         timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
            
    def install_python_dependencies(self) -> bool:
        """Install Python dependencies"""
        print("📦 Installing Python dependencies...")
        
        try:
            # Upgrade pip first
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                         check=True)
            
            # Install core requirements
            requirements_file = self.setup_dir / "requirements.txt"
            if requirements_file.exists():
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], 
                             check=True)
            else:
                # Install core dependencies manually
                core_deps = [
                    "streamdeck>=0.9.5",
                    "Pillow>=9.0.0", 
                    "pyaudio>=0.2.11",
                    "openai-whisper>=20231117",
                    "python-dotenv>=1.0.0",
                    "openai>=1.0.0",
                    "deepl>=1.12.0"
                ]
                
                for dep in core_deps:
                    print(f"Installing {dep}...")
                    subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                                 check=True)
                    
            # Install platform-specific dependencies
            if self.platform == "windows":
                print("Installing Windows TTS support...")
                subprocess.run([sys.executable, "-m", "pip", "install", "pyttsx3>=2.90"], 
                             check=True)
                             
            print("✅ Python dependencies installed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            
            # Provide troubleshooting hints
            if "pyaudio" in str(e).lower():
                print("\n💡 PyAudio installation failed. Try:")
                if self.platform == "darwin":
                    print("   brew install portaudio")
                elif self.platform == "windows":
                    print("   Install Visual C++ Build Tools")
                elif self.platform == "linux":
                    print("   sudo apt-get install portaudio19-dev python3-dev")
                    
            return False
            
    def setup_configuration(self) -> bool:
        """Setup configuration files"""
        print("⚙️  Setting up configuration...")
        
        try:
            # Create .env file from sample if it doesn't exist
            env_file = self.setup_dir / ".env"
            env_sample = self.setup_dir / ".env.sample"
            
            if not env_file.exists():
                if env_sample.exists():
                    # Copy sample to .env
                    with open(env_sample, 'r') as src, open(env_file, 'w') as dst:
                        dst.write(src.read())
                    print(f"✅ Created .env from sample")
                else:
                    # Create basic .env file
                    env_content = """# Clinical Voice Interpreter Configuration
WHISPER_MODEL=small
DECK_BUTTON_INDEX=0
ENABLE_TTS=true
OUTPUT_DIR=./output
ENABLE_PERSISTENCE=true
PRIVACY_MODE=true
CONSENT_LLM=false
CONSENT_DEEPL=false
"""
                    with open(env_file, 'w') as f:
                        f.write(env_content)
                    print("✅ Created basic .env file")
            else:
                print("✅ .env file already exists")
                
            # Create initial config.json
            config_file = self.setup_dir / "clinical_voice_config.json"
            if not config_file.exists():
                config_content = {
                    "whisper_model": "small",
                    "deck_button_index": 0,
                    "enable_tts": True,
                    "enable_persistence": True,
                    "privacy_mode": True
                }
                
                import json
                with open(config_file, 'w') as f:
                    json.dump(config_content, f, indent=2)
                print("✅ Created initial configuration")
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup configuration: {e}")
            return False
            
    def create_directories(self) -> bool:
        """Create necessary directories"""
        print("📁 Creating directories...")
        
        try:
            directories = [
                "output",
                "output/sessions", 
                "output/transcriptions",
                "output/exports"
            ]
            
            for dir_name in directories:
                dir_path = self.setup_dir / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)
                
            print("✅ Directories created")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create directories: {e}")
            return False
            
    def test_installation(self) -> bool:
        """Test the installation"""
        print("🧪 Testing installation...")
        
        tests_passed = 0
        total_tests = 4
        
        # Test 1: Import core modules
        try:
            import streamdeck
            import whisper
            import pyaudio
            from PIL import Image
            print("✅ Core modules import OK")
            tests_passed += 1
        except ImportError as e:
            print(f"❌ Core module import failed: {e}")
            
        # Test 2: Test audio system
        try:
            p = pyaudio.PyAudio()
            device_count = p.get_device_count()
            p.terminate()
            print(f"✅ Audio system OK ({device_count} devices found)")
            tests_passed += 1
        except Exception as e:
            print(f"❌ Audio system test failed: {e}")
            
        # Test 3: Test Whisper model download
        try:
            print("   Downloading Whisper 'tiny' model for testing...")
            model = whisper.load_model("tiny")
            print("✅ Whisper model test OK")
            tests_passed += 1
        except Exception as e:
            print(f"❌ Whisper model test failed: {e}")
            
        # Test 4: Test Stream Deck detection
        try:
            from StreamDeck.DeviceManager import DeviceManager
            streamdecks = DeviceManager().enumerate()
            if streamdecks:
                print(f"✅ Stream Deck detected ({len(streamdecks)} device(s))")
            else:
                print("⚠️  No Stream Deck detected (connect device and try again)")
            tests_passed += 1
        except Exception as e:
            print(f"❌ Stream Deck test failed: {e}")
            
        print(f"\n📊 Tests passed: {tests_passed}/{total_tests}")
        
        if tests_passed >= 3:  # Allow Stream Deck test to fail
            print("✅ Installation test passed")
            return True
        else:
            print("❌ Installation test failed")
            return False
            
    def print_troubleshooting_guide(self):
        """Print troubleshooting information"""
        print("\n🔧 Troubleshooting Guide")
        print("=" * 30)
        
        print("\nCommon Issues:")
        
        print("\n1. PyAudio installation fails:")
        if self.platform == "darwin":
            print("   Solution: brew install portaudio")
        elif self.platform == "windows":
            print("   Solution: Install Visual C++ Build Tools")
            print("   Alternative: pip install pipwin && pipwin install pyaudio")
        elif self.platform == "linux":
            print("   Solution: sudo apt-get install portaudio19-dev python3-dev")
            
        print("\n2. Stream Deck not detected:")
        print("   - Ensure device is connected via USB")
        print("   - Try different USB port")
        if self.platform == "linux":
            print("   - Check udev rules (see README)")
        print("   - Install Elgato Stream Deck software (optional)")
        
        print("\n3. Whisper model download slow/fails:")
        print("   - Ensure stable internet connection")
        print("   - Check available disk space (~1GB for models)")
        print("   - Try smaller model: WHISPER_MODEL=tiny")
        
        print("\n4. Audio permissions:")
        if self.platform == "darwin":
            print("   - Check System Settings > Privacy & Security > Microphone")
        elif self.platform == "windows":
            print("   - Check Settings > Privacy > Microphone")
        elif self.platform == "linux":
            print("   - Add user to audio group: sudo usermod -a -G audio $USER")
            
        print(f"\nFor more help, see README.md or create an issue on GitHub")

def main():
    """Main setup function"""
    setup = ClinicalVoiceSetup()
    
    # Check if running with admin privileges on Windows
    if setup.platform == "windows":
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("⚠️  Consider running as Administrator for best compatibility")
        except:
            pass
            
    success = setup.run_setup()
    
    if not success:
        print("\n❌ Setup failed!")
        setup.print_troubleshooting_guide()
        sys.exit(1)
    else:
        print("\n🎉 Setup completed successfully!")
        
        # Ask if user wants to run the application
        try:
            response = input("\nWould you like to start the application now? (y/n): ")
            if response.lower() in ['y', 'yes']:
                print("Starting Clinical Voice Interpreter...")
                subprocess.run([sys.executable, "main.py"])
        except KeyboardInterrupt:
            print("\nGoodbye!")

if __name__ == "__main__":
    main()