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
        """
        user_tags = context.get('user_tags') if context else None

        if not user_tags:
            from core.config import settings
            user_tags = settings.DEFAULT_PII_TAGS
            log.info(f"SLMDetector: No tags provided, using defaults: {user_tags}")

        page_number = context.get('page_number') if context else None
        
        log.debug(f"SLMDetector: Analyzing with tags: {user_tags}")
        
        # Process text in chunks to avoid timeout on long documents
        all_detections = []
        chunks = self._split_text(text)
        
        log.info(f"SLMDetector: Processing {len(chunks)} chunk(s)")

        for i, chunk in enumerate(chunks):
            try:
                prompt = self._build_prompt(chunk['text'], user_tags)
                detections_data = await self._call_ollama(prompt)
                chunk_detections = self._parse_response(
                    detections_data, 
                    text,           # use full text for position finding
                    page_number,
                    chunk_offset=chunk['offset']
                )
                all_detections.extend(chunk_detections)
                log.info(f"SLMDetector: Chunk {i+1}/{len(chunks)} → {len(chunk_detections)} matches")

            except Exception as e:
                log.error(f"SLMDetector failed on chunk {i+1}: {type(e).__name__}: {str(e)}")
                continue
        
        log.info(f"SLMDetector: Found {len(all_detections)} context-aware matches total")
        return all_detections
    
    def _split_text(self, text: str, chunk_size: int = 2000) -> List[Dict]:
        """
        Split text into chunks for faster SLM processing.
        Splits on newlines where possible to avoid cutting mid-sentence.
        """
        if len(text) <= chunk_size:
            return [{'text': text, 'offset': 0}]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end >= len(text):
                chunks.append({'text': text[start:], 'offset': start})
                break

            # Try to split on a newline boundary
            split_pos = text.rfind('\n', start, end)
            if split_pos == -1 or split_pos <= start:
                split_pos = end  # fallback to hard cut

            chunks.append({'text': text[start:split_pos], 'offset': start})
            start = split_pos + 1

        return chunks

    def _build_prompt(self, text: str, user_tags: List[str]) -> str:
        """Build prompt for the SLM"""
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
        """Call Ollama API for inference"""
        url = f"{self.ollama_host}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get('response', '[]')
            
            try:
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                detections_data = json.loads(response_text)
                log.info(f"SLM raw response: {response_text[:500]}")
                return detections_data if isinstance(detections_data, list) else []
            
            except json.JSONDecodeError as e:
                log.info(f"SLM raw response: {response_text[:500]}")
                log.error(f"Failed to parse SLM response as JSON: {e}")
                log.debug(f"Response text: {response_text}")
                return []
    
    def _parse_response(
        self, 
        detections_data: List[Dict[str, str]], 
        text: str, 
        page_number: int = None,
        chunk_offset: int = 0
    ) -> List[Detection]:
        """Parse SLM response into Detection objects"""
        detections = []
        used_positions: Dict[str, List[int]] = {}
        
        for item in detections_data:
            pii_type = item.get('type', 'unknown')
            value = item.get('value', '')
            
            if not value:
                continue
            
            # Find position in full text, skipping already-used positions
            search_start = chunk_offset
            if value in used_positions:
                last_pos = used_positions[value][-1]
                search_start = max(chunk_offset, last_pos + 1)
            
            start_pos = text.find(value, search_start)
            
            if start_pos == -1:
                # Try case-insensitive search
                value_lower = value.lower()
                text_lower = text.lower()
                start_pos = text_lower.find(value_lower, search_start)
                if start_pos != -1:
                    value = text[start_pos:start_pos + len(value)]
            
            if start_pos == -1:
                log.warning(f"SLM detected '{value}' but couldn't find in text")
                continue

            if value not in used_positions:
                used_positions[value] = []
            used_positions[value].append(start_pos)
            
            end_pos = start_pos + len(value)
            
            detection = self._create_detection(
                pii_type=pii_type,
                value=value,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=0.85,
                page_number=page_number
            )
            detections.append(detection)
        
        return detections
    
    async def check_ollama_health(self) -> bool:
        """Check if Ollama service is available"""
        try:
            url = f"{self.ollama_host}/api/tags"
            
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                
                model_found = any(
                    name == self.model or 
                    name.startswith(f"{self.model}:") or
                    name == f"{self.model}:latest"
                    for name in model_names
                )
                
                if model_found:
                    log.info(f"Ollama healthy, model {self.model} available")
                    return True
                else:
                    log.warning(f"Model {self.model} not found in Ollama")
                    return False
        
        except Exception as e:
            log.error(f"Ollama health check failed: {type(e).__name__}: {str(e)}")
            return False