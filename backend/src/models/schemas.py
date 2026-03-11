"""
Pydantic request/response schemas for FastAPI validation.

All request/response bodies go through these schemas for strict validation.
This prevents insecure output handling and ensures type safety.
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional, Literal, Generic, TypeVar
from datetime import datetime
from enum import Enum

T = TypeVar('T')


# ===== ENUMS =====
class ConfidenceLevel(str, Enum):
    """Confidence score for KQL parsing and table recommendations"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TierType(str, Enum):
    """Log Analytics table tier types"""
    HOT = "Hot"
    BASIC = "Basic"
    ARCHIVE = "Archive"


class JobStatus(str, Enum):
    """Audit job status"""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ===== REQUEST SCHEMAS =====
class StartAuditRequest(BaseModel):
    """Start a new audit job"""
    workspace_id: str = Field(..., min_length=1, description="Sentinel workspace ID")
    subscription_id: str = Field(..., min_length=1, description="Azure subscription ID")
    days_lookback: int = Field(default=30, ge=1, le=365, description="Days of history to analyze")

    class Config:
        schema_extra = {
            "example": {
                "workspace_id": "workspace-123",
                "subscription_id": "sub-456",
                "days_lookback": 30
            }
        }


class ApprovalRequest(BaseModel):
    """Approve tier changes"""
    table_names: List[str] = Field(..., min_items=1, description="Tables to migrate to Archive")

    class Config:
        schema_extra = {
            "example": {
                "table_names": ["UnusedTable1", "UnusedTable2"]
            }
        }


class SetupCredentialsRequest(BaseModel):
    """Setup app registration credentials"""
    client_id: str = Field(..., min_length=1, description="Azure AD app registration client ID")
    client_secret: str = Field(..., min_length=1, description="Azure AD app registration client secret")

    class Config:
        schema_extra = {
            "example": {
                "client_id": "12345678-1234-1234-1234-123456789012",
                "client_secret": "your_client_secret_here"
            }
        }


# ===== RESPONSE SCHEMAS =====
class WorkspaceInfo(BaseModel):
    """Sentinel workspace info"""
    workspace_id: str
    workspace_name: str
    subscription_id: str
    resource_group: str


class AuditJobMetadata(BaseModel):
    """Audit job metadata"""
    job_id: str
    workspace_id: str
    workspace_name: Optional[str] = None
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    report_url: Optional[str] = None

    # Report summary fields
    tables_analyzed: Optional[int] = None
    archive_candidates_count: Optional[int] = None
    total_monthly_savings: Optional[float] = None

    # Report storage fields
    report_blob_url: Optional[str] = None
    report_saved_at: Optional[datetime] = None
    report_expires_at: Optional[datetime] = None


class ProgressUpdate(BaseModel):
    """Progress update from audit execution (SSE stream)"""
    job_id: str
    status: str = Field(..., description="Job status: running, completed, failed")
    progress_percentage: int = Field(0, ge=0, le=100)
    current_step: str = Field(..., description="Current step being executed")
    total_steps: int = Field(..., ge=1)
    message: str = Field("", description="Human-readable progress message")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


class ToolExecutionEvent(BaseModel):
    """Real-time SSE event for agent progress"""
    event_type: Literal["tool_called", "tool_completed", "tool_failed", "step_complete"]
    step_number: int
    tool_name: Optional[str] = None
    details: str
    timestamp: datetime


class PiiEntity(BaseModel):
    """PII entity detected and masked"""
    entity_type: str
    confidence: float
    start_position: int
    end_position: int


class MaskingEvent(BaseModel):
    """PII masking event"""
    original_text_length: int
    masked_text_length: int
    pii_entities_found: int
    entities: List[PiiEntity]


# ===== REPORT SCHEMAS =====
class TableRecommendation(BaseModel):
    """Recommendation for a specific table"""
    table_name: str
    current_tier: TierType
    ingestion_gb_per_day: float = Field(..., ge=0)
    ingestion_gb_per_month: float = Field(..., ge=0)
    rule_coverage_count: int = Field(..., ge=0)
    rule_names: List[str] = []
    confidence: ConfidenceLevel
    parsing_confidence: float = Field(..., ge=0, le=1)
    monthly_cost_hot: float = Field(..., ge=0)
    monthly_cost_archive: float = Field(..., ge=0)
    monthly_savings: float = Field(..., ge=0)
    annual_savings: float = Field(..., ge=0)
    connector_name: Optional[str] = None
    log_category: str = Field(default="Other", description="Log category")
    notes: str = ""

    class Config:
        schema_extra = {
            "example": {
                "table_name": "SecurityEvent",
                "current_tier": "Hot",
                "ingestion_gb_per_day": 0.9538,
                "ingestion_gb_per_month": 28.614,
                "rule_coverage_count": 25,
                "confidence": "HIGH",
                "parsing_confidence": 1.0,
                "monthly_cost_hot": 123.04,
                "monthly_cost_archive": 0.74,
                "monthly_savings": 122.30,
                "annual_savings": 1467.60,
            }
        }


class ConnectorCoverageItem(BaseModel):
    """Connector to table mapping"""
    connector_name: str
    connector_type: str
    tables_fed: List[str]
    tables_with_coverage: int
    tables_without_coverage: int


class ReportWarning(BaseModel):
    """Warning or manual review item"""
    warning_type: str
    table_name: str
    description: str
    recommendation: str


class ExecutionMetadata(BaseModel):
    """Metadata about report generation"""
    agent_run_timestamp: datetime
    agent_completion_time_seconds: float
    kql_parsing_success_rate: float = Field(..., ge=0, le=1)
    tables_analyzed: int
    rules_analyzed: int
    workbooks_analyzed: int
    hunt_queries_analyzed: int
    agent_tokens_used: int
    agent_tokens_limit: int


class ReportSummary(BaseModel):
    """Executive summary"""
    total_tables_analyzed: int
    days_lookback: int = Field(default=30, description="Lookback window used for ingestion query")
    total_ingestion_gb_per_day: float = Field(default=0.0, ge=0, description="Total GB/day across all tables")
    total_ingestion_gb_per_month: float = Field(ge=0)
    total_monthly_cost_hot: float = Field(ge=0)
    total_monthly_cost_archive: float = Field(ge=0)
    total_monthly_savings: float = Field(ge=0)
    total_annual_savings: float = Field(ge=0)
    tables_by_tier: dict
    tables_by_confidence: dict


class Report(BaseModel):
    """Full optimization report"""
    job_id: str
    workspace_id: str
    workspace_name: str
    timestamp: datetime
    days_lookback: int = Field(default=30, description="Lookback window used for ingestion query")

    # Summary
    summary: ReportSummary

    # Recommendations
    archive_candidates: List[TableRecommendation] = []
    low_usage_candidates: List[TableRecommendation] = []
    active_tables: List[TableRecommendation] = []

    # Coverage analysis
    connector_coverage: List[ConnectorCoverageItem] = []

    # Waste analysis
    waste_analysis: Optional['WasteAnalysisSummary'] = None

    # Warnings
    warnings: List[ReportWarning] = []

    # Execution details
    metadata: ExecutionMetadata

    class Config:
        schema_extra = {
            "example": {
                "job_id": "job-123",
                "workspace_id": "ws-456",
                "workspace_name": "Production Sentinel",
                "timestamp": "2026-03-09T10:30:00Z"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str
    environment: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response"""
    error_code: str
    error_message: str
    details: Optional[str] = None
    timestamp: datetime

    class Config:
        schema_extra = {
            "example": {
                "error_code": "INVALID_INPUT",
                "error_message": "Workspace ID is required",
                "timestamp": "2026-03-09T10:30:00Z"
            }
        }


# ===== INTERNAL SCHEMAS (not exposed in API) =====
class KqlParseResult(BaseModel):
    """Result of KQL parsing"""
    tables: List[str]
    confidence: ConfidenceLevel
    parsing_method: Literal["AST", "REGEX"]
    success: bool
    error_message: Optional[str] = None


class TableIngestionData(BaseModel):
    """Table ingestion and cost data"""
    table_name: str
    ingestion_gb_per_day: float
    ingestion_gb_per_month: float
    current_tier: TierType
    retention_days: int


class AnalyticsRule(BaseModel):
    """Analytics rule metadata"""
    rule_id: str
    rule_name: str
    rule_type: str
    kql_query: str
    enabled: bool
    tables_referenced: List[str] = []
    parsing_confidence: float = 0.0


class Workbook(BaseModel):
    """Workbook metadata"""
    workbook_id: str
    workbook_name: str
    kql_queries: List[str] = []
    tables_referenced: List[str] = []


class HuntQuery(BaseModel):
    """Hunt query metadata"""
    query_id: str
    query_name: str
    kql_query: str
    tables_referenced: List[str] = []


class DataConnector(BaseModel):
    """Data connector metadata"""
    connector_name: str
    connector_id: str
    connector_type: str
    tables_fed: List[str] = []


class TableIngestionInfo(BaseModel):
    """Table ingestion data from Usage table"""
    table_name: str
    ingestion_gb_90d: float
    ingestion_gb_daily_avg: float
    cost_hot_90d: float
    cost_archive_90d: float
    last_ingestion: Optional[str] = None
    rule_count: int = 0
    rules_using_table: List[str] = []


class RuleTableMapping(BaseModel):
    """Maps a rule to tables it uses"""
    rule_id: str
    rule_name: str
    rule_severity: Optional[str] = None
    tables_referenced: List[str] = []
    table_count: int = 0


class WastedTable(BaseModel):
    """Table with ingestion but no analytics rules using it"""
    table_name: str
    waste_potential: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    last_ingestion: Optional[str] = None

    # Per-day rate (normalised — always comparable regardless of lookback)
    ingestion_gb_per_day: float = Field(default=0.0, ge=0)

    # Monthly costs at $4.30/GB ingestion
    monthly_cost_hot: float = Field(default=0.0, ge=0)
    monthly_cost_archive: float = Field(default=0.0, ge=0)
    monthly_savings: float = Field(default=0.0, ge=0)
    annual_savings: float = Field(default=0.0, ge=0)

    # Legacy 90-day fields kept for schema compatibility
    ingestion_gb_90d: float = Field(default=0.0, ge=0)
    cost_hot_90d: float = Field(default=0.0, ge=0)


class WasteAnalysisSummary(BaseModel):
    """Summary of wasted resources"""
    tables_analyzed: int
    tables_with_data: int
    tables_with_rules: int
    tables_without_rules: int

    # Legacy 90-day fields (kept for schema compatibility)
    total_ingestion_gb_90d: float = Field(default=0.0, ge=0)
    wasted_ingestion_gb_90d: float = Field(default=0.0, ge=0)
    total_cost_hot_90d: float = Field(default=0.0, ge=0)
    wasted_cost_hot_90d: float = Field(default=0.0, ge=0)

    # Per-day fields (normalised, always accurate regardless of lookback)
    total_ingestion_gb_per_day: float = Field(default=0.0, ge=0)
    wasted_ingestion_gb_per_day: float = Field(default=0.0, ge=0)

    # Monthly / annual costs at $4.30/GB ingestion
    total_monthly_cost: float = Field(default=0.0, ge=0)
    wasted_monthly_cost: float = Field(default=0.0, ge=0)
    total_annual_cost: float = Field(default=0.0, ge=0)
    wasted_annual_cost: float = Field(default=0.0, ge=0)
    potential_annual_savings: float = Field(default=0.0, ge=0)


# ===== PAGINATION =====
class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    wasted_percentage: float = Field(default=0.0, ge=0)
    top_wasted_tables: List[WastedTable] = []
    rule_coverage_stats: dict = {}