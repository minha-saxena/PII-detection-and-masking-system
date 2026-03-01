"""
Main processing pipeline orchestrator
"""
import os
from typing import List
from datetime import datetime

from models.job import Job
from models.schemas import JobStatus, Detection
from utils.processor import PDFProcessor
from utils.reconstructor import PDFReconstructor
from detectors import (
    DetectorOrchestrator, 
    RegexDetector, 
    NERDetector, 
    SLMDetector
)
from masking.masker import MaskingEngine
from core.config import settings
from core.logger import log
import asyncio


class PIIProcessor:
    """Main PII processing pipeline"""
    
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.pdf_reconstructor = PDFReconstructor()
        
        self.orchestrator = DetectorOrchestrator()
        
        if settings.ENABLE_REGEX_DETECTOR:
            self.orchestrator.register_detector(RegexDetector())
            log.info("✓ RegexDetector registered")
        
        if settings.ENABLE_NER_DETECTOR:
            self.orchestrator.register_detector(NERDetector())
            log.info("✓ NERDetector registered")
        
        if settings.ENABLE_SLM_DETECTOR:
            self.orchestrator.register_detector(SLMDetector())
            log.info("✓ SLMDetector registered")
        
        self.masker = MaskingEngine()
        
        log.info("PIIProcessor initialized with all components")
    
    async def process_job(self, job: Job) -> Job:
        """Process a complete job from PDF to masked output"""
        start_time = datetime.now()
        
        try:
            log.info(f"=" * 60)
            log.info(f"Processing job: {job.job_id}")
            log.info(f"=" * 60)
            
            # Step 1: Extract text from PDF
            log.info("Step 1: Extracting text from PDF...")
            text, pdf_metadata = await asyncio.to_thread(
                self.pdf_processor.extract_text,
                job.original_file_path
            )
            job.metadata['pdf_metadata'] = pdf_metadata

            # Store extracted text for debugging via report endpoint
            job.metadata['extracted_text'] = text

            log.info(f"✓ Extracted {len(text)} characters from {pdf_metadata['num_pages']} pages")
            
            # Step 2: Detect PII
            log.info("Step 2: Detecting PII...")
            context = {
                'user_tags': job.user_tags,
                'page_number': 1
            }
            
            detections = await self.orchestrator.detect_all(text, context)
            
            filtered_detections = [
                d for d in detections 
                if d.confidence >= settings.CONFIDENCE_THRESHOLD
            ]
            
            log.info(f"✓ Found {len(detections)} detections ({len(filtered_detections)} above threshold)")
            
            for detection in filtered_detections:
                job.add_detection(detection)
            
            job.metadata['detection_stats'] = {
                'total_found': len(detections),
                'above_threshold': len(filtered_detections),
                'by_detector': self._count_by_detector(filtered_detections),
                'by_type': job.get_detections_by_type()
            }
            
            # Step 3: Mask text
            log.info("Step 3: Masking detected PII...")
            masked_text, masking_stats = self.masker.mask_text(
                text, 
                filtered_detections
            )
            job.metadata['masking_stats'] = masking_stats
            log.info(f"✓ Masked {masking_stats['total_masked']} items")
            
            # Step 4: Create masked PDF
            log.info("Step 4: Creating masked PDF...")
            os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(
                settings.OUTPUT_DIR,
                f"{job.job_id}_masked.pdf"
            )
            
            self.pdf_reconstructor.create_simple_masked_pdf(
                text_content=text,
                detections=filtered_detections,
                output_path=output_path
            )
            
            job.masked_file_path = output_path
            log.info(f"✓ Masked PDF created: {output_path}")
            
            job.update_status(JobStatus.COMPLETED)
            job.calculate_processing_time()
            
            log.info("=" * 60)
            log.info(f"✓ Job {job.job_id} completed in {job.processing_time:.2f}s")
            log.info(f"  - Detections: {len(filtered_detections)}")
            log.info(f"  - Pages: {pdf_metadata['num_pages']}")
            log.info("=" * 60)
            
            return job
        
        except Exception as e:
            log.error(f"✗ Job {job.job_id} failed: {str(e)}", exc_info=True)
            job.update_status(JobStatus.FAILED, error_message=str(e))
            raise
    
    def _count_by_detector(self, detections: List[Detection]) -> dict:
        from collections import Counter
        return dict(Counter([d.detector for d in detections]))
    
    async def process_page_by_page(self, job: Job) -> Job:
        """Alternative: Process PDF page by page for better accuracy"""
        try:
            log.info(f"Processing job {job.job_id} page by page")
            
            pages_data = self.pdf_processor.extract_by_page(job.original_file_path)
            all_detections = []
            
            for page_data in pages_data:
                context = {
                    'user_tags': job.user_tags,
                    'page_number': page_data['page_number']
                }
                
                page_detections = await self.orchestrator.detect_all(
                    page_data['text'],
                    context
                )
                
                filtered = [
                    d for d in page_detections 
                    if d.confidence >= settings.CONFIDENCE_THRESHOLD
                ]
                
                all_detections.extend(filtered)
                log.info(f"Page {page_data['page_number']}: {len(filtered)} detections")

            for detection in all_detections:
                job.add_detection(detection)
            
            full_text = "\n".join(p['text'] for p in pages_data)
            job.metadata['extracted_text'] = full_text

            masked_text, masking_stats = self.masker.mask_text(full_text, all_detections)
            job.metadata['masking_stats'] = masking_stats

            output_path = os.path.join(settings.OUTPUT_DIR, f"{job.job_id}_masked.pdf")
            os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
            self.pdf_reconstructor.create_simple_masked_pdf(
                text_content=full_text,
                detections=all_detections,
                output_path=output_path
            )
            job.masked_file_path = output_path
            job.update_status(JobStatus.COMPLETED)
            job.calculate_processing_time()
            
            return job
        
        except Exception as e:
            log.error(f"Page-by-page processing failed: {str(e)}", exc_info=True)
            job.update_status(JobStatus.FAILED, error_message=str(e))
            raise