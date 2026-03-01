"""
Named Entity Recognition (NER) detector using spaCy
"""
from typing import List, Dict, Any
import spacy
from detectors.base import BaseDetector
from models.schemas import Detection
from core.logger import log
import asyncio

class NERDetector(BaseDetector):
    """Detects PII using spaCy Named Entity Recognition"""
    
    # Map spaCy entity types to our PII types
    ENTITY_TYPE_MAPPING = {
        "PERSON": "name",
        "ORG": "organization",
        "GPE": "location",
        "LOC": "location",
        "DATE": "date",
        "MONEY": "financial",
        "CARDINAL": "number",
        "ORDINAL": "number",
    }

    # Only keep entity types that are genuinely PII
    ALLOWED_ENTITY_TYPES = {"PERSON", "GPE", "LOC", "DATE", "MONEY"}
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        super().__init__(name="ner")
        try:
            log.info(f"Loading spaCy model: {model_name}")
            self.nlp = spacy.load(model_name)
            log.info("spaCy model loaded successfully")
        except OSError:
            log.warning(f"spaCy model {model_name} not found, falling back to en_core_web_sm...")
            try:
                self.nlp = spacy.load("en_core_web_sm")
                log.warning("Using en_core_web_sm as fallback")
            except OSError:
                log.error("Failed to load any spaCy model")
                raise
    
    async def detect(self, text: str, context: Dict[str, Any] = None) -> List[Detection]:
        """
        Detect PII using NER

        Args:
            text: Text to analyze
            context: Optional context (page_number, etc.)

        Returns:
            List of Detection objects
        """
        detections = []
        page_number = context.get('page_number') if context else None
        
        log.debug(f"NERDetector: Processing {len(text)} characters")
        
        doc = await asyncio.to_thread(self.nlp, text)
        
        for ent in doc.ents:
            # Skip entity types that aren't genuinely PII
            if ent.label_ not in self.ALLOWED_ENTITY_TYPES:
                continue

            # Strip whitespace from entity text and adjust positions accordingly
            original_text = ent.text
            stripped_text = original_text.strip()

            if not stripped_text or len(stripped_text) < 3:
                continue

            leading_spaces = len(original_text) - len(original_text.lstrip())
            start_pos = ent.start_char + leading_spaces
            end_pos = start_pos + len(stripped_text)

            pii_type = self.ENTITY_TYPE_MAPPING.get(ent.label_, ent.label_.lower())
            confidence = self._calculate_confidence(ent, stripped_text)
            
            detection = self._create_detection(
                pii_type=pii_type,
                value=stripped_text,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=confidence,
                page_number=page_number
            )
            detections.append(detection)
        
        log.info(f"NERDetector: Found {len(detections)} entities")
        return detections
    
    def _calculate_confidence(self, entity, stripped_text: str = None) -> float:
        """Calculate confidence score for an entity"""
        base_confidence = {
            "PERSON": 0.9,
            "GPE": 0.8,
            "LOC": 0.8,
            "DATE": 0.7,
            "MONEY": 0.75,
        }.get(entity.label_, 0.7)
        
        text_to_check = stripped_text if stripped_text else entity.text
        length_factor = min(len(text_to_check) / 10.0, 1.0)
        cap_factor = 1.0 if (text_to_check and text_to_check[0].isupper()) else 0.9
        
        return min(base_confidence * (0.7 + 0.3 * length_factor) * cap_factor, 1.0)
    
    def get_supported_entities(self) -> List[str]:
        return list(self.nlp.pipe_labels.get('ner', []))