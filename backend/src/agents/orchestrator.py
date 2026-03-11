"""
Azure AI Foundry Agent Orchestrator

Manages agent lifecycle, tool execution, and result collection.
Implements ReAct loop: Reason → Act → Observe
"""

import logging
import asyncio
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from src.config import settings
from src.models.schemas import (
    AnalyticsRule, Workbook, HuntQuery, DataConnector, TableIngestionData,
    KqlParseResult, Report, ProgressUpdate, ConfidenceLevel
)
from src.services.azure_api import azure_api_service
from src.services.kql_parser import kql_parser
from src.services.cost_calculator import cost_calculator
from src.services.report_generator import report_generator
from src.services.waste_analyzer import WasteAnalyzer
from src.security import pii_masking, prompt_shield, data_sanitizer
from src.security_middleware import security_middleware
from src.utils.logging import AuditLogger
from src.storage import job_storage

logger = logging.getLogger(__name__)

# Parallel execution step names (must match asyncio.gather() order)
PARALLEL_STEP_NAMES = [
    "list_workspace_tables",
    "get_ingestion_volume",
    "list_analytics_rules",
    "list_workbooks",
    "list_hunt_queries",
    "list_data_connectors"
]


class AgentOrchestrator:
    """
    Orchestrates the SentinelLens agent workflow.

    ReAct Loop Flow:
    1. Reason: Understand the audit goal
    2. Act: Execute tools to gather data
    3. Observe: Collect results and process
    4. Repeat until sufficient data to generate report
    """

    def __init__(self):
        self.agent_id = None
        self.execution_start_time = None
        self.execution_times = {}
        self.tokens_used = 0
        self.max_tokens = settings.AGENT_MAX_TOKENS_PER_RUN
        self.tool_results = {}
        logger.info("[AGENT] Orchestrator initialized")

    async def _emit_progress(
        self,
        job_id: str,
        current_step: int,
        total_steps: int,
        tool_name: str,
        status: str = "running"
    ):
        progress_percent = int((current_step / total_steps) * 100)
        update = ProgressUpdate(
            job_id=job_id,
            status=status,
            progress_percentage=progress_percent,
            current_step=tool_name,
            total_steps=total_steps,
            message=f"Step {current_step}/{total_steps}: {tool_name}"
        )
        await job_storage.add_progress_update(job_id, update)
        logger.info(
            f"[AGENT] Progress emitted: job_id={job_id} "
            f"step={current_step}/{total_steps} "
            f"progress={progress_percent}% "
            f"tool={tool_name}"
        )

    async def execute_audit(
        self,
        job_id: str,
        workspace_id: str,
        subscription_id: str,
        resource_group: str,
        workspace_name: str,
        days_lookback: int = 30
    ) -> Report:
        """
        Execute complete audit workflow.

        ingestion_data contract (from azure_api.get_ingestion_volume):
            Dict[str, float]  →  table_name → avg_gb_per_day

        The KQL query in azure_api already divides TotalGB by days_lookback
        to produce a per-day rate. Everything downstream uses gb_per_day;
        we never multiply back out to a period total before passing data between
        services — that was the root cause of the wrong cost numbers.
        """
        self.agent_id = job_id
        self.execution_start_time = time.time()
        total_steps = 10

        try:
            logger.info(f"[AGENT] Starting audit execution: job_id={job_id}")

            # ── Emit initial progress for all parallel steps ──────────
            logger.info("[AGENT] STEPS 1-7: Fetching workspace data concurrently")
            await asyncio.gather(
                self._emit_progress(job_id, 1, total_steps, "list_workspace_tables"),
                self._emit_progress(job_id, 2, total_steps, "get_ingestion_volume"),
                self._emit_progress(job_id, 3, total_steps, "list_analytics_rules"),
                self._emit_progress(job_id, 5, total_steps, "list_workbooks"),
                self._emit_progress(job_id, 6, total_steps, "list_hunt_queries"),
                self._emit_progress(job_id, 7, total_steps, "list_data_connectors")
            )

            # ── PARALLEL STEPS 1-3, 5-7: Gather independent data ─────
            results = await asyncio.gather(
                self._execute_tool(
                    "list_workspace_tables",
                    lambda: azure_api_service.list_workspace_tables(resource_group, workspace_name)
                ),
                self._execute_tool(
                    "get_ingestion_volume",
                    lambda: azure_api_service.get_ingestion_volume(
                        resource_group, workspace_name, days_lookback
                    )
                ),
                self._execute_tool(
                    "list_analytics_rules",
                    lambda: azure_api_service.list_analytics_rules(resource_group, workspace_name)
                ),
                self._execute_tool(
                    "list_workbooks",
                    lambda: azure_api_service.list_workbooks(resource_group, workspace_name)
                ),
                self._execute_tool(
                    "list_hunt_queries",
                    lambda: azure_api_service.list_hunt_queries(resource_group, workspace_name)
                ),
                self._execute_tool(
                    "list_data_connectors",
                    lambda: azure_api_service.list_data_connectors(resource_group, workspace_name)
                ),
                return_exceptions=True
            )

            # Unpack results — graceful degradation on individual failures
            tables      = results[0] if not isinstance(results[0], Exception) else []
            ingestion_data = results[1] if not isinstance(results[1], Exception) else {}
            rules       = results[2] if not isinstance(results[2], Exception) else []
            workbooks   = results[3] if not isinstance(results[3], Exception) else []
            hunt_queries = results[4] if not isinstance(results[4], Exception) else []
            connectors  = results[5] if not isinstance(results[5], Exception) else []

            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    step_name = PARALLEL_STEP_NAMES[idx] if idx < len(PARALLEL_STEP_NAMES) else "unknown"
                    logger.warning(
                        f"[AGENT] Step '{step_name}' failed: "
                        f"{type(result).__name__}: {result}"
                    )

            if not isinstance(tables, list):
                tables = []
            if not isinstance(ingestion_data, dict):
                ingestion_data = {}

            if not tables:
                raise Exception("No tables found in workspace")

            logger.info(
                f"[AGENT] Parallel data gathering complete: "
                f"{len(tables)} tables, {len(rules)} rules, "
                f"{len(workbooks)} workbooks, {len(hunt_queries)} hunt queries, "
                f"{len(connectors)} connectors"
            )

            # ── SECURITY: Validate and mask KQL queries ───────────────
            logger.info("[AGENT] Applying security controls: validating and masking KQL")
            rules = security_middleware.validate_and_mask_kql_queries(rules)
            security_middleware.log_security_event(
                event_type="KQL_VALIDATION_COMPLETE",
                severity="LOW",
                details=f"Validated {len(rules)} KQL queries"
            )

            # ── STEP 4: Parse KQL ─────────────────────────────────────
            logger.info("[AGENT] STEP 4: Parsing KQL queries")
            await self._emit_progress(job_id, 4, total_steps, "parse_kql_tables")

            kql_queries = [rule.kql_query for rule in rules if rule.kql_query]
            kql_parse_results = await self._execute_tool(
                "parse_kql_tables",
                lambda: asyncio.to_thread(kql_parser.batch_parse, kql_queries)
            )

            confidence_mapping = {
                ConfidenceLevel.HIGH:   1.0,
                ConfidenceLevel.MEDIUM: 0.5,
                ConfidenceLevel.LOW:    0.0
            }
            for rule, parse_result in zip(rules, kql_parse_results):
                rule.tables_referenced = parse_result.tables
                rule.parsing_confidence = confidence_mapping.get(parse_result.confidence, 0.0)

            parse_success_rate = (
                sum(1 for r in kql_parse_results if r.success) / len(kql_parse_results)
                if kql_parse_results else 0
            )
            logger.info(f"[AGENT] KQL parsing complete: {parse_success_rate:.1%} success rate")

            # ── SECURITY: Mask connector metadata ────────────────────
            logger.info("[AGENT] Applying security controls: masking connector metadata")
            if isinstance(connectors, list):
                connectors = security_middleware.mask_connector_metadata(connectors)
                security_middleware.log_security_event(
                    event_type="CONNECTOR_METADATA_MASKED",
                    severity="LOW",
                    details=f"Masked metadata for {len(connectors)} connectors"
                )

            # ── STEP 8: Calculate cost savings ────────────────────────
            #
            # ingestion_data is Dict[str, float]: table_name → gb_per_day
            # cost_calculator.calculate_table_costs() expects gb_per_day — pass it directly.
            # DO NOT multiply by days_lookback or any period here.
            #
            logger.info("[AGENT] STEP 8: Calculating cost savings")
            await self._emit_progress(job_id, 8, total_steps, "calculate_cost_savings")

            tables_with_costs = []
            for table in tables:
                gb_per_day = ingestion_data.get(table.table_name, 0.0)
                costs = cost_calculator.calculate_table_costs(
                    gb_per_day, table.current_tier, "Archive"
                )
                tables_with_costs.append({
                    "table_name": table.table_name,
                    "ingestion_gb_day": gb_per_day,
                    "costs": costs
                })

            logger.info("[AGENT] Cost calculations complete")

            # ── STEP 9: Analyze waste ─────────────────────────────────
            #
            # WasteAnalyzer.analyze_waste() expects:
            #   ingestion_data: Dict[str, Tuple[float, str]]
            #                   table_name → (gb_per_day, last_ingestion_timestamp)
            #
            # CRITICAL: pass gb_per_day directly — do NOT pre-multiply to 90d.
            # The old code did `gb_90d = gb_day * 90` here which inflated every
            # cost figure by 3× before even reaching the analyzer.
            #
            logger.info("[AGENT] STEP 9: Analyzing wasted resources")
            await self._emit_progress(job_id, 9, total_steps, "analyze_waste")

            waste_analysis_summary = None
            try:
                if ingestion_data and rules:
                    current_time = datetime.utcnow().isoformat()
                    ingestion_data_for_waste: Dict[str, Tuple[float, str]] = {
                        table_name: (gb_per_day, current_time)
                        for table_name, gb_per_day in ingestion_data.items()
                    }
                    waste_analyzer = WasteAnalyzer()
                    waste_analysis_summary = waste_analyzer.analyze_waste(
                        rules,
                        ingestion_data_for_waste,
                        days_lookback=days_lookback,
                    )
                    logger.info(
                        f"[AGENT] Waste analysis complete: "
                        f"${waste_analysis_summary.wasted_monthly_cost:.2f}/month wasted "
                        f"({waste_analysis_summary.wasted_percentage}%) | "
                        f"potential annual savings: "
                        f"${waste_analysis_summary.potential_annual_savings:,.2f} | "
                        f"unused tables: {waste_analysis_summary.tables_without_rules}"
                    )
                else:
                    logger.warning("[AGENT] Insufficient data for waste analysis")
            except Exception as e:
                logger.error(f"[AGENT] Waste analysis failed (non-blocking): {e}", exc_info=True)
                waste_analysis_summary = None

            # ── STEP 10: Generate report ──────────────────────────────
            logger.info("[AGENT] STEP 10: Generating optimization report")
            await self._emit_progress(job_id, 10, total_steps, "generate_report")

            execution_time = time.time() - self.execution_start_time

            report = await self._execute_tool(
                "generate_report",
                lambda: asyncio.to_thread(
                    report_generator.generate_report,
                    job_id=job_id,
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    tables=tables,
                    rules=rules,
                    ingestion_data=ingestion_data,   # gb_per_day dict — no transformation
                    connectors=connectors,
                    kql_parse_results=kql_parse_results,
                    agent_tokens_used=self.tokens_used,
                    agent_max_tokens=self.max_tokens,
                    agent_run_seconds=execution_time,
                    waste_analysis_summary=waste_analysis_summary,
                    days_lookback=days_lookback,
                )
            )

            logger.info(
                f"[AGENT] Audit execution complete: "
                f"job_id={job_id} | "
                f"tables={len(tables)} | "
                f"monthly_cost=${report.summary.total_monthly_cost_hot:,.2f} | "
                f"monthly_savings=${report.summary.total_monthly_savings:,.2f} | "
                f"annual_savings=${report.summary.total_annual_savings:,.0f} | "
                f"execution_time={execution_time:.1f}s"
            )

            logger.info("[AGENT] Logging audit completion event")
            security_middleware.log_security_event(
                event_type="AUDIT_COMPLETED",
                severity="LOW",
                details=(
                    f"Audit completed: {len(tables)} tables, "
                    f"${report.summary.total_annual_savings:,.0f} savings identified"
                )
            )

            return report

        except asyncio.TimeoutError:
            logger.error(f"[AGENT] Execution timeout after {settings.AGENT_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"[AGENT] Execution failed: {e}", exc_info=True)
            raise

    async def _execute_tool(self, tool_name: str, tool_func) -> any:
        start_time = time.time()
        try:
            logger.info(f"[AGENT] Executing tool: {tool_name}")
            result = await asyncio.wait_for(
                tool_func(),
                timeout=settings.AGENT_TIMEOUT_SECONDS
            )
            execution_time = time.time() - start_time
            self.execution_times[tool_name] = execution_time
            result_count = len(result) if isinstance(result, (list, dict)) else 1
            logger.info(
                f"[AGENT] Tool complete: {tool_name} "
                f"(results: {result_count}, time: {execution_time:.2f}s)"
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"[AGENT] Tool timeout: {tool_name}")
            raise
        except Exception as e:
            logger.error(f"[AGENT] Tool failed: {tool_name} - {e}")
            raise

    def check_token_budget(self):
        if self.tokens_used >= self.max_tokens:
            raise Exception(f"Token budget exceeded: {self.tokens_used} >= {self.max_tokens}")

    def get_execution_summary(self) -> Dict:
        if not self.execution_start_time:
            return {}
        return {
            "agent_id": self.agent_id,
            "total_execution_time": time.time() - self.execution_start_time,
            "tool_execution_times": self.execution_times,
            "tokens_used": self.tokens_used,
            "tokens_limit": self.max_tokens
        }


# ── Singleton ─────────────────────────────────────────────────────────
agent_orchestrator = AgentOrchestrator()