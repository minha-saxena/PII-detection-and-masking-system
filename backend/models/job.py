"""
Job tracking and state management
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from .schemas import JobStatus, Detection
import uuid


@dataclass
class Job:
    """Job state tracker"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4().hex[:12]))
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # File paths
    original_file_path: Optional[str] = None
    masked_file_path: Optional[str] = None
    temp_dir: Optional[str] = None
    
    # Processing data
    user_tags: List[str] = field(default_factory=list)
    detections: List[Detection] = field(default_factory=list)
    processing_time: Optional[float] = None
    
    # Error handling
    error_message: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: JobStatus, error_message: Optional[str] = None):
        """Update job status"""
        self.status = status
        self.updated_at = datetime.now()
        if error_message:
            self.error_message = error_message
    
    def add_detection(self, detection: Detection):
        """Add a detection to the job"""
        self.detections.append(detection)
    
    def get_detections_count(self) -> int:
        """Get total number of detections"""
        return len(self.detections)
    
    def get_detections_by_type(self) -> Dict[str, int]:
        """Get count of detections grouped by type"""
        from collections import Counter
        return dict(Counter([d.type for d in self.detections]))
    
    def calculate_processing_time(self):
        """Calculate total processing time"""
        self.processing_time = (self.updated_at - self.created_at).total_seconds()


class JobStore:
    """In-memory job storage (will replace with Redis in Phase 2)"""
    
    _instance = None
    _jobs: Dict[str, Job] = {}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(JobStore, cls).__new__(cls)
        return cls._instance
    
    def create_job(self, user_tags: Optional[List[str]] = None) -> Job:
        """Create a new job"""
        job = Job(user_tags=user_tags or [])
        self._jobs[job.job_id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self._jobs.get(job_id)
    
    def update_job(self, job: Job):
        """Update existing job"""
        self._jobs[job.job_id] = job
    
    def delete_job(self, job_id: str):
        """Delete a job"""
        if job_id in self._jobs:
            del self._jobs[job_id]
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        return list(self._jobs.values())
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        jobs_to_delete = [
            job_id for job_id, job in self._jobs.items()
            if job.created_at < cutoff_time
        ]
        
        for job_id in jobs_to_delete:
            self.delete_job(job_id)
        
        return len(jobs_to_delete)


# Global job store instance
job_store = JobStore()