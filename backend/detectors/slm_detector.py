"""
Small Language Model (SLM) detector using Ollama for context-aware PII detection
"""
import json
from typing import List, Dict, Any
import httpx
from detectors.base import BaseDetector
from models.schemas import Detection
from core.config import settings
from core.logger import log


class SLMDetector(BaseDetector):
    """Detects PII using Small Language Model via Ollama"""
    
    def __init__(self):
        super().__init__(name="slm")
        self.ollama_host = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        
        log.info(f"SLMDetector initialized with model: {self.model}")
    
    async def detect(self, text: str, context: Dict[str, Any] = None) -> List[Detection]:
        """
        Detect PII using SLM with user-provided tags as hints
        
        Args:
            text: Text to analyze
            context: Context including user_tags and page_number
        
        Returns:
            List of Detection objects
        """
        if not context or not context.get('user_tags'):
            log.debug("SLMDetector: No user tags provided, skipping SLM detection")
            return []
        
        user_tags = context.get('user_tags', [])
        page_number = context.get('page_number')
        
        log.debug(f"SLMDetector: Analyzing with tags: {user_tags}")
        
        # Build prompt
        prompt = self._build_prompt(text, user_tags)
        
        # Call Ollama API
        try:
            detections_data = await self._call_ollama(prompt)
            detections = self._parse_response(detections_data, text, page_number)
            
            log.info(f"SLMDetector: Found {len(detections)} context-aware matches")
            return detections
        
        except Exception as e:
            log.error(f"SLMDetector failed: {str(e)}")
            return []
    
    def _build_prompt(self, text: str, user_tags: List[str]) -> str:
        """
        Build prompt for the SLM
        
        Args:
            text: Text to analyze
            user_tags: User-provided PII tags
        
        Returns:
            Formatted prompt string
        """
        tags_str = ", ".join(user_tags)
        
        prompt = f"""You are a PII (Personally Identifiable Information) detection assistant. Your task is to identify all instances of the following PII types in the provided text:

PII Types to detect: {tags_str}

Instructions:
1. Carefully read the text below
2. Identify ALL instances of the specified PII types
3. For each detection, note the exact text and its position
4. Return ONLY a JSON array with the following structure:

[
  {{
    "type": "pii_type",
    "value": "exact text found",
    "context": "brief surrounding context"
  }}
]

Important:
- Be precise with the exact text
- Include variations (e.g., "Dr. Smith" for name, "diabetes" for medical_condition)
- Do NOT include explanations or preamble
- Return ONLY the JSON array, nothing else

Text to analyze:
{text}

JSON array:"""
        
        return prompt
    
    async def _call_ollama(self, prompt: str) -> List[Dict[str, str]]:
        """
        Call Ollama API for inference
        
        Args:
            prompt: Formatted prompt
        
        Returns:
            Parsed JSON response
        """
        url = f"{self.ollama_host}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # Request JSON output
            "options": {
                "temperature": 0.1,  # Low temperature for more deterministic output
                "top_p": 0.9,
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get('response', '[]')
            
            # Parse JSON from response
            try:
                # Remove any markdown code blocks if present
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                detections_data = json.loads(response_text)
                return detections_data if isinstance(detections_data, list) else []
            
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse SLM response as JSON: {e}")
                log.debug(f"Response text: {response_text}")
                return []
    
    def _parse_response(
        self, 
        detections_data: List[Dict[str, str]], 
        text: str, 
        page_number: int = None
    ) -> List[Detection]:
        """
        Parse SLM response into Detection objects
        
        Args:
            detections_data: List of detection dicts from SLM
            text: Original text (to find positions)
            page_number: Page number if available
        
        Returns:
            List of Detection objects
        """
        detections = []
        
        for item in detections_data:
            pii_type = item.get('type', 'unknown')
            value = item.get('value', '')
            
            if not value:
                continue
            
            # Find position in text
            start_pos = text.find(value)
            
            if start_pos == -1:
                # Try case-insensitive search
                value_lower = value.lower()
                text_lower = text.lower()
                start_pos = text_lower.find(value_lower)
                
                if start_pos != -1:
                    # Get actual text at that position
                    value = text[start_pos:start_pos + len(value)]
            
            if start_pos == -1:
                log.warning(f"SLM detected '{value}' but couldn't find in text")
                continue
            
            end_pos = start_pos + len(value)
            
            # SLM detections have slightly lower confidence since they're context-based
            confidence = 0.85
            
            detection = self._create_detection(
                pii_type=pii_type,
                value=value,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=confidence,
                page_number=page_number
            )
            detections.append(detection)
        
        return detections
    
    async def check_ollama_health(self) -> bool:
        """
        Check if Ollama service is available
        
        Returns:
            True if available, False otherwise
        """
        try:
            url = f"{self.ollama_host}/api/tags"
            
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Check if our model is available
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                
                if self.model in model_names or f"{self.model}:latest" in model_names:
                    log.info(f"Ollama healthy, model {self.model} available")
                    return True
                else:
                    log.warning(f"Model {self.model} not found in Ollama")
                    return False
        
        except Exception as e:
            log.error(f"Ollama health check failed: {str(e)}")
            return False