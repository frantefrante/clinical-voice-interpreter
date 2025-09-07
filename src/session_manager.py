"""
Session Manager for Clinical Voice Interpreter
Handles persistence of transcriptions and metadata
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SessionManager:
    """Save session artifacts to disk in a simple JSON format"""

    def __init__(self, output_dir: str = "./output", enabled: bool = True):
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(output_dir)
        self.enabled = enabled
        
        # Conversation tracking
        self.current_conversation: List[Dict[str, Any]] = []
        self.conversation_started = datetime.now()
        
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create output dir '{self.output_dir}': {e}")
            self.enabled = False

    def save_transcription(
        self,
        original_text: str,
        processed_text: str,
        audio_file: Optional[str],
        model: str,
        processing_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            entry = {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "original_text": original_text,
                "processed_text": processed_text,
                "audio_file": audio_file,
                "processing": processing_config or {},
            }
            out_path = self.output_dir / f"transcription_{ts}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved transcription: {out_path}")
            return str(out_path)
        except Exception as e:
            self.logger.error(f"Failed to save transcription: {e}")
            return None

    def add_to_conversation(self, speaker: str, text: str, translation: str = None, 
                           translation_direction: str = None) -> None:
        """Add a message to the current conversation"""
        message = {
            "timestamp": datetime.now().isoformat(),
            "speaker": speaker,  # "patient", "doctor", "system"
            "original_text": text,
            "translation": translation,
            "translation_direction": translation_direction,  # "it_to_en", "en_to_it"
        }
        self.current_conversation.append(message)
        self.logger.info(f"Added to conversation: {speaker} - {text[:50]}...")
        
    def get_conversation_context(self, last_n_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history for LLM context"""
        if last_n_messages:
            return self.current_conversation[-last_n_messages:]
        return self.current_conversation.copy()
    
    def get_conversation_summary(self) -> str:
        """Get a formatted summary of the conversation for LLM"""
        if not self.current_conversation:
            return "No conversation yet."
            
        summary = f"Clinical conversation started at {self.conversation_started.strftime('%H:%M:%S')}:\n\n"
        
        for msg in self.current_conversation:
            timestamp = datetime.fromisoformat(msg["timestamp"]).strftime("%H:%M:%S")
            speaker = msg["speaker"].title()
            original = msg["original_text"]
            translation = msg.get("translation", "")
            direction = msg.get("translation_direction", "")
            
            summary += f"[{timestamp}] {speaker}: {original}\n"
            if translation and translation != original:
                direction_arrow = "🇮🇹→🇬🇧" if direction == "it_to_en" else "🇬🇧→🇮🇹" if direction == "en_to_it" else ""
                summary += f"  {direction_arrow} {translation}\n"
            summary += "\n"
            
        return summary
    
    def save_conversation(self) -> Optional[str]:
        """Save the current conversation to a file"""
        if not self.enabled or not self.current_conversation:
            return None
            
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            conversation_data = {
                "session_started": self.conversation_started.isoformat(),
                "session_ended": datetime.now().isoformat(),
                "total_messages": len(self.current_conversation),
                "conversation": self.current_conversation
            }
            
            out_path = self.output_dir / f"conversation_{ts}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Saved conversation: {out_path}")
            return str(out_path)
            
        except Exception as e:
            self.logger.error(f"Failed to save conversation: {e}")
            return None
    
    def start_new_conversation(self) -> None:
        """Start a new conversation (save current one if exists)"""
        if self.current_conversation:
            self.save_conversation()
            
        self.current_conversation = []
        self.conversation_started = datetime.now()
        self.logger.info("Started new conversation session")

    def cleanup(self):
        """Clean up session manager resources"""
        try:
            # Save current conversation before cleanup
            if self.current_conversation:
                self.save_conversation()
                
            self.logger.info("Session manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during session manager cleanup: {e}")
