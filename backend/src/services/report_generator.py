"""
Report Generator Service

Assembles structured optimization reports from agent analysis results.
All outputs validated against Pydantic schemas.

PRICING (matching Azure Sentinel workbook — $4.30/GB ingestion):
  - Hot (Analytics) ingestion:  $4.30/GB
  - Basic logs ingestion:       $0.65/GB
  - Archive retention:          $0.026/GB/month
  - Costs are always expressed as monthly (30-day) and annual (365-day)
  - gb_per_day × 30 × price = monthly cost  ← single source of truth
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from src.models.schemas import (
    Report, ReportSummary, TableRecommendation, ConnectorCoverageItem,
    ReportWarning, ExecutionMetadata, TierType, ConfidenceLevel,
    AnalyticsRule, DataConnector, TableIngestionData, KqlParseResult,
    WasteAnalysisSummary
)
from src.services.table_categorizer import get_table_category

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Azure Sentinel Pricing Constants (USD, 2025 pay-as-you-go)
# ─────────────────────────────────────────────────────────────
PRICE_HOT_PER_GB     = 4.30    # Analytics / Hot tier ingestion $/GB
PRICE_BASIC_PER_GB   = 0.65    # Basic logs ingestion $/GB
PRICE_ARCHIVE_PER_GB = 0.026   # Archive retention $/GB/month
DAYS_PER_MONTH       = 30.0
MONTHS_PER_YEAR      = 12.0


def _monthly_ingestion_cost(gb_per_day: float, tier: str = "Hot") -> float:
    """Return the monthly ingestion cost for a table given its daily ingestion rate."""
    gb_per_month = gb_per_day * DAYS_PER_MONTH
    if tier == "Basic":
        return gb_per_month * PRICE_BASIC_PER_GB
    elif tier == "Archive":
        return gb_per_month * PRICE_ARCHIVE_PER_GB
    else:
        return gb_per_month * PRICE_HOT_PER_GB


def _monthly_archive_cost(gb_per_day: float) -> float:
    """Return the monthly storage cost if moved to Archive tier."""
    return gb_per_day * DAYS_PER_MONTH * PRICE_ARCHIVE_PER_GB


def _monthly_savings(gb_per_day: float, current_tier: str = "Hot") -> float:
    """Net monthly saving from moving the table to Archive."""
    if current_tier == "Archive":
        return 0.0
    return max(0.0,
        _monthly_ingestion_cost(gb_per_day, current_tier)
        - _monthly_archive_cost(gb_per_day)
    )


# Confidence level to numeric score mapping (0.0 to 1.0)
CONFIDENCE_ENUM_MAPPING = {
    ConfidenceLevel.HIGH:   1.0,
    ConfidenceLevel.MEDIUM: 0.5,
    ConfidenceLevel.LOW:    0.0
}


class ReportGenerator:
    """Generate optimization reports"""

    @staticmethod
    def generate_report(
        job_id: str,
        workspace_id: str,
        workspace_name: str,
        tables: List[TableIngestionData],
        rules: List[AnalyticsRule],
        ingestion_data: Dict[str, float],       # table_name → avg_gb_per_day
        connectors: List[DataConnector],
        kql_parse_results: List[KqlParseResult],
        agent_tokens_used: int,
        agent_max_tokens: int,
        agent_run_seconds: float,
        waste_analysis_summary: Optional[WasteAnalysisSummary] = None,
        days_lookback: int = 30,                # surfaced in UI filter
    ) -> Report:
        """
        Generate a full optimization report.

        Args:
            job_id:                  Audit job ID.
            workspace_id:            Sentinel workspace ARM resource ID.
            workspace_name:          Human-readable workspace name.
            tables:                  All tables in the workspace.
            rules:                   All enabled analytics rules.
            ingestion_data:          table_name → avg_gb_per_day (already normalised to
                                     per-day rate regardless of lookback window).
            connectors:              All data connectors.
            kql_parse_results:       KQL parsing results parallel to `rules`.
            agent_tokens_used:       LLM tokens consumed.
            agent_max_tokens:        LLM token cap.
            agent_run_seconds:       Wall-clock execution time.
            waste_analysis_summary:  Pre-built waste analysis (from WasteAnalyzer).
            days_lookback:           Lookback window used for ingestion query (for display).

        Returns:
            Assembled Report object.
        """
        try:
            logger.info(f"[REPORT] Generating report for job {job_id}")

            # ── Build table → rule mapping ────────────────────────────
            table_usage_map = ReportGenerator._build_table_usage_map(
                rules, kql_parse_results
            )

            # ── Classify tables ───────────────────────────────────────
            archive_candidates  = []
            low_usage_candidates = []
            active_tables        = []

            for table in tables:
                usage_count    = len(table_usage_map.get(table.table_name, []))
                gb_per_day     = ingestion_data.get(table.table_name, 0.0)

                # Tier string normalisation
                tier_str = (
                    table.current_tier.value
                    if hasattr(table.current_tier, "value")
                    else str(table.current_tier)
                )

                # Confidence / bucket assignment
                if usage_count == 0:
                    confidence         = ConfidenceLevel.HIGH
                    parsing_confidence = 1.0
                    recommendation_list = archive_candidates
                elif usage_count <= 2:
                    confidence         = ConfidenceLevel.MEDIUM
                    parsing_confidence = 0.7
                    recommendation_list = low_usage_candidates
                else:
                    confidence         = ConfidenceLevel.HIGH
                    parsing_confidence = 1.0
                    recommendation_list = active_tables

                # ── Cost calculations (all based on gb_per_day) ───────
                monthly_cost_hot     = round(_monthly_ingestion_cost(gb_per_day, tier_str), 4)
                monthly_cost_archive = round(_monthly_archive_cost(gb_per_day), 4)
                monthly_saving       = round(_monthly_savings(gb_per_day, tier_str), 4)
                annual_saving        = round(monthly_saving * MONTHS_PER_YEAR, 2)

                rec = TableRecommendation(
                    table_name=table.table_name,
                    current_tier=table.current_tier,
                    ingestion_gb_per_day=round(gb_per_day, 6),
                    ingestion_gb_per_month=round(gb_per_day * DAYS_PER_MONTH, 4),
                    rule_coverage_count=usage_count,
                    rule_names=table_usage_map.get(table.table_name, [])[:5],
                    confidence=confidence,
                    parsing_confidence=parsing_confidence,
                    monthly_cost_hot=monthly_cost_hot,
                    monthly_cost_archive=monthly_cost_archive,
                    monthly_savings=monthly_saving,
                    annual_savings=annual_saving,
                    log_category=get_table_category(table.table_name),
                    notes=ReportGenerator._generate_notes(
                        table.table_name, usage_count, gb_per_day,
                        table.retention_days
                    )
                )

                recommendation_list.append(rec)

            # Sort each bucket by annual savings descending
            for bucket in (archive_candidates, low_usage_candidates, active_tables):
                bucket.sort(key=lambda x: x.annual_savings, reverse=True)

            # ── Connector coverage ────────────────────────────────────
            connector_coverage = ReportGenerator._build_connector_coverage(
                connectors, table_usage_map
            )

            # ── Warnings ──────────────────────────────────────────────
            warnings = ReportGenerator._generate_warnings(
                tables, kql_parse_results, archive_candidates
            )

            # ── Executive summary ─────────────────────────────────────
            summary = ReportGenerator._calculate_summary(
                tables,
                archive_candidates,
                low_usage_candidates,
                active_tables,
                days_lookback=days_lookback,
            )

            # ── Execution metadata ────────────────────────────────────
            metadata = ExecutionMetadata(
                agent_run_timestamp=datetime.utcnow(),
                agent_completion_time_seconds=agent_run_seconds,
                kql_parsing_success_rate=ReportGenerator._calculate_parse_success_rate(
                    kql_parse_results
                ),
                tables_analyzed=len(tables),
                rules_analyzed=len(rules),
                workbooks_analyzed=0,
                hunt_queries_analyzed=0,
                agent_tokens_used=agent_tokens_used,
                agent_tokens_limit=agent_max_tokens
            )

            # ── Assemble report ───────────────────────────────────────
            report = Report(
                job_id=job_id,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                timestamp=datetime.utcnow(),
                days_lookback=days_lookback,
                summary=summary,
                archive_candidates=archive_candidates,
                low_usage_candidates=low_usage_candidates,
                active_tables=active_tables,
                connector_coverage=connector_coverage,
                waste_analysis=waste_analysis_summary,
                warnings=warnings,
                metadata=metadata
            )

            # logger.info(
            #     f"[REPORT] Report generated: "
            #     f"{len(archive_candidates)} archive candidates | "
            #     f"${summary.total_monthly_cost:.2f}/month total ingestion | "
            #     f"${summary.total_monthly_savings:.2f}/month saveable | "
            #     f"${summary.total_annual_savings:,.0f} potential annual savings"
            # )
            logger.info(
                            f"[REPORT] Report generated: "
                            f"{len(archive_candidates)} archive candidates | "
                            f"${summary.total_monthly_cost_hot:.2f}/month total ingestion | "
                            f"${summary.total_monthly_savings:.2f}/month saveable | "
                            f"${summary.total_annual_savings:,.0f} potential annual savings"
                        )            

            return report

        except Exception as e:
            logger.error(f"[REPORT] Report generation failed: {e}", exc_info=True)
            raise

    # ──────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_table_usage_map(
        rules: List[AnalyticsRule],
        kql_parse_results: List[KqlParseResult]
    ) -> Dict[str, List[str]]:
        """Build mapping: table_name → [rule_name, ...]"""
        usage_map: Dict[str, List[str]] = defaultdict(list)

        for rule, parse_result in zip(rules, kql_parse_results):
            if parse_result.success:
                for table in parse_result.tables:
                    usage_map[table].append(rule.rule_name)

        return dict(usage_map)

    @staticmethod
    def _build_connector_coverage(
        connectors: List[DataConnector],
        table_usage_map: Dict[str, List[str]]
    ) -> List[ConnectorCoverageItem]:
        """Build connector → table coverage items."""
        coverage_items = []

        for connector in connectors:
            tables_with_coverage = sum(
                1 for t in connector.tables_fed if t in table_usage_map
            )
            coverage_items.append(
                ConnectorCoverageItem(
                    connector_name=connector.connector_name,
                    connector_type=connector.connector_type,
                    tables_fed=connector.tables_fed,
                    tables_with_coverage=tables_with_coverage,
                    tables_without_coverage=len(connector.tables_fed) - tables_with_coverage
                )
            )

        return coverage_items

    @staticmethod
    def _generate_warnings(
        tables: List[TableIngestionData],
        kql_parse_results: List[KqlParseResult],
        archive_candidates: List[TableRecommendation]
    ) -> List[ReportWarning]:
        """Generate actionable warnings."""
        warnings = []

        # Warn on low-confidence KQL parsing
        for result in kql_parse_results:
            conf_score = CONFIDENCE_ENUM_MAPPING.get(result.confidence, 0.0)
            if conf_score < 0.5 and not result.success:
                warnings.append(
                    ReportWarning(
                        warning_type="COMPLEX_KQL",
                        table_name="N/A",
                        description="Complex KQL with functions/aliases detected — manual review recommended",
                        recommendation="Review the rule manually to verify table extraction"
                    )
                )

        # Warn on high-cost Hot-tier tables flagged for archiving
        for candidate in archive_candidates:
            if (
                candidate.current_tier == TierType.HOT
                and candidate.monthly_cost_hot > 100
            ):
                warnings.append(
                    ReportWarning(
                        warning_type="HIGH_COST_ARCHIVE",
                        table_name=candidate.table_name,
                        description=(
                            f"High-cost table (${candidate.monthly_cost_hot:.2f}/month) "
                            f"with no analytics rule coverage"
                        ),
                        recommendation=(
                            "Verify no external dashboards, workbooks, or SIEM playbooks "
                            "depend on this table before archiving"
                        )
                    )
                )

        return warnings

    @staticmethod
    def _calculate_summary(
        tables: List[TableIngestionData],
        archive_candidates: List[TableRecommendation],
        low_usage_candidates: List[TableRecommendation],
        active_tables: List[TableRecommendation],
        days_lookback: int = 30,
    ) -> ReportSummary:
        """
        Calculate executive summary.

        Cost math:
          monthly_cost_hot  = gb_per_day × 30 × $4.30
          monthly_savings   = monthly_cost_hot  - monthly_cost_archive
          annual_savings    = monthly_savings   × 12

        All three are already pre-computed on each TableRecommendation;
        we just sum them here.
        """
        all_recs = archive_candidates + low_usage_candidates + active_tables

        # ── GB totals ─────────────────────────────────────────────────
        total_gb_per_day   = sum(r.ingestion_gb_per_day    for r in all_recs)
        total_gb_per_month = sum(r.ingestion_gb_per_month  for r in all_recs)

        # ── Cost totals ───────────────────────────────────────────────
        # Only archive_candidates contribute real savings (no rule coverage)
        total_monthly_cost_hot     = sum(r.monthly_cost_hot     for r in all_recs)
        total_monthly_cost_archive = sum(r.monthly_cost_archive for r in all_recs)

        # Savings = only from archive candidates (the ones we'd actually move)
        saveable_monthly = sum(r.monthly_savings for r in archive_candidates)
        saveable_annual  = sum(r.annual_savings  for r in archive_candidates)

        # ── Tier breakdown ────────────────────────────────────────────
        tier_breakdown = {
            "Hot":     sum(1 for r in all_recs if r.current_tier == TierType.HOT),
            "Basic":   sum(1 for r in all_recs if r.current_tier == TierType.BASIC),
            "Archive": sum(1 for r in all_recs if r.current_tier == TierType.ARCHIVE),
        }

        # ── Confidence breakdown ──────────────────────────────────────
        confidence_breakdown = {
            "HIGH":   sum(1 for r in all_recs if r.confidence == ConfidenceLevel.HIGH),
            "MEDIUM": sum(1 for r in all_recs if r.confidence == ConfidenceLevel.MEDIUM),
            "LOW":    sum(1 for r in all_recs if r.confidence == ConfidenceLevel.LOW),
        }

        return ReportSummary(
            total_tables_analyzed=len(tables),
            days_lookback=days_lookback,
            total_ingestion_gb_per_day=round(total_gb_per_day, 4),
            total_ingestion_gb_per_month=round(total_gb_per_month, 2),
            total_monthly_cost_hot=round(total_monthly_cost_hot, 2),
            total_monthly_cost_archive=round(total_monthly_cost_archive, 2),
            total_monthly_savings=round(saveable_monthly, 2),
            total_annual_savings=round(saveable_annual, 2),
            tables_by_tier=tier_breakdown,
            tables_by_confidence=confidence_breakdown,
        )

    @staticmethod
    def _generate_notes(
        table_name: str,
        usage_count: int,
        gb_per_day: float,
        retention_days: int
    ) -> str:
        notes = []

        if usage_count == 0:
            notes.append("No analytics rules reference this table")
        elif usage_count <= 2:
            notes.append(f"Only {usage_count} rule(s) reference this table")

        if gb_per_day < 0.001:
            notes.append("Near-zero ingestion volume")
        elif gb_per_day < 0.01:
            notes.append("Minimal ingestion volume")
        elif gb_per_day > 10:
            notes.append(f"High ingestion: {gb_per_day:.2f} GB/day")

        if retention_days < 30:
            notes.append(f"Short retention policy: {retention_days} days")

        return "; ".join(notes) if notes else "Archive candidate for cost optimisation"

    @staticmethod
    def _calculate_parse_success_rate(kql_parse_results: List[KqlParseResult]) -> float:
        if not kql_parse_results:
            return 0.0
        return sum(1 for r in kql_parse_results if r.success) / len(kql_parse_results)


# ── Singleton ─────────────────────────────────────────────────────────
report_generator = ReportGenerator()