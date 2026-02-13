"""
PII Masking engine
"""
from typing import List, Dict, Tuple
from app.models.schemas import Detection
from app.core.logger import log


class MaskingEngine:
    """Handles PII masking strategies"""
    
    def __init__(self, mask_char: str = "█"):
        """
        Initialize masking engine
        
        Args:
            mask_char: Character to use for masking (default: black box)
        """
        self.mask_char = mask_char
        log.info(f"MaskingEngine initialized with mask_char: {mask_char}")
    
    def mask_text(
        self, 
        text: str, 
        detections: List[Detection],
        preserve_length: bool = True
    ) -> Tuple[str, Dict]:
        """
        Mask PII in text
        
        Args:
            text: Original text
            detections: List of PII detections
            preserve_length: If True, mask with same length as original
        
        Returns:
            Tuple of (masked_text, masking_stats)
        """
        if not detections:
            log.info("No detections to mask")
            return text, {"total_masked": 0, "chars_masked": 0}
        
        log.info(f"Masking {len(detections)} detections in {len(text)} chars")
        
        # Sort detections by position (reverse to avoid offset issues)
        sorted_detections = sorted(
            detections, 
            key=lambda d: d.start_pos, 
            reverse=True
        )
        
        # Convert text to list for easier manipulation
        text_chars = list(text)
        total_chars_masked = 0
        
        # Apply masking
        for detection in sorted_detections:
            start = detection.start_pos
            end = detection.end_pos
            
            # Validate positions
            if start < 0 or end > len(text) or start >= end:
                log.warning(f"Invalid detection positions: {start}-{end}")
                continue
            
            # Calculate mask
            if preserve_length:
                mask_length = end - start
            else:
                mask_length = min(10, end - start)  # Max 10 chars
            
            mask = self.mask_char * mask_length
            
            # Apply mask
            text_chars[start:end] = list(mask)
            total_chars_masked += mask_length
            
            log.debug(f"Masked '{detection.value}' at {start}-{end}")
        
        masked_text = ''.join(text_chars)
        
        stats = {
            "total_masked": len(sorted_detections),
            "chars_masked": total_chars_masked,
            "original_length": len(text),
            "masked_length": len(masked_text),
        }
        
        log.info(f"Masking complete: {stats}")
        return masked_text, stats
    
    def mask_with_placeholder(
        self, 
        text: str, 
        detections: List[Detection]
    ) -> Tuple[str, Dict]:
        """
        Mask with placeholders like [NAME], [SSN], etc.
        
        Args:
            text: Original text
            detections: List of detections
        
        Returns:
            Tuple of (masked_text, masking_stats)
        """
        log.info(f"Masking with placeholders: {len(detections)} detections")
        
        # Sort by position (reverse)
        sorted_detections = sorted(
            detections,
            key=lambda d: d.start_pos,
            reverse=True
        )
        
        text_chars = list(text)
        
        for detection in sorted_detections:
            start = detection.start_pos
            end = detection.end_pos
            
            # Create placeholder
            placeholder = f"[{detection.type.upper()}]"
            
            # Replace
            text_chars[start:end] = list(placeholder)
        
        masked_text = ''.join(text_chars)
        
        stats = {
            "total_masked": len(sorted_detections),
            "original_length": len(text),
            "masked_length": len(masked_text),
        }
        
        return masked_text, stats
    
    def mask_with_hash(
        self,
        text: str,
        detections: List[Detection]
    ) -> Tuple[str, Dict]:
        """
        Mask with hash values (for reversible masking)
        
        Args:
            text: Original text
            detections: List of detections
        
        Returns:
            Tuple of (masked_text, hash_mapping)
        """
        import hashlib
        
        log.info(f"Masking with hashes: {len(detections)} detections")
        
        sorted_detections = sorted(
            detections,
            key=lambda d: d.start_pos,
            reverse=True
        )
        
        text_chars = list(text)
        hash_mapping = {}
        
        for detection in sorted_detections:
            start = detection.start_pos
            end = detection.end_pos
            original_value = detection.value
            
            # Create hash
            hash_value = hashlib.sha256(
                original_value.encode()
            ).hexdigest()[:8]
            
            # Store mapping
            hash_mapping[hash_value] = {
                "original": original_value,
                "type": detection.type,
                "position": [start, end]
            }
            
            # Create masked value
            masked = f"[HASH_{hash_value}]"
            
            # Replace
            text_chars[start:end] = list(masked)
        
        masked_text = ''.join(text_chars)
        
        return masked_text, hash_mapping
    
    def get_masking_preview(
        self,
        text: str,
        detections: List[Detection],
        context_chars: int = 20
    ) -> List[Dict]:
        """
        Generate preview of what will be masked
        
        Args:
            text: Original text
            detections: List of detections
            context_chars: Number of context chars before/after
        
        Returns:
            List of preview items
        """
        previews = []
        
        for detection in detections:
            start = detection.start_pos
            end = detection.end_pos
            
            # Extract context
            context_start = max(0, start - context_chars)
            context_end = min(len(text), end + context_chars)
            
            before = text[context_start:start]
            matched = text[start:end]
            after = text[end:context_end]
            
            # Create masked version
            masked = self.mask_char * (end - start)
            
            preview = {
                "type": detection.type,
                "original_value": matched,
                "before_context": before,
                "after_context": after,
                "masked_preview": f"{before}{masked}{after}",
                "confidence": detection.confidence,
            }
            
            previews.append(preview)
        
        return previews