"""
Stream Deck Controller for Clinical Voice Interpreter
Handles Stream Deck button press/release events with visual feedback
"""

import logging
import threading
import time
from typing import Callable, Optional
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

try:
    from StreamDeck.DeviceManager import DeviceManager
    from StreamDeck.ImageHelpers import PILHelper
    STREAMDECK_AVAILABLE = True
except ImportError:
    STREAMDECK_AVAILABLE = False
    logging.warning("StreamDeck library not available. Stream Deck functionality will be disabled.")

class StreamDeckController:
    """
    Controller for Elgato Stream Deck integration
    Provides visual feedback and button state management
    """
    
    def __init__(self, button_index: int = 0, on_press: Optional[Callable] = None, 
                 on_release: Optional[Callable] = None):
        self.button_index = button_index
        self.on_press_callback = on_press
        self.on_release_callback = on_release
        
        self.deck = None
        self.running = False
        self.button_pressed = False
        self.monitor_thread = None
        
        self.logger = logging.getLogger(__name__)
        
        # Button state images
        self._icon_idle = None
        self._icon_recording = None
        self._icon_processing = None
        
        if not STREAMDECK_AVAILABLE:
            self.logger.error("StreamDeck library not available")
            return
            
        self._init_deck()
        self._create_button_icons()
        
    def _init_deck(self):
        """Initialize Stream Deck connection"""
        try:
            streamdecks = DeviceManager().enumerate()
            
            if not streamdecks:
                self.logger.error("No Stream Deck devices found")
                return
                
            # Use first available deck
            self.deck = streamdecks[0]
            self.deck.open()
            self.deck.reset()
            
            # Set brightness
            self.deck.set_brightness(50)
            
            self.logger.info(f"Stream Deck connected: {self.deck.deck_type()}")
            self.logger.info(f"Buttons available: {self.deck.key_count()}")
            
            if self.button_index >= self.deck.key_count():
                self.logger.error(f"Button index {self.button_index} exceeds available buttons")
                self.button_index = 0
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Stream Deck: {e}")
            self.deck = None
            
    def _create_button_icons(self):
        """Create visual icons for different button states"""
        if not self.deck:
            return
            
        try:
            # Get button image format
            key_spacing = self.deck.key_image_format()['size']
            
            # Create idle state icon (microphone off)
            self._icon_idle = self._create_icon(
                key_spacing, "🎤", "gray", "IDLE"
            )
            
            # Create recording state icon (microphone on)
            self._icon_recording = self._create_icon(
                key_spacing, "🎤", "red", "REC"
            )
            
            # Create processing state icon
            self._icon_processing = self._create_icon(
                key_spacing, "⚙️", "orange", "PROC"
            )
            
            self.logger.info("Button icons created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create button icons: {e}")
            
    def _create_icon(self, size: tuple, emoji: str, color: str, text: str):
        """Create a button icon with emoji and text"""
        try:
            # Create image
            image = Image.new('RGB', size, color='black')
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fall back to default
            try:
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_small = ImageFont.truetype("arial.ttf", 12)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Draw emoji (if supported)
            try:
                emoji_bbox = draw.textbbox((0, 0), emoji, font=font_large)
                emoji_w = emoji_bbox[2] - emoji_bbox[0]
                emoji_h = emoji_bbox[3] - emoji_bbox[1]
                emoji_x = (size[0] - emoji_w) // 2
                emoji_y = (size[1] - emoji_h) // 2 - 10
                draw.text((emoji_x, emoji_y), emoji, font=font_large, fill='white')
            except:
                # Fallback to simple circle
                circle_size = 20
                circle_x = (size[0] - circle_size) // 2
                circle_y = (size[1] - circle_size) // 2 - 10
                draw.ellipse([circle_x, circle_y, circle_x + circle_size, circle_y + circle_size], 
                           fill=color)
            
            # Draw text label
            text_bbox = draw.textbbox((0, 0), text, font=font_small)
            text_w = text_bbox[2] - text_bbox[0]
            text_x = (size[0] - text_w) // 2
            text_y = size[1] - 20
            draw.text((text_x, text_y), text, font=font_small, fill=color)
            
            # Convert to Stream Deck format
            return PILHelper.to_native_format(self.deck, image)
            
        except Exception as e:
            self.logger.error(f"Failed to create icon: {e}")
            return None
            
    def start(self):
        """Start Stream Deck monitoring"""
        if not self.deck:
            self.logger.error("Stream Deck not available")
            return False
            
        try:
            self.running = True
            
            # Set initial button state
            self.set_button_state('idle')
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(target=self._monitor_buttons, daemon=True)
            self.monitor_thread.start()
            
            self.logger.info("Stream Deck monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Stream Deck monitoring: {e}")
            return False
            
    def stop(self):
        """Stop Stream Deck monitoring"""
        try:
            self.running = False
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=1.0)
                
            if self.deck:
                self.deck.reset()
                
            self.logger.info("Stream Deck monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Stream Deck: {e}")
            
    def _monitor_buttons(self):
        """Monitor button press/release events"""
        previous_states = [False] * self.deck.key_count()
        
        while self.running:
            try:
                # Read current button states
                current_states = []
                for i in range(self.deck.key_count()):
                    current_states.append(self.deck.key_states()[i])
                
                # Check our target button
                current_pressed = current_states[self.button_index]
                previous_pressed = previous_states[self.button_index]
                
                # Detect press event
                if current_pressed and not previous_pressed:
                    self.logger.info(f"Button {self.button_index} pressed")
                    self.button_pressed = True
                    self.set_button_state('recording')
                    
                    if self.on_press_callback:
                        self.on_press_callback()
                        
                # Detect release event
                elif not current_pressed and previous_pressed:
                    self.logger.info(f"Button {self.button_index} released")
                    self.button_pressed = False
                    self.set_button_state('processing')
                    
                    if self.on_release_callback:
                        self.on_release_callback()
                        
                previous_states = current_states.copy()
                time.sleep(0.01)  # 10ms polling
                
            except Exception as e:
                self.logger.error(f"Error in button monitoring: {e}")
                time.sleep(0.1)
                
    def set_button_state(self, state: str):
        """Set visual state of the button"""
        if not self.deck:
            return
            
        try:
            icon = None
            
            if state == 'idle':
                icon = self._icon_idle
            elif state == 'recording':
                icon = self._icon_recording
            elif state == 'processing':
                icon = self._icon_processing
                
            if icon:
                self.deck.set_key_image(self.button_index, icon)
                
        except Exception as e:
            self.logger.error(f"Failed to set button state: {e}")
            
    def reset_to_idle(self):
        """Reset button to idle state"""
        self.set_button_state('idle')
        
    def cleanup(self):
        """Clean up Stream Deck resources"""
        try:
            self.stop()
            
            if self.deck:
                self.deck.close()
                self.deck = None
                
            self.logger.info("Stream Deck cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Stream Deck cleanup: {e}")
            
    def is_available(self) -> bool:
        """Check if Stream Deck is available and connected"""
        return STREAMDECK_AVAILABLE and self.deck is not None
        
    def get_info(self) -> dict:
        """Get Stream Deck device information"""
        if not self.deck:
            return {'available': False}
            
        try:
            return {
                'available': True,
                'deck_type': self.deck.deck_type(),
                'serial_number': self.deck.get_serial_number(),
                'firmware_version': self.deck.get_firmware_version(),
                'key_count': self.deck.key_count(),
                'button_index': self.button_index
            }
        except Exception as e:
            self.logger.error(f"Failed to get Stream Deck info: {e}")
            return {'available': False, 'error': str(e)}