"""
Job tracking and state management
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .schemas import JobStatus, Detection
import uuid
import threading


@dataclass
class Job:
    """Job state tracker"""

    # Core identity
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
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

    # Internal locks (not part of dataclass repr/init)
    _detections_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False
    )

    # --------------------
    # State management
    # --------------------

    def update_status(self, status: JobStatus, error_message: Optional[str] = None):
        """Update job status safely"""
        self.status = status
        self.updated_at = datetime.now()
        if error_message is not None:
            self.error_message = error_message

    # --------------------
    # Detection handling
    # --------------------

    def add_detection(self, detection: Detection):
        """Add a detection to the job (thread-safe)"""
        with self._detections_lock:
            self.detections.append(detection)

    def get_detections_count(self) -> int:
        """Get total number of detections"""
        return len(self.detections)

    def get_detections_by_type(self) -> Dict[str, int]:
        """Get count of detections grouped by type"""
        from collections import Counter
        return dict(
            Counter(
                d.type.upper() if isinstance(d.type, str) else str(d.type)
                for d in self.detections
            )
        )

    # --------------------
    # Metrics
    # --------------------

    def calculate_processing_time(self):
        """Calculate total processing time"""
        self.processing_time = (
            datetime.now() - self.created_at
        ).total_seconds()


# =====================================================================
# Job Store (In-memory – replace with Redis in Phase 2)
# =====================================================================

class JobStore:
    """In-memory job storage"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(JobStore, cls).__new__(cls)
            cls._instance._jobs = {}
        return cls._instance

    # --------------------
    # CRUD operations
    # --------------------

    def create_job(self, user_tags: Optional[List[str]] = None) -> Job:
        """Create a new job"""
        job = Job(user_tags=user_tags or [])
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job: Job) -> Job:
        """Update existing job"""
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def delete_job(self, job_id: str):
        """Delete a job"""
        with self._lock:
            self._jobs.pop(job_id, None)

    def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        with self._lock:
            return list(self._jobs.values())

    # --------------------
    # Maintenance
    # --------------------

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove jobs older than max_age_hours"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        with self._lock:
            jobs_to_delete = [
                job_id
                for job_id, job in self._jobs.items()
                if job.created_at < cutoff_time
            ]

            for job_id in jobs_to_delete:
                del self._jobs[job_id]

        return len(jobs_to_delete)


# Global job store instance
job_store = JobStore()
