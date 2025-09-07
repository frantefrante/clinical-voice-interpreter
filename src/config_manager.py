"""
Configuration Manager for Clinical Voice Interpreter
Handles .env files and configuration persistence
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv, set_key

@dataclass
class ClinicalVoiceConfig:
    """Configuration data class with defaults"""
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    
    # Whisper settings  
    whisper_model: str = "small"  # "medium" causes errors: Linear(in_features=1024) on some Macs
    whisper_language: Optional[str] = "it"
    
    # Stream Deck settings
    deck_button_index: int = 0
    
    # Text processing
    enable_llm: bool = False
    llm_endpoint: Optional[str] = None
    enable_deepl: bool = False
    deepl_api_key: Optional[str] = None
    deepl_target_lang: str = "EN-US"
    
    # TTS settings
    enable_tts: bool = True
    tts_voice: Optional[str] = None
    tts_rate: int = 200
    # TTS backend: 'system' (default) or 'piper'
    tts_backend: Optional[str] = None
    # Piper TTS settings
    piper_path: Optional[str] = None
    piper_model: Optional[str] = None
    piper_models_dir: Optional[str] = None
    
    # Storage settings
    output_dir: str = "./output"
    enable_persistence: bool = True
    
    # Privacy settings
    privacy_mode: bool = True
    
    # API keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Consent flags for external services
    consent_llm: bool = False
    consent_deepl: bool = False

class ConfigManager:
    """
    Manages configuration loading, saving, and environment integration
    """
    
    def __init__(self, config_file: str = "clinical_voice_config.json", 
                 env_file: str = ".env"):
        self.config_file = Path(config_file)
        self.env_file = Path(env_file)
        
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables first
        self._load_env()
        
        # Load or create configuration
        self.config = self._load_config()
        
    def _load_env(self):
        """Load environment variables from .env file"""
        try:
            if self.env_file.exists():
                load_dotenv(self.env_file)
                self.logger.info(f"Environment loaded from: {self.env_file}")
            else:
                self.logger.info("No .env file found, using system environment")
                
        except Exception as e:
            self.logger.error(f"Failed to load environment: {e}")
            
    def _load_config(self) -> ClinicalVoiceConfig:
        """Load configuration from file and environment"""
        try:
            # Start with defaults
            config_dict = asdict(ClinicalVoiceConfig())
            
            # Override with saved config file
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    config_dict.update(saved_config)
                    
            # Override with environment variables
            config_dict.update(self._get_env_overrides())
            
            # Create config object
            config = ClinicalVoiceConfig(**config_dict)
            
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Return defaults on error
            return ClinicalVoiceConfig()
            
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables"""
        env_overrides = {}
        
        # Audio settings
        if os.getenv('SAMPLE_RATE'):
            try:
                env_overrides['sample_rate'] = int(os.getenv('SAMPLE_RATE'))
            except ValueError:
                self.logger.warning(f"Invalid SAMPLE_RATE: {os.getenv('SAMPLE_RATE')}")
                
        if os.getenv('CHANNELS'):
            try:
                env_overrides['channels'] = int(os.getenv('CHANNELS'))
            except ValueError:
                self.logger.warning(f"Invalid CHANNELS: {os.getenv('CHANNELS')}")
                
        if os.getenv('CHUNK_SIZE'):
            try:
                env_overrides['chunk_size'] = int(os.getenv('CHUNK_SIZE'))
            except ValueError:
                self.logger.warning(f"Invalid CHUNK_SIZE: {os.getenv('CHUNK_SIZE')}")
                
        # Whisper settings
        if os.getenv('WHISPER_MODEL'):
            env_overrides['whisper_model'] = os.getenv('WHISPER_MODEL')
            
        if os.getenv('WHISPER_LANGUAGE'):
            env_overrides['whisper_language'] = os.getenv('WHISPER_LANGUAGE')
            
        # Stream Deck settings
        if os.getenv('DECK_BUTTON_INDEX'):
            try:
                env_overrides['deck_button_index'] = int(os.getenv('DECK_BUTTON_INDEX'))
            except ValueError:
                self.logger.warning(f"Invalid DECK_BUTTON_INDEX: {os.getenv('DECK_BUTTON_INDEX')}")
                
        # Text processing
        if os.getenv('LLM_ENDPOINT'):
            env_overrides['llm_endpoint'] = os.getenv('LLM_ENDPOINT')
            env_overrides['enable_llm'] = True
            
        if os.getenv('DEEPL_API_KEY'):
            env_overrides['deepl_api_key'] = os.getenv('DEEPL_API_KEY')
            env_overrides['enable_deepl'] = True
            
        if os.getenv('DEEPL_TARGET_LANG'):
            env_overrides['deepl_target_lang'] = os.getenv('DEEPL_TARGET_LANG')
            
        # TTS settings
        if os.getenv('ENABLE_TTS'):
            env_overrides['enable_tts'] = os.getenv('ENABLE_TTS').lower() in ['true', '1', 'yes']
        
        if os.getenv('TTS_VOICE'):
            env_overrides['tts_voice'] = os.getenv('TTS_VOICE')
        
        if os.getenv('TTS_RATE'):
            try:
                env_overrides['tts_rate'] = int(os.getenv('TTS_RATE'))
            except ValueError:
                self.logger.warning(f"Invalid TTS_RATE: {os.getenv('TTS_RATE')}")
        
        if os.getenv('TTS_BACKEND'):
            env_overrides['tts_backend'] = os.getenv('TTS_BACKEND').lower()
        
        # Piper specific
        if os.getenv('PIPER_PATH'):
            env_overrides['piper_path'] = os.getenv('PIPER_PATH')
        if os.getenv('PIPER_MODEL'):
            env_overrides['piper_model'] = os.getenv('PIPER_MODEL')
        if os.getenv('PIPER_MODELS_DIR'):
            env_overrides['piper_models_dir'] = os.getenv('PIPER_MODELS_DIR')
                
        # Storage settings
        if os.getenv('OUTPUT_DIR'):
            env_overrides['output_dir'] = os.getenv('OUTPUT_DIR')
            
        if os.getenv('ENABLE_PERSISTENCE'):
            env_overrides['enable_persistence'] = os.getenv('ENABLE_PERSISTENCE').lower() in ['true', '1', 'yes']
            
        # Privacy settings
        if os.getenv('PRIVACY_MODE'):
            env_overrides['privacy_mode'] = os.getenv('PRIVACY_MODE').lower() in ['true', '1', 'yes']
            
        # API keys
        if os.getenv('OPENAI_API_KEY'):
            env_overrides['openai_api_key'] = os.getenv('OPENAI_API_KEY')
            
        if os.getenv('ANTHROPIC_API_KEY'):
            env_overrides['anthropic_api_key'] = os.getenv('ANTHROPIC_API_KEY')
            
        # Consent flags
        if os.getenv('CONSENT_LLM'):
            env_overrides['consent_llm'] = os.getenv('CONSENT_LLM').lower() in ['true', '1', 'yes']
            
        if os.getenv('CONSENT_DEEPL'):
            env_overrides['consent_deepl'] = os.getenv('CONSENT_DEEPL').lower() in ['true', '1', 'yes']
            
        return env_overrides
        
    def save_config(self, config: Optional[ClinicalVoiceConfig] = None):
        """Save configuration to file"""
        try:
            config_to_save = config or self.config
            
            # Convert to dictionary, excluding sensitive data
            config_dict = asdict(config_to_save)
            
            # Remove sensitive keys (they should be in .env)
            sensitive_keys = ['openai_api_key', 'deepl_api_key']
            for key in sensitive_keys:
                if key in config_dict:
                    del config_dict[key]
                    
            # Save to file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Configuration saved to: {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            
    def update_config(self, **kwargs):
        """Update configuration parameters"""
        try:
            config_dict = asdict(self.config)
            config_dict.update(kwargs)
            self.config = ClinicalVoiceConfig(**config_dict)
            
            self.logger.info("Configuration updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            
    def set_env_var(self, key: str, value: str):
        """Set environment variable and update .env file"""
        try:
            # Set in current environment
            os.environ[key] = value
            
            # Update .env file
            set_key(self.env_file, key, value)
            
            self.logger.info(f"Environment variable set: {key}")
            
        except Exception as e:
            self.logger.error(f"Failed to set environment variable {key}: {e}")
            
    def get_config(self) -> ClinicalVoiceConfig:
        """Get current configuration"""
        return self.config
        
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration and return status"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': []
        }
        
        try:
            # Validate Whisper model
            valid_models = ["tiny", "base", "small", "medium", "large-v3"]
            if self.config.whisper_model not in valid_models:
                validation_results['errors'].append(
                    f"Invalid Whisper model: {self.config.whisper_model}. "
                    f"Valid options: {', '.join(valid_models)}"
                )
                validation_results['valid'] = False
                
            # Validate audio settings
            if not 8000 <= self.config.sample_rate <= 48000:
                validation_results['warnings'].append(
                    f"Sample rate {self.config.sample_rate} may not be optimal. "
                    "Recommended: 16000Hz"
                )
                
            if self.config.channels not in [1, 2]:
                validation_results['errors'].append(
                    f"Invalid channels: {self.config.channels}. Must be 1 or 2"
                )
                validation_results['valid'] = False
                
            # Validate Stream Deck settings
            if self.config.deck_button_index < 0:
                validation_results['errors'].append(
                    "Stream Deck button index must be non-negative"
                )
                validation_results['valid'] = False
                
            # Validate LLM settings
            if self.config.enable_llm:
                if not self.config.llm_endpoint and not self.config.openai_api_key:
                    validation_results['warnings'].append(
                        "LLM enabled but no endpoint or API key configured"
                    )
                    
            # Validate DeepL settings
            if self.config.enable_deepl:
                if not self.config.deepl_api_key:
                    validation_results['warnings'].append(
                        "DeepL enabled but no API key configured"
                    )
                    
            # Validate TTS settings
            if self.config.enable_tts:
                if not 50 <= self.config.tts_rate <= 500:
                    validation_results['warnings'].append(
                        f"TTS rate {self.config.tts_rate} may be too fast/slow. "
                        "Recommended: 150-250"
                    )
                    
            # Validate storage settings
            try:
                output_path = Path(self.config.output_dir)
                if not output_path.parent.exists():
                    validation_results['warnings'].append(
                        f"Output directory parent does not exist: {output_path.parent}"
                    )
            except Exception:
                validation_results['errors'].append(
                    f"Invalid output directory path: {self.config.output_dir}"
                )
                validation_results['valid'] = False
                
            # Privacy mode checks
            if self.config.privacy_mode:
                external_services = []
                if self.config.enable_llm and (self.config.llm_endpoint or self.config.openai_api_key):
                    external_services.append("LLM")
                if self.config.enable_deepl and self.config.deepl_api_key:
                    external_services.append("DeepL")
                    
                if external_services:
                    if not self.config.consent_llm and "LLM" in external_services:
                        validation_results['warnings'].append(
                            "Privacy mode enabled but LLM consent not granted"
                        )
                    if not self.config.consent_deepl and "DeepL" in external_services:
                        validation_results['warnings'].append(
                            "Privacy mode enabled but DeepL consent not granted"
                        )
                        
            # Success info
            if validation_results['valid'] and not validation_results['warnings']:
                validation_results['info'].append("Configuration is valid and optimal")
                
        except Exception as e:
            validation_results['errors'].append(f"Validation error: {e}")
            validation_results['valid'] = False
            
        return validation_results
        
    def create_sample_env_file(self):
        """Create a sample .env file with documentation"""
        try:
            sample_env_content = """# Clinical Voice Interpreter Configuration
# Copy this file to .env and customize for your setup

# ==================== AUDIO SETTINGS ====================
# Sample rate for audio recording (Hz)
# SAMPLE_RATE=16000

# Number of audio channels (1=mono, 2=stereo)
# CHANNELS=1

# Audio buffer size
# CHUNK_SIZE=1024

# ==================== WHISPER SETTINGS ====================
# Whisper model size (tiny/base/small/medium/large-v3)
WHISPER_MODEL=small

# Language for transcription (auto-detect if not set)
# WHISPER_LANGUAGE=en

# ==================== STREAM DECK SETTINGS ====================
# Which Stream Deck button to use (0-based index)
DECK_BUTTON_INDEX=0

# ==================== TEXT PROCESSING ====================
# LLM endpoint for text processing (optional)
# LLM_ENDPOINT=http://localhost:11434/api/generate

# OpenAI API key (for LLM fallback)
# OPENAI_API_KEY=your_openai_api_key_here

# DeepL API key for translation (optional)
# DEEPL_API_KEY=your_deepl_api_key_here

# Target language for DeepL translation
DEEPL_TARGET_LANG=EN-US

# ==================== TTS SETTINGS ====================
# Enable text-to-speech output
ENABLE_TTS=true

# TTS voice (system-specific)
# TTS_VOICE=Alex

# TTS speech rate (words per minute)
TTS_RATE=200

# ==================== STORAGE SETTINGS ====================
# Output directory for transcriptions
OUTPUT_DIR=./output

# Enable local persistence
ENABLE_PERSISTENCE=true

# ==================== PRIVACY SETTINGS ====================
# Privacy mode (requires explicit consent for external services)
PRIVACY_MODE=true

# Consent for external services (set to true to allow)
CONSENT_LLM=false
CONSENT_DEEPL=false

# ==================== ADVANCED SETTINGS ====================
# Additional environment variables can be added here
# for custom integrations and advanced configuration
"""
            
            sample_file = self.env_file.parent / ".env.sample"
            with open(sample_file, 'w', encoding='utf-8') as f:
                f.write(sample_env_content)
                
            self.logger.info(f"Sample .env file created: {sample_file}")
            return str(sample_file)
            
        except Exception as e:
            self.logger.error(f"Failed to create sample .env file: {e}")
            return None
            
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        try:
            return {
                'audio': {
                    'sample_rate': self.config.sample_rate,
                    'channels': self.config.channels,
                    'chunk_size': self.config.chunk_size
                },
                'whisper': {
                    'model': self.config.whisper_model,
                    'language': self.config.whisper_language or 'auto-detect'
                },
                'stream_deck': {
                    'button_index': self.config.deck_button_index
                },
                'text_processing': {
                    'llm_enabled': self.config.enable_llm,
                    'llm_configured': bool(self.config.llm_endpoint or self.config.openai_api_key),
                    'deepl_enabled': self.config.enable_deepl,
                    'deepl_configured': bool(self.config.deepl_api_key)
                },
                'tts': {
                    'enabled': self.config.enable_tts,
                    'voice': self.config.tts_voice or 'system-default',
                    'rate': self.config.tts_rate
                },
                'storage': {
                    'output_dir': self.config.output_dir,
                    'persistence_enabled': self.config.enable_persistence
                },
                'privacy': {
                    'privacy_mode': self.config.privacy_mode,
                    'llm_consent': self.config.consent_llm,
                    'deepl_consent': self.config.consent_deepl
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get config summary: {e}")
            return {}
            
    def export_config(self, file_path: str, include_sensitive: bool = False):
        """Export configuration to a file"""
        try:
            config_dict = asdict(self.config)
            
            # Remove sensitive data unless explicitly requested
            if not include_sensitive:
                sensitive_keys = ['openai_api_key', 'deepl_api_key']
                for key in sensitive_keys:
                    if key in config_dict and config_dict[key]:
                        config_dict[key] = "***REDACTED***"
                        
            # Add metadata
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'config_version': '1.0',
                'configuration': config_dict
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Configuration exported to: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            
    def import_config(self, file_path: str) -> bool:
        """Import configuration from a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
                
            # Extract configuration
            if 'configuration' in import_data:
                config_dict = import_data['configuration']
            else:
                config_dict = import_data  # Assume direct config format
                
            # Remove redacted values
            for key, value in config_dict.items():
                if value == "***REDACTED***":
                    config_dict[key] = None
                    
            # Update current config
            current_dict = asdict(self.config)
            current_dict.update(config_dict)
            self.config = ClinicalVoiceConfig(**current_dict)
            
            # Save updated config
            self.save_config()
            
            self.logger.info(f"Configuration imported from: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            return False
            
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        try:
            self.config = ClinicalVoiceConfig()
            self.save_config()
            self.logger.info("Configuration reset to defaults")
            
        except Exception as e:
            self.logger.error(f"Failed to reset configuration: {e}")
            
    def get_env_file_path(self) -> str:
        """Get path to .env file"""
        return str(self.env_file)
        
    def get_config_file_path(self) -> str:
        """Get path to config file"""
        return str(self.config_file)
        
    def cleanup(self):
        """Clean up config manager resources"""
        try:
            # Save current configuration
            self.save_config()
            
            self.logger.info("Configuration manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during config manager cleanup: {e}")

# Utility functions for configuration management

def setup_initial_config(base_dir: str = ".") -> ConfigManager:
    """
    Set up initial configuration for first-time users
    
    Args:
        base_dir: Base directory for config files
        
    Returns:
        Configured ConfigManager instance
    """
    try:
        base_path = Path(base_dir)
        config_manager = ConfigManager(
            config_file=base_path / "clinical_voice_config.json",
            env_file=base_path / ".env"
        )
        
        # Create sample .env if it doesn't exist
        if not config_manager.env_file.exists():
            config_manager.create_sample_env_file()
            
        # Save initial config
        config_manager.save_config()
        
        return config_manager
        
    except Exception as e:
        logging.error(f"Failed to setup initial config: {e}")
        raise

def migrate_config(old_config_path: str, new_config_manager: ConfigManager) -> bool:
    """
    Migrate configuration from old format to new format
    
    Args:
        old_config_path: Path to old configuration file
        new_config_manager: New ConfigManager instance
        
    Returns:
        True if migration successful
    """
    try:
        # This function can be expanded to handle migration from
        # different configuration formats (e.g., from the original
        # push-to-talk project format)
        
        if Path(old_config_path).exists():
            return new_config_manager.import_config(old_config_path)
        else:
            logging.warning(f"Old config file not found: {old_config_path}")
            return False
            
    except Exception as e:
        logging.error(f"Config migration failed: {e}")
        return False
