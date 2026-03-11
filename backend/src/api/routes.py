"""
FastAPI Routes - SentinelLens REST API

Endpoints:
- GET  /workspaces - List accessible workspaces
- POST /audits - Start new audit job
- GET  /audits/{job_id} - Get audit job status
- GET  /audits/{job_id}/stream - SSE stream of progress
- GET  /audits/{job_id}/report - Get full report
- POST /audits/{job_id}/approve - Approve tier changes
- GET  /audits - List all audit jobs
- GET  /health - Health check
"""

import logging
import json
import os
import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.config import settings
from src.models.schemas import (
    StartAuditRequest, ApprovalRequest, WorkspaceInfo, AuditJobMetadata,
    Report, HealthResponse, ErrorResponse, JobStatus,
    TierType, ConfidenceLevel, ReportSummary, TableRecommendation,
    ConnectorCoverageItem, ReportWarning, ExecutionMetadata,
    SetupCredentialsRequest, ProgressUpdate, AnalyticsRule, PaginatedResponse
)
from src.utils.azure_utils import extract_workspace_details
from src.api.auth import validate_entra_token, require_approval_group, extract_user_info
from src.services.azure_api import azure_api_service
from src.agents.orchestrator import agent_orchestrator
from src.services.report_exporter import report_exporter
from src.storage import job_storage
from src.storage.blob_storage import blob_storage_service
from src.security import pii_masking, prompt_shield
from src.security_middleware import security_middleware
from src.utils.logging import AuditLogger
from fastapi.responses import FileResponse, StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["audit"])


# ===== BACKGROUND ORCHESTRATOR EXECUTION =====
async def _execute_audit_background(
    job_id: str,
    workspace_id: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    days_lookback: int,
    user_id: str,
    user_principal: str
):
    """
    Background task to execute audit orchestrator with comprehensive logging.

    This function:
    1. Updates job status to RUNNING
    2. Executes orchestrator with all 9 steps
    3. Streams progress updates
    4. Saves completed report to storage
    5. Updates job status to COMPLETED
    6. Logs all errors and execution details
    """
    try:
        logger.info(
            f"[ORCHESTRATOR] Starting background execution: job_id={job_id} "
            f"workspace={workspace_name} "
            f"user={user_principal}"
        )

        # Update job status to RUNNING
        await job_storage.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"[ORCHESTRATOR] Job status updated to RUNNING: {job_id}")

        # Execute orchestrator
        logger.info(
            f"[ORCHESTRATOR] Triggering agent orchestrator execution "
            f"(workspace={workspace_name}, resource_group={resource_group}, "
            f"days_lookback={days_lookback})"
        )

        report = await agent_orchestrator.execute_audit(
            job_id=job_id,
            workspace_id=workspace_id,
            subscription_id=subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name,
            days_lookback=days_lookback
        )

        logger.info(
            f"[ORCHESTRATOR] Orchestrator execution completed successfully: "
            f"job_id={job_id} "
            f"tables_analyzed={report.summary.total_tables_analyzed} "
            f"annual_savings=${report.summary.total_annual_savings:,.0f}"
        )

        # Save report to storage
        await job_storage.save_report(job_id, report)
        logger.info(f"[ORCHESTRATOR] Report saved to storage: job_id={job_id}")

        # Update job status to COMPLETED
        await job_storage.update_job_status(job_id, JobStatus.COMPLETED)
        logger.info(f"[ORCHESTRATOR] Job status updated to COMPLETED: {job_id}")

        # Log audit completion event
        AuditLogger.log_event(
            event_type="AUDIT_COMPLETED",
            resource=workspace_id,
            status="SUCCESS",
            user_id=user_id,
            details=f"job_id={job_id}, tables={report.summary.total_tables_analyzed}, "
                    f"savings=${report.summary.total_annual_savings:,.0f}"
        )

        logger.info(
            f"[ORCHESTRATOR] Background execution SUCCEEDED for job_id={job_id}"
        )

    except Exception as e:
        logger.error(
            f"[ORCHESTRATOR] Background execution FAILED for job_id={job_id}: "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True
        )

        # Update job status to FAILED with error message
        await job_storage.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e)
        )
        logger.error(f"[ORCHESTRATOR] Job marked as FAILED: {job_id}")

        # Log audit failure event
        AuditLogger.log_event(
            event_type="AUDIT_FAILED",
            resource=workspace_id,
            status="FAILED",
            user_id=user_id,
            details=f"job_id={job_id}, error={str(e)}"
        )


# ===== HEALTH CHECK =====
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"]
)
async def health_check():
    """Health check endpoint (no authentication required)"""
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.utcnow()
    )


# ===== SETUP & CONFIGURATION =====
@router.post(
    "/setup/credentials",
    summary="Setup app registration credentials",
    description="Configure Azure AD app registration credentials and save to .env.local",
    tags=["setup"]
)
async def setup_credentials(request: SetupCredentialsRequest):
    """
    Setup app registration credentials.

    This endpoint saves the Azure AD app registration credentials to .env.local
    for local development. In production, these should be stored in Azure Key Vault.

    IMPORTANT: This endpoint has NO authentication check (for initial setup only).
    In production, this should be removed or protected.
    """
    try:
        logger.info("[AUDIT] Credential setup requested")

        # Get the backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_local_path = os.path.join(backend_dir, ".env.local")

        # Read existing .env.local if it exists
        env_content = {}
        if os.path.exists(env_local_path):
            logger.info(f"[AUDIT] Reading existing .env.local from {env_local_path}")
            with open(env_local_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_content[key.strip()] = value.strip()

        # Update with new credentials
        env_content["AZURE_CLIENT_ID"] = request.client_id
        env_content["AZURE_CLIENT_SECRET"] = request.client_secret

        # Write back to .env.local
        with open(env_local_path, "w") as f:
            f.write("# Backend Configuration\n")
            f.write("# This file was auto-generated by the setup endpoint\n")
            f.write("# IMPORTANT: Never commit this to Git!\n\n")
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")

        logger.info(f"[AUDIT] Credentials saved to {env_local_path}")

        return {
            "status": "success",
            "message": "Credentials configured successfully",
            "env_file": env_local_path,
            "note": "Please restart the backend for changes to take effect",
            "client_id": request.client_id[:20] + "..." if len(request.client_id) > 20 else request.client_id
        }

    except Exception as e:
        logger.error(f"[AUDIT] Credential setup failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup credentials: {str(e)}"
        )


# ===== WORKSPACE MANAGEMENT =====
@router.get(
    "/workspaces",
    response_model=List[WorkspaceInfo],
    summary="List accessible Sentinel workspaces",
    description="Returns all Sentinel workspaces accessible to the authenticated user"
)
async def get_workspaces(token: dict = Depends(validate_entra_token)):
    """
    List accessible Sentinel workspaces.

    Returns workspaces from subscriptions the user has access to.
    """
    try:
        user_info = extract_user_info(token)
        logger.info(f"[AUDIT] Workspace list requested by: {user_info['user_principal']}")

        # Get list of workspaces from Azure
        try:
            azure_workspaces = await azure_api_service.list_workspaces()
        except Exception as azure_err:
            logger.error(f"[AUDIT] Azure API error: {type(azure_err).__name__}: {str(azure_err)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Azure API error: {str(azure_err)}"
            )

        # Convert to WorkspaceInfo format
        workspaces = [
            WorkspaceInfo(
                workspace_id=ws["workspace_id"],
                workspace_name=ws["workspace_name"],
                subscription_id=ws["subscription_id"],
                resource_group=ws.get("resource_group", "unknown")
            )
            for ws in azure_workspaces
        ]

        logger.info(f"[AUDIT] Returned {len(workspaces)} workspaces")
        return workspaces

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Workspace list failed: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workspace list failed: {str(e)}"
        )


# ===== ANALYTICS RULES =====
@router.get(
    "/rules",
    response_model=List[AnalyticsRule],
    summary="List analytics rules for a workspace",
    description="Returns all enabled analytics rules for the specified Sentinel workspace"
)
async def get_analytics_rules(
    workspace_id: str,
    token: dict = Depends(validate_entra_token)
):
    """
    Get all analytics rules from a Sentinel workspace.

    Returns all enabled analytics rules with their KQL queries.
    """
    try:
        user_info = extract_user_info(token)
        logger.info(f"[AUDIT] Analytics rules requested for workspace: {workspace_id} by: {user_info['user_principal']}")

        # Extract resource group and workspace name from workspace_id
        resource_group, workspace_name = extract_workspace_details(workspace_id)

        # Fetch rules from Azure
        try:
            rules = await azure_api_service.list_analytics_rules(resource_group, workspace_name)
        except Exception as azure_err:
            logger.error(f"[AUDIT] Azure API error fetching rules: {type(azure_err).__name__}: {str(azure_err)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch analytics rules: {str(azure_err)}"
            )

        logger.info(f"[AUDIT] Retrieved {len(rules)} analytics rules for {workspace_name}")
        return rules

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Failed to get analytics rules: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics rules: {str(e)}"
        )


# ===== AUDIT JOB MANAGEMENT =====
@router.post(
    "/audits",
    response_model=AuditJobMetadata,
    summary="Start a new audit job",
    description="Initiate cost optimization audit for a Sentinel workspace"
)
async def start_audit(
    request: StartAuditRequest,
    token: dict = Depends(validate_entra_token)
):
    """
    Start a new audit job.

    Validates Entra token, creates audit job, and triggers background orchestrator.
    Async job runs in background - client polls /audits/{job_id} for status.
    """
    try:
        user_info = extract_user_info(token)

        # Validate prompt shield on user inputs
        is_safe, risk_score, reason = prompt_shield.validate(request.workspace_id)
        if not is_safe:
            logger.warning(
                f"[AUDIT] Prompt injection detected in audit request: {reason}"
            )
            # Log security event
            security_middleware.log_security_event(
                event_type="PROMPT_INJECTION_ATTEMPT",
                severity="HIGH",
                details=f"Injection detected in workspace_id: {reason}",
                user_id=user_info['user_id']
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected"
            )

        logger.info(
            f"[AUDIT] Audit job initiated by: {user_info['user_principal']} "
            f"for workspace: {request.workspace_id} "
            f"(days_lookback={request.days_lookback})"
        )

        # Extract workspace details from workspace_id
        resource_group, workspace_name = extract_workspace_details(request.workspace_id)

        logger.info(
            f"[AUDIT] Extracted workspace details: "
            f"name={workspace_name}, resource_group={resource_group}"
        )

        # Create job ID
        job_id = f"job-{datetime.utcnow().timestamp()}"
        logger.info(f"[AUDIT] Created job_id: {job_id}")

        # Create job record in storage
        job_metadata = await job_storage.create_job(
            job_id=job_id,
            workspace_id=request.workspace_id,
            subscription_id=request.subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name
        )

        # Log audit event
        AuditLogger.log_event(
            event_type="AUDIT_STARTED",
            resource=request.workspace_id,
            status="SUCCESS",
            user_id=user_info['user_id'],
            details=f"job_id={job_id}, days_lookback={request.days_lookback}"
        )

        # Trigger background orchestrator execution
        logger.info(f"[AUDIT] Triggering background orchestrator for job_id={job_id}")
        asyncio.create_task(
            _execute_audit_background(
                job_id=job_id,
                workspace_id=request.workspace_id,
                subscription_id=request.subscription_id,
                resource_group=resource_group,
                workspace_name=workspace_name,
                days_lookback=request.days_lookback,
                user_id=user_info['user_id'],
                user_principal=user_info['user_principal']
            )
        )

        logger.info(
            f"[AUDIT] Job queued successfully: job_id={job_id} "
            f"workspace={workspace_name}"
        )

        # Return job metadata
        return job_metadata

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Audit start failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start audit job"
        )


@router.get(
    "/audits/{job_id}",
    response_model=AuditJobMetadata,
    summary="Get audit job status",
    description="Retrieve status and metadata for an audit job"
)
async def get_audit_status(
    job_id: str,
    token: dict = Depends(validate_entra_token)
):
    """Get audit job status and metadata"""
    try:
        user_info = extract_user_info(token)
        logger.info(f"[AUDIT] Status requested for job: {job_id}")

        # Fetch job from storage
        job_record = await job_storage.get_job(job_id)
        if not job_record:
            logger.warning(f"[AUDIT] Job not found: {job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )

        logger.info(
            f"[AUDIT] Job status retrieved: job_id={job_id} "
            f"status={job_record.status.value}"
        )

        # Extract report summary if available
        tables_analyzed = None
        archive_candidates_count = None
        total_monthly_savings = None

        if job_record.report:
            tables_analyzed = job_record.report.summary.total_tables_analyzed
            archive_candidates_count = len(job_record.report.archive_candidates)
            total_monthly_savings = job_record.report.summary.total_monthly_savings

        return AuditJobMetadata(
            job_id=job_id,
            workspace_id=job_record.workspace_id,
            workspace_name=job_record.workspace_name,
            status=job_record.status,
            created_at=job_record.created_at,
            error_message=job_record.error_message,
            report_url=f"/audits/{job_id}/report" if job_record.report else None,
            # Report summary fields
            tables_analyzed=tables_analyzed,
            archive_candidates_count=archive_candidates_count,
            total_monthly_savings=total_monthly_savings,
            # Report storage fields
            report_blob_url=job_record.report_blob_url,
            report_saved_at=job_record.report_saved_at,
            report_expires_at=job_record.report_expires_at
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Status check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )


@router.get(
    "/audits/{job_id}/stream",
    summary="Real-time audit progress (SSE)",
    description="Server-sent events stream of agent tool execution progress"
)
async def stream_audit_progress(
    job_id: str,
    token: dict = Depends(validate_entra_token)
):
    """
    Stream audit progress via Server-Sent Events (SSE).

    Returns real-time updates as agent executes tools and completes steps.
    Polls job storage for progress updates and streams them to client.
    """
    async def event_generator():
        try:
            logger.info(f"[AUDIT] SSE stream opened for job: {job_id}")

            # Verify job exists
            job_record = await job_storage.get_job(job_id)
            if not job_record:
                logger.warning(f"[AUDIT] Job not found for stream: {job_id}")
                yield f"data: {json.dumps({'error': f'Job not found: {job_id}'})}\n\n"
                return

            logger.info(f"[AUDIT] Job found, starting progress stream: {job_id}")

            # Track last sent update index to avoid duplicates
            sent_updates = 0
            consecutive_empty_polls = 0
            max_empty_polls = 60  # Wait up to 60 seconds for job completion

            while True:
                # Get current progress updates
                all_updates = await job_storage.get_progress_updates(job_id)

                # Send any new updates since last poll
                if len(all_updates) > sent_updates:
                    for update in all_updates[sent_updates:]:
                        logger.debug(
                            f"[AUDIT] Streaming progress: job_id={job_id} "
                            f"step={update.current_step}/{update.total_steps}"
                        )
                        yield f"data: {json.dumps(update.dict())}\n\n"
                        sent_updates += 1

                # Get current job status
                job_record = await job_storage.get_job(job_id)
                if not job_record:
                    logger.error(f"[AUDIT] Job disappeared during stream: {job_id}")
                    yield f"data: {json.dumps({'error': 'Job disappeared'})}\n\n"
                    break

                # Check if job is complete
                if job_record.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    logger.info(
                        f"[AUDIT] Job execution complete: job_id={job_id} "
                        f"status={job_record.status.value}"
                    )

                    # Send completion event
                    completion_event = {
                        'job_id': job_id,
                        'status': job_record.status.value,
                        'progress_percent': 100 if job_record.status == JobStatus.COMPLETED else -1,
                        'message': f'Job {job_record.status.value}'
                    }

                    if job_record.error_message:
                        completion_event['error'] = job_record.error_message

                    yield f"data: {json.dumps(completion_event)}\n\n"
                    break

                # Job still running - wait before next poll
                consecutive_empty_polls += 1
                if consecutive_empty_polls > max_empty_polls:
                    logger.warning(
                        f"[AUDIT] SSE stream timeout waiting for job completion: {job_id}"
                    )
                    yield f"data: {json.dumps({'warning': 'Job execution timeout'})}\n\n"
                    break

                # Sleep briefly before next poll
                await asyncio.sleep(1)

            logger.info(f"[AUDIT] SSE stream closed for job: {job_id}")

        except Exception as e:
            logger.error(f"[AUDIT] SSE stream error for job {job_id}: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/audits/{job_id}/report",
    response_model=Report,
    summary="Get full optimization report",
    description="Retrieve complete cost optimization analysis and recommendations"
)
async def get_report(
    job_id: str,
    token: dict = Depends(validate_entra_token)
):
    """Get full audit report"""
    try:
        user_info = extract_user_info(token)
        logger.info(f"[AUDIT] Report requested for job: {job_id}")

        # Fetch report from storage
        report = await job_storage.get_report(job_id)
        if not report:
            logger.warning(f"[AUDIT] Report not available: job_id={job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not available for job: {job_id}"
            )

        logger.info(
            f"[AUDIT] Report retrieved successfully: job_id={job_id} "
            f"tables={report.summary.total_tables_analyzed} "
            f"annual_savings=${report.summary.total_annual_savings:,.0f}"
        )

        return report

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Report fetch failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get report"
        )


# ===== REPORT EXPORT ENDPOINTS =====
@router.get(
    "/audits/{job_id}/report/export/{export_format}",
    summary="Export report in multiple formats",
    description="Download audit report as JSON, CSV, or TXT"
)
async def export_report(
    job_id: str,
    export_format: str,
    token: dict = Depends(validate_entra_token)
):
    """
    Export audit report in requested format.

    Args:
        job_id: Audit job ID
        export_format: Format (json, csv, txt)
        token: Validated Entra ID token

    Returns:
        File download with appropriate MIME type

    Raises:
        404: Report not found
        400: Invalid format
    """
    try:
        # Validate format
        valid_formats = ["json", "csv", "txt"]
        if export_format.lower() not in valid_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}"
            )

        # Get report
        report = await job_storage.get_report(job_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not found for job: {job_id}"
            )

        # Export to requested format
        if export_format == "json":
            content = report_exporter.export_to_json(report)
            media_type = "application/json"
            filename = f"report-{report.workspace_name}-{job_id}.json"
        elif export_format == "csv":
            content = report_exporter.export_to_csv(report)
            media_type = "text/csv"
            filename = f"report-{report.workspace_name}-{job_id}.csv"
        else:  # txt
            content = report_exporter.export_to_txt(report)
            media_type = "text/plain"
            filename = f"report-{report.workspace_name}-{job_id}.txt"

        logger.info(f"[EXPORT] Report exported: job_id={job_id}, format={export_format}")

        return StreamingResponse(
            iter([content.encode("utf-8")]),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EXPORT] Export failed: job_id={job_id}, format={export_format}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export report"
        )


@router.post(
    "/audits/{job_id}/report/save",
    summary="Save report to blob storage",
    description="Persist audit report to Azure Blob Storage for long-term retention"
)
async def save_report_to_storage(
    job_id: str,
    token: dict = Depends(validate_entra_token)
):
    """
    Save audit report to Azure Blob Storage.

    Args:
        job_id: Audit job ID
        token: Validated Entra ID token

    Returns:
        {
            "blob_url": "https://storage.blob.core.windows.net/...",
            "expires_at": "2026-04-09T...",
            "report_id": "job-..."
        }

    Raises:
        404: Report not found
        500: Storage upload failed
    """
    try:
        # Get report from in-memory storage
        report = await job_storage.get_report(job_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not found for job: {job_id}"
            )

        # Export to JSON
        report_json = report_exporter.export_to_json(report)

        # Upload to blob storage
        blob_url = await blob_storage_service.upload_report(
            job_id=job_id,
            report_data=report_json,
            content_type="application/json",
            metadata={
                "workspace_name": report.workspace_name,
                "timestamp": report.timestamp.isoformat(),
                "tables_analyzed": str(report.summary.total_tables_analyzed),
            }
        )

        # Calculate expiration date
        from datetime import datetime, timedelta
        expires_at_datetime = (
            datetime.utcnow() +
            timedelta(days=settings.REPORT_EXPIRATION_DAYS)
        )
        expires_at = expires_at_datetime.isoformat()

        # Update job record with blob URL
        job_record = await job_storage.get_job(job_id)
        if job_record:
            job_record.report_blob_url = blob_url
            job_record.report_saved_at = datetime.utcnow()
            job_record.report_expires_at = expires_at_datetime  # Use datetime object, not string
            logger.info(
                f"[SAVE_REPORT] Job record updated: job_id={job_id}, "
                f"report_saved_at={job_record.report_saved_at}, "
                f"report_expires_at={job_record.report_expires_at}"
            )

        logger.info(
            f"[SAVE_REPORT] Report saved to blob storage: "
            f"job_id={job_id} blob_url={blob_url} expires={expires_at}"
        )

        return {
            "blob_url": blob_url,
            "expires_at": expires_at,
            "report_id": job_id,
            "workspace_name": report.workspace_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SAVE_REPORT] Failed to save report: job_id={job_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save report to storage: {str(e)}"
        )


# ===== APPROVAL GATE (HARD SEPARATION) =====
@router.post(
    "/audits/{job_id}/approve",
    summary="Approve tier changes (HARD GATE)",
    description="Execute table tier migrations - requires security group membership"
)
async def approve_migration(
    job_id: str,
    request: ApprovalRequest,
    token: dict = Depends(validate_entra_token),
    authorized: bool = Depends(require_approval_group)
):
    """
    Approve and execute tier changes.

    HARD GATE: This is a separate service path with its own authentication.
    Only users in approval security group can execute tier changes.
    All approvals logged immutably.

    Args:
        job_id: Audit job ID
        request: List of tables to migrate
        token: Validated Entra ID token
        authorized: Must be member of approval group

    Returns:
        Approval result and execution status
    """
    try:
        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

        user_info = extract_user_info(token)

        logger.warning(
            f"[AUDIT] TIER CHANGE APPROVED AND EXECUTED by: {user_info['user_principal']} "
            f"job_id={job_id} tables={len(request.table_names)}"
        )

        # Placeholder: In production, would execute tier changes via API
        return {
            "status": "approved",
            "job_id": job_id,
            "tables_migrated": request.table_names,
            "executed_at": datetime.utcnow()
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AUDIT] Approval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Approval execution failed"
        )


# ===== AUDIT HISTORY =====
@router.get(
    "/audits",
    response_model=PaginatedResponse[AuditJobMetadata],
    summary="List all audit jobs",
    description="Retrieve history of audit jobs with pagination"
)
async def list_audits(
    page: int = 1,
    page_size: int = 50,
    token: dict = Depends(validate_entra_token)
):
    """List all audit jobs (paginated)"""
    try:
        user_info = extract_user_info(token)
        logger.info(f"[AUDIT] Audit history requested by {user_info.get('upn', 'unknown')} page={page} page_size={page_size}")

        # Get all jobs from storage
        all_jobs = await job_storage.get_all_jobs()
        total = len(all_jobs)

        # Calculate pagination
        skip = (page - 1) * page_size
        paginated_jobs = all_jobs[skip:skip + page_size]
        total_pages = (total + page_size - 1) // page_size

        logger.info(f"[AUDIT] Returning {len(paginated_jobs)} of {total} jobs (page {page}/{total_pages})")

        return PaginatedResponse(
            items=paginated_jobs,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"[AUDIT] Audit list failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list audits"
        )


# ===== DIAGNOSTICS =====
@router.post(
    "/debug/test-usage-table",
    tags=["debug"]
)
async def test_usage_table(request: dict):
    """
    Debug endpoint: Test Usage table query directly

    Request body:
    {
        "workspace_id": "/subscriptions/.../workspaces/...",
        "days_lookback": 30
    }
    """
    try:
        workspace_id = request.get("workspace_id")
        days_lookback = request.get("days_lookback", 30)

        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id required")

        logger.info(f"[DEBUG] Testing Usage table query for workspace: {workspace_id}")

        # Test query (same as in get_ingestion_volume)
        kql_query = f"""
        Usage
        | where TimeGenerated > ago({days_lookback}d)
        | where DataType != "Usage"
        | summarize TotalGB = sum(Quantity) / 1024 by DataType
        | extend AvgGBPerDay = TotalGB / {days_lookback}
        | project TableName=DataType, AvgGBPerDay
        """

        logger.info(f"[DEBUG] Executing KQL: {kql_query[:80]}...")

        from datetime import timedelta
        response = azure_api_service.logs_query_client.query_workspace(
            workspace_id=workspace_id,
            query=kql_query,
            timespan=timedelta(days=days_lookback)
        )

        if response.tables and len(response.tables) > 0:
            rows = response.tables[0].rows
            logger.info(f"[DEBUG] Query returned {len(rows)} rows")

            results = []
            for row in rows:
                results.append({
                    "TableName": row[0],
                    "AvgGBPerDay": float(row[1]) if row[1] is not None else 0.0
                })

            return {
                "status": "success",
                "usage_table_exists": True,
                "rows_returned": len(rows),
                "sample_data": results[:5],
                "all_data": results
            }
        else:
            logger.warning("[DEBUG] Usage table query returned no rows")
            return {
                "status": "no_data",
                "usage_table_exists": False,
                "rows_returned": 0,
                "message": "Usage table exists but returned no rows for this timespan"
            }

    except Exception as e:
        logger.error(f"[DEBUG] Usage table test failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)}",
            "message": "Failed to query Usage table"
        }


# ===== ERROR HANDLING =====
@router.get(
    "/error",
    response_model=ErrorResponse,
    tags=["system"]
)
async def error_example():
    """Example error response"""
    return ErrorResponse(
        error_code="EXAMPLE",
        error_message="This is an example error",
        timestamp=datetime.utcnow()
    )
