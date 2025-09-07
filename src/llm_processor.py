"""
LLM Processor for Clinical Voice Interpreter
Handles AI-powered conversation analysis and queries
"""

import logging
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

# Try to import AI libraries
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMProcessor:
    """AI-powered clinical conversation processor"""
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 anthropic_api_key: Optional[str] = None,
                 llm_endpoint: Optional[str] = None,
                 model_name: str = "claude-3-haiku-20240307",
                 privacy_mode: bool = True):
        
        self.logger = logging.getLogger(__name__)
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.llm_endpoint = llm_endpoint
        self.model_name = model_name
        self.privacy_mode = privacy_mode
        
        # Initialize LLM connections
        self.openai_client = None
        self.anthropic_client = None
        self.local_endpoint_available = False
        
        self._init_llm_connection()
        
    def _init_llm_connection(self):
        """Initialize connection to LLM services"""
        self.logger.info("Initializing LLM connections...")
        
        # Try Anthropic (Claude) first
        if ANTHROPIC_AVAILABLE and self.anthropic_api_key and not self.privacy_mode:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
                self.logger.info("Anthropic Claude client initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize Anthropic: {e}")
        
        # Try OpenAI as fallback
        if OPENAI_AVAILABLE and self.openai_api_key and not self.privacy_mode:
            try:
                openai.api_key = self.openai_api_key
                self.openai_client = openai
                self.logger.info("OpenAI client initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI: {e}")
                
        # Try local endpoint
        if self.llm_endpoint:
            try:
                # Test local endpoint with a simple request
                test_response = requests.post(
                    f"{self.llm_endpoint}/health", 
                    timeout=5
                )
                if test_response.status_code == 200:
                    self.local_endpoint_available = True
                    self.logger.info(f"Local LLM endpoint available: {self.llm_endpoint}")
            except Exception as e:
                self.logger.warning(f"Local LLM endpoint not available: {e}")
                
        # Check if any LLM is available
        if not self.anthropic_client and not self.openai_client and not self.local_endpoint_available:
            self.logger.warning("No LLM services available - LLM features disabled")
    
    def is_available(self) -> bool:
        """Check if any LLM service is available"""
        return bool(self.anthropic_client or self.openai_client or self.local_endpoint_available)
    
    def review_conversation(self, conversation_summary: str) -> Dict[str, Any]:
        """
        Review conversation for inconsistencies and suggest follow-up questions
        
        Mode 1: Clinical Review
        """
        if not self.is_available():
            return {"error": "No LLM service available"}
            
        system_prompt = """You are a medical AI assistant helping with clinical conversations. 

Analyze the provided conversation between a doctor and patient. Your tasks:

1. IDENTIFY INCONSISTENCIES: Look for contradictory information, unclear statements, or missing critical details
2. SUGGEST CLARIFICATIONS: Propose specific follow-up questions to gather missing information
3. MEDICAL RELEVANCE: Highlight medically significant statements that need follow-up
4. COMMUNICATION GAPS: Identify where translation or communication might have caused confusion

Respond in Italian (for the doctor) with a structured analysis.

Format your response as:
🔍 ANALISI CONVERSAZIONE:
[Your analysis]

⚠️ INCONGRUENZE RILEVATE:
[List any inconsistencies]

❓ DOMANDE SUGGERITE:
[Specific questions to ask the patient]

🏥 NOTE CLINICHE:
[Medical observations and recommendations]"""

        user_prompt = f"""Analizza questa conversazione clinica:

{conversation_summary}

Fornisci un'analisi dettagliata come descritto nelle istruzioni."""

        try:
            response = self._call_llm(system_prompt, user_prompt)
            return {
                "success": True,
                "analysis": response,
                "mode": "conversation_review",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to review conversation: {e}")
            return {"error": f"Review failed: {str(e)}"}
    
    def process_query(self, query: str, conversation_context: str = "") -> Dict[str, Any]:
        """
        Process a direct query with conversation context
        
        Mode 2: Direct Query
        """
        if not self.is_available():
            return {"error": "No LLM service available"}
            
        system_prompt = """You are a medical AI assistant in a clinical setting. 

You help doctors:
- Explain medical conditions to patients in simple terms
- Suggest diagnostic questions for specific conditions  
- Provide patient education materials
- Clarify medical terminology
- Generate treatment explanations

Always respond in Italian, using clear and empathetic language appropriate for patient communication.
Be professional but warm and reassuring.

If you have conversation context, use it to provide more personalized responses."""

        user_prompt = f"""RICHIESTA: {query}

CONTESTO CONVERSAZIONE:
{conversation_context if conversation_context else "Nessun contesto disponibile"}

Fornisci una risposta utile e appropriata per il contesto clinico."""

        try:
            response = self._call_llm(system_prompt, user_prompt)
            return {
                "success": True,
                "response": response,
                "mode": "direct_query",
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to process query: {e}")
            return {"error": f"Query failed: {str(e)}"}
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Make the actual LLM API call"""
        
        # Try Anthropic (Claude) first
        if self.anthropic_client:
            try:
                message = self.anthropic_client.messages.create(
                    model=self.model_name,
                    max_tokens=1000,
                    temperature=0.7,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return message.content[0].text
                
            except Exception as e:
                self.logger.error(f"Anthropic API call failed: {e}")
        
        # Try OpenAI as fallback
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Use OpenAI model if falling back
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                return response.choices[0].message.content
                
            except Exception as e:
                self.logger.error(f"OpenAI API call failed: {e}")
                
        # Try local endpoint as fallback
        if self.local_endpoint_available:
            try:
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
                
                response = requests.post(
                    f"{self.llm_endpoint}/chat/completions",
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    raise Exception(f"Local endpoint returned {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"Local LLM call failed: {e}")
                
        raise Exception("All LLM services failed")
    
    def get_suggested_queries(self) -> List[str]:
        """Get a list of suggested queries for the doctor"""
        return [
            "Spiega al paziente cos'è l'ipertensione in termini semplici",
            "Suggerisci domande per anamnesi cardiovascolare",  
            "Come spiegare gli effetti collaterali di questo farmaco",
            "Domande per valutare il dolore toracico",
            "Spiegazione semplice di cosa sono gli esami del sangue",
            "Come rassicurare un paziente ansioso",
            "Istruzioni post-operatorie da dare al paziente",
            "Spiegare l'importanza dell'aderenza terapeutica"
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current LLM processor status"""
        return {
            "available": self.is_available(),
            "anthropic_connected": bool(self.anthropic_client),
            "openai_connected": bool(self.openai_client),
            "local_endpoint_connected": self.local_endpoint_available,
            "model_name": self.model_name,
            "privacy_mode": self.privacy_mode,
            "endpoint": self.llm_endpoint
        }
    
    def cleanup(self):
        """Clean up LLM processor resources"""
        try:
            self.anthropic_client = None
            self.openai_client = None
            self.local_endpoint_available = False
            self.logger.info("LLM processor cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during LLM cleanup: {e}")