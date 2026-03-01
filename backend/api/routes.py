"""
API routes for PII masking service
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List
import json
from datetime import datetime
import os
import shutil
from models.schemas import (
    UploadResponse,
    StatusResponse,
    JobStatus,
    ErrorResponse,
    HealthResponse
)
from models.job import job_store, Job
from core.config import settings
from core.logger import log
from api.processor_orchestrator import PIIProcessor

router = APIRouter()
processor = PIIProcessor()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None)
):
    """
    Upload a PDF document for PII detection and masking

    Args:
        file: PDF file to process
        tags: Optional JSON array of PII tags to guide detection

    Returns:
        UploadResponse with job_id and status
    """
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        user_tags = None
        if tags:
            try:
                user_tags = json.loads(tags) if isinstance(tags, str) else tags
            except json.JSONDecodeError:
                user_tags = [t.strip() for t in tags.split(',')]

        log.info(f"Upload request: {file.filename}, tags: {user_tags}")

        job = job_store.create_job(user_tags=user_tags)

        upload_path = os.path.join(settings.UPLOAD_DIR, f"{job.job_id}.pdf")
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        job.original_file_path = upload_path
        job.update_status(JobStatus.PROCESSING)
        job_store.update_job(job)

        log.info(f"File saved: {upload_path}, job_id: {job.job_id}")

        try:
            await processor.process_job(job)
        except Exception as e:
            log.error(f"Processing failed for job {job.job_id}: {str(e)}")
            job.update_status(JobStatus.FAILED, error_message=str(e))
            job_store.update_job(job)

        return UploadResponse(
            job_id=job.job_id,
            status=job.status,
            message="File uploaded and processing started"
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during file upload")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get processing status for a job"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        processing_time=job.processing_time,
        detections_count=job.get_detections_count() if job.status == JobStatus.COMPLETED else None,
        error_message=job.error_message
    )


@router.get("/download/{job_id}")
async def download_masked_pdf(job_id: str):
    """Download the masked PDF"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed. Current status: {job.status}")

    if not job.masked_file_path or not os.path.exists(job.masked_file_path):
        raise HTTPException(status_code=404, detail="Masked file not found")

    real_path = os.path.realpath(job.masked_file_path)
    if not real_path.startswith(os.path.realpath(settings.OUTPUT_DIR)):
        log.error(f"Path traversal attempt detected for job {job_id}")
        raise HTTPException(status_code=404, detail="Masked file not found")

    return FileResponse(
        job.masked_file_path,
        media_type="application/pdf",
        filename=f"masked_{job.job_id}.pdf"
    )


@router.get("/report/{job_id}")
async def get_detection_report(job_id: str):
    """
    Get detailed detection report including extracted text for debugging.

    Args:
        job_id: Job identifier

    Returns:
        Detection report with findings and extracted text
    """
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed. Current status: {job.status}")

    def mask_pii_value(value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    for d in job.detections:
        log.info(f"Value: {d.value}, Masked: {mask_pii_value(d.value)}, Type: {d.type}, Confidence: {d.confidence}")

    return {
        "job_id": job.job_id,
        "total_detections": job.get_detections_count(),
        "detections_by_type": job.get_detections_by_type(),
        "detections": [
            {
                "type": d.type,
                "value": mask_pii_value(d.value),
                "start_pos": d.start_pos,
                "end_pos": d.end_pos,
                "confidence": d.confidence,
                "detector": d.detector,
                "page_number": d.page_number
            }
            for d in job.detections
        ],
        # Extracted text included for debugging — shows exactly what docling pulled from the PDF
        "extracted_text": job.metadata.get("extracted_text"),
        "metadata": job.metadata,
        "processing_time": job.processing_time
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    from detectors.slm_detector import SLMDetector

    try:
        slm = SLMDetector()
        ollama_healthy = await slm.check_ollama_health()
        ollama_status = "connected" if ollama_healthy else "unavailable"
    except Exception as e:
        log.warning(f"Ollama health check failed: {e}")
        ollama_status = "error"

    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        ollama_status=ollama_status,
        timestamp=datetime.now()
    )


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Cannot delete job while processing")

    try:
        if job.original_file_path and os.path.exists(job.original_file_path):
            os.remove(job.original_file_path)
        if job.masked_file_path and os.path.exists(job.masked_file_path):
            os.remove(job.masked_file_path)
    except OSError as e:
        log.warning(f"Failed to delete files for job {job_id}: {e}")

    job_store.delete_job(job_id)
    return {"message": f"Job {job_id} deleted successfully"}