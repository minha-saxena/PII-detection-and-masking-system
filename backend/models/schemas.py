"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    """Job processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PIIType(str, Enum):
    """Types of PII that can be detected"""
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    MEDICAL_CONDITION = "medical_condition"
    MEDICATION = "medication"
    CUSTOM = "custom"


class Detection(BaseModel):
    """Individual PII detection"""
    type: str = Field(..., description="Type of PII detected")
    value: str = Field(..., description="Original value detected")
    start_pos: int = Field(..., description="Start position in text")
    end_pos: int = Field(..., description="End position in text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    detector: str = Field(..., description="Which detector found this (regex/ner/slm)")
    page_number: Optional[int] = Field(None, description="Page number if available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "ssn",
                "value": "123-45-6789",
                "start_pos": 150,
                "end_pos": 161,
                "confidence": 1.0,
                "detector": "regex",
                "page_number": 1
            }
        }


class UploadRequest(BaseModel):
    """Request model for file upload (form data)"""
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional PII tags to guide detection"
    )
    
    @validator('tags', pre=True)
    def parse_tags(cls, v):
        """Parse tags from string if needed"""
        if isinstance(v, str):
            # Handle JSON string or comma-separated
            import json
            try:
                return json.loads(v)
            except:
                return [tag.strip() for tag in v.split(',')]
        return v


class UploadResponse(BaseModel):
    """Response after file upload"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123def456",
                "status": "processing",
                "message": "File uploaded successfully. Processing started."
            }
        }


class StatusResponse(BaseModel):
    """Response for status check"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    detections_count: Optional[int] = Field(None, description="Number of PIIs detected")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123def456",
                "status": "completed",
                "created_at": "2024-02-11T10:30:00",
                "updated_at": "2024-02-11T10:30:15",
                "processing_time": 12.5,
                "detections_count": 7,
                "error_message": None
            }
        }


class DetectionReport(BaseModel):
    """Detailed detection report"""
    job_id: str
    total_detections: int
    detections_by_type: Dict[str, int]
    detections: List[Detection]
    processing_details: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123def456",
                "total_detections": 7,
                "detections_by_type": {
                    "name": 2,
                    "email": 1,
                    "ssn": 1,
                    "phone": 3
                },
                "detections": [],
                "processing_details": {
                    "regex_matches": 4,
                    "ner_matches": 2,
                    "slm_matches": 1
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "FileProcessingError",
                "message": "Failed to process PDF file",
                "detail": "Invalid PDF format or corrupted file"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    ollama_status: str = Field(..., description="Ollama service status")
    timestamp: datetime = Field(..., description="Current timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "ollama_status": "connected",
                "timestamp": "2024-02-11T10:30:00"
            }
        }