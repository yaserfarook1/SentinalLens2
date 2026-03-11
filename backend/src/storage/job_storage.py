"""
In-Memory Job Storage for Audit Execution

Stores audit job metadata, results, and progress updates.
In production, this would be replaced with persistent storage (Blob Storage, Database).
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

from src.models.schemas import AuditJobMetadata, Report, JobStatus, ProgressUpdate

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """Complete job record including metadata and results"""
    job_id: str
    workspace_id: str
    subscription_id: str
    resource_group: str
    workspace_name: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    report: Optional[Report] = None
    progress_updates: List[ProgressUpdate] = field(default_factory=list)
    # Blob storage fields
    report_blob_url: Optional[str] = None
    report_saved_at: Optional[datetime] = None
    report_expires_at: Optional[datetime] = None


class JobStorage:
    """In-memory job storage with concurrent access support"""

    def __init__(self):
        self.jobs: Dict[str, JobRecord] = {}
        self.lock = asyncio.Lock()
        logger.info("[STORAGE] Job storage initialized")

    async def create_job(
        self,
        job_id: str,
        workspace_id: str,
        subscription_id: str,
        resource_group: str,
        workspace_name: str
    ) -> AuditJobMetadata:
        """
        Create a new job record.

        Args:
            job_id: Unique job identifier
            workspace_id: Sentinel workspace ID
            subscription_id: Azure subscription ID
            resource_group: Azure resource group
            workspace_name: Workspace display name

        Returns:
            Job metadata
        """
        async with self.lock:
            now = datetime.utcnow()
            job = JobRecord(
                job_id=job_id,
                workspace_id=workspace_id,
                subscription_id=subscription_id,
                resource_group=resource_group,
                workspace_name=workspace_name,
                status=JobStatus.QUEUED,
                created_at=now
            )
            self.jobs[job_id] = job

            logger.info(
                f"[STORAGE] Job created: job_id={job_id} "
                f"workspace={workspace_name} "
                f"resource_group={resource_group}"
            )

        return AuditJobMetadata(
            job_id=job_id,
            workspace_id=workspace_id,
            status=JobStatus.QUEUED,
            created_at=now,
            error_message=None,
            report_url=None
        )

    async def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Get job record by ID"""
        async with self.lock:
            return self.jobs.get(job_id)

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """Update job status"""
        async with self.lock:
            if job_id not in self.jobs:
                logger.error(f"[STORAGE] Job not found: {job_id}")
                return False

            job = self.jobs[job_id]
            old_status = job.status
            job.status = status
            job.error_message = error_message

            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status == JobStatus.COMPLETED:
                job.completed_at = datetime.utcnow()

            logger.info(
                f"[STORAGE] Job status updated: job_id={job_id} "
                f"{old_status.value} → {status.value}"
            )
            return True

    async def save_report(self, job_id: str, report: Report) -> bool:
        """Save completed report to job"""
        async with self.lock:
            if job_id not in self.jobs:
                logger.error(f"[STORAGE] Job not found for report: {job_id}")
                return False

            job = self.jobs[job_id]
            job.report = report
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            logger.info(
                f"[STORAGE] Report saved: job_id={job_id} "
                f"tables={report.summary.total_tables_analyzed} "
                f"savings=${report.summary.total_annual_savings:,.0f}"
            )
            return True

    async def get_report(self, job_id: str) -> Optional[Report]:
        """Get report for completed job"""
        async with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                logger.error(f"[STORAGE] Job not found: {job_id}")
                return None

            if not job.report:
                logger.warning(f"[STORAGE] No report available: job_id={job_id}")
                return None

            logger.info(f"[STORAGE] Report retrieved: job_id={job_id}")
            return job.report

    async def add_progress_update(
        self,
        job_id: str,
        update: ProgressUpdate
    ) -> bool:
        """Add progress update to job"""
        async with self.lock:
            if job_id not in self.jobs:
                logger.error(f"[STORAGE] Job not found for progress: {job_id}")
                return False

            self.jobs[job_id].progress_updates.append(update)

            logger.debug(
                f"[STORAGE] Progress update added: job_id={job_id} "
                f"step={update.current_step}/{update.total_steps}"
            )
            return True

    async def get_progress_updates(self, job_id: str) -> List[ProgressUpdate]:
        """Get all progress updates for a job"""
        async with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return []
            return job.progress_updates.copy()

    async def get_all_jobs(self) -> List[AuditJobMetadata]:
        """Get metadata for all jobs"""
        async with self.lock:
            result = []
            for job in self.jobs.values():
                # Extract report summary if available
                tables_analyzed = None
                archive_candidates_count = None
                total_monthly_savings = None

                if job.report:
                    tables_analyzed = job.report.summary.total_tables_analyzed
                    archive_candidates_count = len(job.report.archive_candidates)
                    total_monthly_savings = job.report.summary.total_monthly_savings

                result.append(
                    AuditJobMetadata(
                        job_id=job.job_id,
                        workspace_id=job.workspace_id,
                        workspace_name=job.workspace_name,
                        status=job.status,
                        created_at=job.created_at,
                        error_message=job.error_message,
                        report_url=f"/audits/{job.job_id}/report" if job.report else None,
                        # Report summary fields
                        tables_analyzed=tables_analyzed,
                        archive_candidates_count=archive_candidates_count,
                        total_monthly_savings=total_monthly_savings,
                        # Report storage fields
                        report_blob_url=job.report_blob_url,
                        report_saved_at=job.report_saved_at,
                        report_expires_at=job.report_expires_at
                    )
                )
            return result


# Singleton instance
job_storage = JobStorage()
