/**
 * TypeScript Type Definitions for SentinelLens Frontend
 *
 * Defines all interfaces for API responses, component props, and data models.
 * Ensures type safety across the frontend.
 */

/**
 * User Information from Entra ID
 */
export interface User {
  id: string;
  displayName: string;
  email: string;
  principalName: string;
}

/**
 * Azure Workspace Information
 */
export interface WorkspaceInfo {
  workspace_id: string;
  workspace_name: string;
  subscription_id: string;
  resource_group: string;
  location?: string;
}

/**
 * Analytics Rule Information
 */
export interface AnalyticsRule {
  rule_id: string;
  rule_name: string;
  rule_type: string;
  kql_query: string;
  enabled: boolean;
  tables_referenced: string[];
  parsing_confidence: number;
}

/**
 * Audit Job Information
 */
export interface AuditJob {
  job_id: string;
  workspace_id: string;
  workspace_name: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "AWAITING_APPROVAL" | "APPROVED" | "CANCELLED";
  progress_percentage: number;
  current_step?: string;
  total_steps?: number;
  error_message?: string;
  tables_analyzed?: number;
  total_savings?: number;
  archive_candidates_count?: number;
  // Report storage fields
  report_blob_url?: string;      // URL to blob storage report
  report_saved_at?: string;      // When report was saved to storage
  report_expires_at?: string;    // When report expires
}

/**
 * Table Recommendation from Analysis
 */
export interface TableRecommendation {
  table_name: string;
  table_id?: string;
  current_tier: string;
  recommended_tier?: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reason?: string;
  ingestion_gb_per_day: number;
  ingestion_gb_per_month: number;
  monthly_cost_hot: number;
  monthly_cost_archive: number;
  monthly_savings: number;
  annual_savings: number;
  rule_coverage_count: number;
  rule_names?: string[];
  parsing_confidence?: number;
  workbook_coverage_count?: number;
  hunt_query_coverage_count?: number;
  data_connector_count?: number;
  log_category?: string; // e.g., "Azure Active Directory", "Windows Security Events"
  connector_name?: string;
  notes?: string;
}

/**
 * Warning in Report
 */
export interface Warning {
  warning_type: string;
  table_name?: string;
  description: string;
  recommendation: string;
}

/**
 * Report Metadata
 */
export interface ReportMetadata {
  [key: string]: any;
}

/**
 * Report Summary
 */
export interface ReportSummary {
  total_tables_analyzed: number;
  total_ingestion_gb_per_month: number;
  total_monthly_cost_hot: number;
  total_monthly_cost_archive: number;
  total_monthly_savings: number;
  total_annual_savings: number;
  tables_by_tier: Record<string, number>;
  tables_by_confidence: Record<string, number>;
}

/**
 * Execution Metadata
 */
export interface ExecutionMetadata {
  agent_run_timestamp: string;
  agent_completion_time_seconds: number;
  kql_parsing_success_rate: number;
  tables_analyzed: number;
  rules_analyzed: number;
  workbooks_analyzed: number;
  hunt_queries_analyzed: number;
  agent_tokens_used: number;
  agent_tokens_limit: number;
}

/**
 * Connector Coverage Item
 */
export interface ConnectorCoverageItem {
  connector_name: string;
  connector_type: string;
  tables_fed: string[];
  tables_with_coverage: number;
  tables_without_coverage: number;
}

/**
 * Report Warning
 */
export interface ReportWarning {
  warning_type: string;
  table_name: string;
  description: string;
  recommendation: string;
}

/**
 * Wasted Table Information
 */
export interface WastedTable {
  table_name: string;
  ingestion_gb_90d: number;
  cost_hot_90d: number;
  last_ingestion?: string;
  waste_potential: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
}

/**
 * Waste Analysis Summary
 */
export interface WasteAnalysisSummary {
  tables_analyzed: number;
  tables_with_data: number;
  tables_with_rules: number;
  tables_without_rules: number;
  total_ingestion_gb_90d: number;
  wasted_ingestion_gb_90d: number;
  total_cost_hot_90d: number;
  wasted_cost_hot_90d: number;
  wasted_percentage: number;
  top_wasted_tables: WastedTable[];
  rule_coverage_stats: Record<string, any>;
}

/**
 * Audit Report - Full Optimization Report
 */
export interface AuditReport {
  job_id: string;
  workspace_id: string;
  workspace_name: string;
  timestamp: string;
  summary: ReportSummary;
  archive_candidates: TableRecommendation[];
  low_usage_candidates: TableRecommendation[];
  active_tables: TableRecommendation[];
  connector_coverage: ConnectorCoverageItem[];
  waste_analysis?: WasteAnalysisSummary;
  warnings: ReportWarning[];
  metadata: ExecutionMetadata;
}

/**
 * Progress Update (from SSE stream)
 */
export interface ProgressUpdate {
  job_id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  progress_percentage: number;
  current_step: string;
  total_steps: number;
  message: string;
  timestamp: string;
  error?: string;
}

/**
 * Approval Request
 */
export interface ApprovalRequest {
  job_id: string;
  tables_to_migrate: string[];
  target_tier: string;
}

/**
 * Approval Response
 */
export interface ApprovalResponse {
  status: "success" | "failed";
  message: string;
  migration_id?: string;
  approved_table_count?: number;
  migrated_tables?: string[];
  errors?: { table_name: string; error: string }[];
}

/**
 * API Response Wrapper
 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/**
 * Paginated Response
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * Audit History Item
 */
export interface AuditHistoryItem {
  job_id: string;
  workspace_id: string;
  workspace_name?: string;       // From job record
  created_at: string;
  completed_at?: string;
  status: "pending" | "running" | "completed" | "failed";
  tables_analyzed?: number;      // From report summary
  archive_candidates_count?: number;  // From report
  total_monthly_savings?: number; // From report summary
  // Report storage fields
  report_blob_url?: string;      // URL to blob storage report
  report_saved_at?: string;      // When report was saved to storage
  report_expires_at?: string;    // When report expires
}

/**
 * Dashboard Summary
 */
export interface DashboardSummary {
  total_audits: number;
  completed_audits: number;
  running_audits: number;
  total_monthly_savings: number;
  total_annual_savings: number;
  archive_candidates_total: number;
  average_tables_analyzed: number;
  success_rate_percentage: number;
}

/**
 * Error Response
 */
export interface ErrorResponse {
  detail: string;
  status: number;
  timestamp?: string;
  path?: string;
}

/**
 * Setup Credentials Request
 */
export interface SetupCredentialsRequest {
  client_id: string;
  client_secret: string;
}

/**
 * Setup Credentials Response
 */
export interface SetupCredentialsResponse {
  status: string;
  message: string;
  env_file: string;
}

/**
 * Report Interface (alias for AuditReport)
 */
export type Report = AuditReport;

/**
 * Audit Progress Update (alias for ProgressUpdate)
 */
export type AuditProgress = ProgressUpdate;

/**
 * Workspace Info (alias for WorkspaceInfo)
 */
export type Workspace = WorkspaceInfo;
