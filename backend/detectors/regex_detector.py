"""
Regex-based PII detector for patterns like SSN, email, phone, credit cards
"""
import re
from typing import List, Dict, Any
from .base import BaseDetector
from models.schemas import Detection
from core.config import settings
from core.logger import log


class RegexDetector(BaseDetector):
    """Detects PII using regular expressions"""
    
    def __init__(self):
        super().__init__(name="regex")
        self.patterns = settings.REGEX_PATTERNS.copy()
        
        # Compile patterns for efficiency
        self.compiled_patterns = {
            pii_type: re.compile(pattern)
            for pii_type, pattern in self.patterns.items()
        }
    
    async def detect(self, text: str, context: Dict[str, Any] = None) -> List[Detection]:
        """
        Detect PII using regex patterns
        """
        detections = []
        page_number = context.get('page_number') if context else None
        
        log.debug(f"RegexDetector: Scanning {len(text)} characters")
        
        for pii_type, pattern in self.compiled_patterns.items():
            matches = pattern.finditer(text)
            
            for match in matches:
                value = match.group(0)
                
                if pii_type == "credit_card" and not self._validate_credit_card(value):
                    continue
                
                if pii_type == "ssn" and not self._validate_ssn(value):
                    continue

                if pii_type == "phone" and not self._validate_phone(value, text, match.start()):
                    continue
                
                detection = self._create_detection(
                    pii_type=pii_type,
                    value=value,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=1.0,
                    page_number=page_number
                )
                detections.append(detection)
        
        log.info(f"RegexDetector: Found {len(detections)} matches")
        return detections

    def _validate_phone(self, value: str, full_text: str, match_start: int) -> bool:
        """
        Validate phone number — reject if preceded by NPI/policy/ID-like labels
        """
        # Look at up to 20 chars before the match for context
        context_start = max(0, match_start - 30)
        preceding = full_text[context_start:match_start].upper()

        # Reject if it looks like an ID/policy/NPI number
        false_positive_labels = ["NPI", "POLICY", "MEMBER ID", "ACCOUNT", "POLICY NUMBER"]
        for label in false_positive_labels:
            if label in preceding:
                log.debug(f"RegexDetector: Skipping phone match '{value}' — looks like {label}")
                return False

        return True
    
    def _validate_credit_card(self, number: str) -> bool:
        """Validate credit card using Luhn algorithm"""
        number = re.sub(r'[\s-]', '', number)
        
        if not number.isdigit() or len(number) < 13 or len(number) > 19:
            return False
        
        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10
        
        return luhn_checksum(number) == 0
    
    def _validate_ssn(self, ssn: str) -> bool:
        """Validate SSN format"""
        digits = ssn.replace('-', '')
        
        if len(digits) != 9 or not digits.isdigit():
            return False
        
        area = int(digits[:3])
        if area == 0 or area == 666 or area >= 900:
            return False
        
        group = int(digits[3:5])
        if group == 0:
            return False
        
        serial = int(digits[5:])
        if serial == 0:
            return False
        
        return True
    
    def add_pattern(self, pii_type: str, pattern: str):
        """Add a custom regex pattern"""
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            log.error(f"Invalid regex pattern for {pii_type}: {e}")
            raise ValueError(f"Invalid regex pattern: {e}") from e
        
        self.patterns[pii_type] = pattern
        self.compiled_patterns[pii_type] = compiled
        log.info(f"Added custom pattern for {pii_type}")

    def remove_pattern(self, pii_type: str):
        """Remove a pattern"""
        if pii_type in self.patterns:
            del self.patterns[pii_type]
            del self.compiled_patterns[pii_type]
            log.info(f"Removed pattern for {pii_type}")