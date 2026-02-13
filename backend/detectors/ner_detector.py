"""
Named Entity Recognition (NER) detector using spaCy
"""
from typing import List, Dict, Any
import spacy
from detectors.base import BaseDetector
from models.schemas import Detection
from core.logger import log


class NERDetector(BaseDetector):
    """Detects PII using spaCy Named Entity Recognition"""
    
    # Map spaCy entity types to our PII types
    ENTITY_TYPE_MAPPING = {
        "PERSON": "name",
        "ORG": "organization",
        "GPE": "location",  # Geo-Political Entity
        "LOC": "location",
        "DATE": "date",
        "MONEY": "financial",
        "CARDINAL": "number",
        "ORDINAL": "number",
    }
    
    def __init__(self, model_name: str = "en_core_web_trf"):
        super().__init__(name="ner")
        
        try:
            log.info(f"Loading spaCy model: {model_name}")
            self.nlp = spacy.load(model_name)
            log.info("spaCy model loaded successfully")
        except OSError:
            log.error(f"spaCy model {model_name} not found. Downloading...")
            # Fallback to smaller model if transformer not available
            try:
                self.nlp = spacy.load("en_core_web_sm")
                log.warning("Using en_core_web_sm as fallback")
            except:
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
        
        # Process text with spaCy
        doc = self.nlp(text)
        
        for ent in doc.ents:
            # Map spaCy entity type to our PII type
            pii_type = self.ENTITY_TYPE_MAPPING.get(ent.label_, ent.label_.lower())
            
            # Calculate confidence based on entity type and length
            confidence = self._calculate_confidence(ent)
            
            detection = self._create_detection(
                pii_type=pii_type,
                value=ent.text,
                start_pos=ent.start_char,
                end_pos=ent.end_char,
                confidence=confidence,
                page_number=page_number
            )
            detections.append(detection)
        
        log.info(f"NERDetector: Found {len(detections)} entities")
        return detections
    
    def _calculate_confidence(self, entity) -> float:
        """
        Calculate confidence score for an entity
        
        Args:
            entity: spaCy entity object
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence on entity type
        base_confidence = {
            "PERSON": 0.9,
            "ORG": 0.85,
            "GPE": 0.8,
            "LOC": 0.8,
            "DATE": 0.7,
            "MONEY": 0.75,
        }.get(entity.label_, 0.7)
        
        # Adjust based on entity length (very short entities less reliable)
        length_factor = min(len(entity.text) / 10.0, 1.0)
        
        # Adjust based on capitalization (proper nouns more reliable)
        if entity.text[0].isupper():
            cap_factor = 1.0
        else:
            cap_factor = 0.9
        
        # Combine factors
        confidence = base_confidence * (0.7 + 0.3 * length_factor) * cap_factor
        
        return min(confidence, 1.0)
    
    def get_supported_entities(self) -> List[str]:
        """Get list of entity types the model can detect"""
        return list(self.nlp.pipe_labels.get('ner', []))