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
        
        Args:
            text: Text to analyze
            context: Optional context (page_number, etc.)
        
        Returns:
            List of Detection objects
        """
        detections = []
        page_number = context.get('page_number') if context else None
        
        log.debug(f"RegexDetector: Scanning {len(text)} characters")
        
        for pii_type, pattern in self.compiled_patterns.items():
            matches = pattern.finditer(text)
            
            for match in matches:
                value = match.group(0)
                
                # Additional validation for specific types
                if pii_type == "credit_card" and not self._validate_credit_card(value):
                    continue
                
                if pii_type == "ssn" and not self._validate_ssn(value):
                    continue
                
                detection = self._create_detection(
                    pii_type=pii_type,
                    value=value,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=1.0,  # Regex matches are high confidence
                    page_number=page_number
                )
                detections.append(detection)
        
        log.info(f"RegexDetector: Found {len(detections)} matches")
        return detections
    
    def _validate_credit_card(self, number: str) -> bool:
        """
        Validate credit card using Luhn algorithm
        
        Args:
            number: Credit card number string
        
        Returns:
            True if valid, False otherwise
        """
        # Remove spaces and dashes
        number = re.sub(r'[\s-]', '', number)
        
        # Must be numeric and 13-19 digits
        if not number.isdigit() or len(number) < 13 or len(number) > 19:
            return False
        
        # Luhn algorithm
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
        """
        Validate SSN format
        
        Args:
            ssn: SSN string
        
        Returns:
            True if valid format, False otherwise
        """
        # Remove dashes
        digits = ssn.replace('-', '')
        
        # Must be 9 digits
        if len(digits) != 9 or not digits.isdigit():
            return False
        
        # Basic validation: no area number 000, 666, or 900-999
        area = int(digits[:3])
        if area == 0 or area == 666 or area >= 900:
            return False
        
        # No group number 00
        group = int(digits[3:5])
        if group == 0:
            return False
        
        # No serial number 0000
        serial = int(digits[5:])
        if serial == 0:
            return False
        
        return True
    
    def add_pattern(self, pii_type: str, pattern: str):
        """
        Add a custom regex pattern
        
        Args:
            pii_type: Type of PII
            pattern: Regex pattern string
        """
        self.patterns[pii_type] = pattern
        self.compiled_patterns[pii_type] = re.compile(pattern)
        log.info(f"Added custom pattern for {pii_type}")
    
    def remove_pattern(self, pii_type: str):
        """
        Remove a pattern
        
        Args:
            pii_type: Type of PII to remove
        """
        if pii_type in self.patterns:
            del self.patterns[pii_type]
            del self.compiled_patterns[pii_type]
            log.info(f"Removed pattern for {pii_type}")