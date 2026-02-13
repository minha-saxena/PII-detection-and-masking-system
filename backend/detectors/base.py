"""
Base detector interface and common utilities
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from models.schemas import Detection


class BaseDetector(ABC):
    """Abstract base class for all PII detectors"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def detect(self, text: str, context: Dict[str, Any] = None) -> List[Detection]:
        """
        Detect PII in the given text
        
        Args:
            text: Text to analyze
            context: Additional context (e.g., user tags, page number)
        
        Returns:
            List of Detection objects
        """
        pass
    
    def _create_detection(
        self,
        pii_type: str,
        value: str,
        start_pos: int,
        end_pos: int,
        confidence: float = 1.0,
        page_number: int = None
    ) -> Detection:
        """Helper to create a Detection object"""
        return Detection(
            type=pii_type,
            value=value,
            start_pos=start_pos,
            end_pos=end_pos,
            confidence=confidence,
            detector=self.name,
            page_number=page_number
        )
    
    def _merge_overlapping_detections(self, detections: List[Detection]) -> List[Detection]:
        """
        Merge overlapping detections, keeping the one with higher confidence
        
        Args:
            detections: List of detections to merge
        
        Returns:
            Merged list without overlaps
        """
        if not detections:
            return []
        
        # Sort by start position
        sorted_detections = sorted(detections, key=lambda d: d.start_pos)
        merged = [sorted_detections[0]]
        
        for current in sorted_detections[1:]:
            previous = merged[-1]
            
            # Check for overlap
            if current.start_pos <= previous.end_pos:
                # Keep detection with higher confidence
                if current.confidence > previous.confidence:
                    merged[-1] = current
                # If same confidence, keep longer match
                elif current.confidence == previous.confidence:
                    if (current.end_pos - current.start_pos) > (previous.end_pos - previous.start_pos):
                        merged[-1] = current
            else:
                merged.append(current)
        
        return merged


class DetectorOrchestrator:
    """Orchestrates multiple detectors"""
    
    def __init__(self):
        self.detectors: List[BaseDetector] = []
    
    def register_detector(self, detector: BaseDetector):
        """Register a detector"""
        self.detectors.append(detector)
    
    async def detect_all(self, text: str, context: Dict[str, Any] = None) -> List[Detection]:
        """
        Run all registered detectors
        
        Args:
            text: Text to analyze
            context: Additional context
        
        Returns:
            Combined list of all detections
        """
        all_detections = []
        
        for detector in self.detectors:
            try:
                detections = await detector.detect(text, context)
                all_detections.extend(detections)
            except Exception as e:
                from core.logger import log
                log.error(f"Detector {detector.name} failed: {str(e)}")
                continue
        
        # Merge overlapping detections
        return self._consolidate_detections(all_detections)
    
    def _consolidate_detections(self, detections: List[Detection]) -> List[Detection]:
        """
        Consolidate detections from multiple sources
        
        Strategy:
        1. Remove exact duplicates
        2. Merge overlapping detections (keep higher confidence)
        3. Sort by position
        """
        if not detections:
            return []
        
        # Remove exact duplicates based on position
        unique_detections = []
        seen_positions = set()
        
        for detection in detections:
            pos_key = (detection.start_pos, detection.end_pos)
            if pos_key not in seen_positions:
                unique_detections.append(detection)
                seen_positions.add(pos_key)
            else:
                # Update if this has higher confidence
                for i, existing in enumerate(unique_detections):
                    if (existing.start_pos == detection.start_pos and 
                        existing.end_pos == detection.end_pos and
                        detection.confidence > existing.confidence):
                        unique_detections[i] = detection
                        break
        
        # Sort by start position
        sorted_detections = sorted(unique_detections, key=lambda d: d.start_pos)
        
        # Merge overlapping
        merged = []
        for detection in sorted_detections:
            if not merged:
                merged.append(detection)
                continue
            
            previous = merged[-1]
            
            # Check overlap
            if detection.start_pos <= previous.end_pos:
                # Overlapping - keep higher confidence
                if detection.confidence > previous.confidence:
                    merged[-1] = detection
                elif detection.confidence == previous.confidence:
                    # Keep longer match
                    if (detection.end_pos - detection.start_pos) > (previous.end_pos - previous.start_pos):
                        merged[-1] = detection
            else:
                merged.append(detection)
        
        return merged