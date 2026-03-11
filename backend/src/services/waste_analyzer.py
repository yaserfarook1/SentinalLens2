"""
Waste Analysis Service - Identifies cost optimization opportunities
Analyzes rule-to-table mapping and identifies unused ingestion

PRICING (matching Azure Sentinel workbook):
  - Pay-as-you-go ingestion: $4.30/GB
  - Basic logs ingestion:    $0.65/GB
  - Archive tier:            $0.026/GB/month (retention only, no ingestion charge)
  - All costs normalized to monthly (30-day) and annual (365-day)
"""

import logging
import re
from typing import Dict, List, Set, Tuple, Optional
from src.models.schemas import (
    TableIngestionInfo, RuleTableMapping, WastedTable, WasteAnalysisSummary,
    AnalyticsRule
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Azure Sentinel Pricing Constants  (USD, as of 2025)
# ─────────────────────────────────────────────────────────────
PRICE_HOT_PER_GB      = 4.30    # Analytics / Hot tier ingestion $/GB
PRICE_BASIC_PER_GB    = 0.65    # Basic logs ingestion $/GB
PRICE_ARCHIVE_PER_GB  = 0.026   # Archive retention $/GB/month (flat storage)
DAYS_PER_MONTH        = 30.0
DAYS_PER_YEAR         = 365.0


class WasteAnalyzer:
    """Analyzes wasted resources and rule-to-table mapping"""

    # ------------------------------------------------------------------
    # KQL Table Extraction
    # ------------------------------------------------------------------

    def extract_tables_from_kql(self, kql_query: str, all_table_names: Set[str]) -> Set[str]:
        """
        Extract table names referenced in a KQL query.
        Uses whole-word regex matching to avoid partial hits.
        """
        if not kql_query:
            return set()

        tables_found = set()
        try:
            for table_name in all_table_names:
                escaped = re.escape(table_name)
                pattern = rf'\b{escaped}\b'
                if re.search(pattern, kql_query, re.IGNORECASE):
                    tables_found.add(table_name)
        except Exception as e:
            logger.warning(f"[WASTE] Error extracting tables from KQL: {e}")

        return tables_found

    # ------------------------------------------------------------------
    # Cost Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _monthly_ingestion_cost(gb_per_day: float, tier: str = "Hot") -> float:
        """
        Calculate monthly ingestion cost from daily ingestion rate.

        Args:
            gb_per_day:  Average GB ingested per day (from Usage table query).
            tier:        "Hot" (Analytics) | "Basic" | "Archive"

        Returns:
            Monthly cost in USD.
        """
        gb_per_month = gb_per_day * DAYS_PER_MONTH

        if tier == "Basic":
            return gb_per_month * PRICE_BASIC_PER_GB
        elif tier == "Archive":
            # Archive has no ingestion cost; only retention cost
            return gb_per_month * PRICE_ARCHIVE_PER_GB
        else:
            # Hot / Analytics (default)
            return gb_per_month * PRICE_HOT_PER_GB

    @staticmethod
    def _monthly_archive_cost(gb_per_day: float) -> float:
        """
        Cost if the table were moved to Archive tier.
        Archive = $0.026/GB/month stored (no ingestion charge).
        """
        gb_per_month = gb_per_day * DAYS_PER_MONTH
        return gb_per_month * PRICE_ARCHIVE_PER_GB

    @staticmethod
    def _monthly_savings(current_gb_per_day: float, current_tier: str = "Hot") -> float:
        """
        How much we save per month by moving to Archive.
        Returns 0 if already on Archive or Basic (savings would be minimal).
        """
        if current_tier in ("Archive",):
            return 0.0
        current_cost  = WasteAnalyzer._monthly_ingestion_cost(current_gb_per_day, current_tier)
        archive_cost  = WasteAnalyzer._monthly_archive_cost(current_gb_per_day)
        return max(0.0, current_cost - archive_cost)

    @staticmethod
    def _waste_severity(monthly_cost: float) -> str:
        if monthly_cost > 100:
            return "CRITICAL"
        elif monthly_cost > 30:
            return "HIGH"
        elif monthly_cost > 5:
            return "MEDIUM"
        else:
            return "LOW"

    # ------------------------------------------------------------------
    # Main Analysis
    # ------------------------------------------------------------------

    def analyze_waste(
        self,
        rules: List[AnalyticsRule],
        ingestion_data: Dict[str, Tuple[float, str]],
        days_lookback: int = 30,
    ) -> WasteAnalysisSummary:
        """
        Analyze waste by mapping analytics rules → tables.

        Args:
            rules:           List of enabled analytics rules (with .kql_query).
            ingestion_data:  table_name → (avg_gb_per_day, last_ingestion_timestamp)
                             NOTE: avg_gb_per_day must already be normalised to per-day
                             (i.e. total_gb_in_period / days_lookback) before calling this.
            days_lookback:   How many days the ingestion query covered (for reference only;
                             cost math uses gb_per_day so it is already normalised).

        Returns:
            WasteAnalysisSummary
        """
        logger.info(
            f"[WASTE] Starting waste analysis: {len(rules)} rules, "
            f"{len(ingestion_data)} tables with data"
        )

        all_table_names = set(ingestion_data.keys())

        # ── Step 1: Build rule ↔ table mappings ──────────────────────
        rule_table_mapping: Dict[str, Set[str]] = {}   # rule_id  → {tables}
        table_rule_mapping: Dict[str, Set[str]] = {}   # table    → {rule_names}

        for rule in rules:
            tables_in_rule = self.extract_tables_from_kql(rule.kql_query, all_table_names)
            rule_table_mapping[rule.rule_id] = tables_in_rule

            for table in tables_in_rule:
                if table not in table_rule_mapping:
                    table_rule_mapping[table] = set()
                table_rule_mapping[table].add(rule.rule_name)

        logger.info(
            f"[WASTE] Mapped {len(rule_table_mapping)} rules "
            f"to {len(table_rule_mapping)} tables"
        )

        # ── Step 2: Classify tables as wasted vs. covered ────────────
        wasted_tables: List[WastedTable] = []
        wasted_gb_per_day    = 0.0
        wasted_monthly_cost  = 0.0
        tables_with_rules    = 0

        # Running totals for ALL tables (used + unused)
        total_gb_per_day   = 0.0
        total_monthly_cost = 0.0

        for table_name, (gb_per_day, last_ingestion) in ingestion_data.items():
            monthly_cost = self._monthly_ingestion_cost(gb_per_day, tier="Hot")
            total_gb_per_day   += gb_per_day
            total_monthly_cost += monthly_cost

            if table_name not in table_rule_mapping or not table_rule_mapping[table_name]:
                # ── Unused table ─────────────────────────────────────
                monthly_saving = self._monthly_savings(gb_per_day, current_tier="Hot")

                wasted_gb_per_day   += gb_per_day
                wasted_monthly_cost += monthly_cost

                wasted_tables.append(
                    WastedTable(
                        table_name=table_name,
                        ingestion_gb_90d=round(gb_per_day * 90, 4),   # kept for schema compat
                        cost_hot_90d=round(monthly_cost * 3, 4),       # 3 months ≈ 90 days
                        last_ingestion=last_ingestion,
                        waste_potential=self._waste_severity(monthly_cost),
                        # Extended fields (used by report frontend)
                        ingestion_gb_per_day=round(gb_per_day, 6),
                        monthly_cost_hot=round(monthly_cost, 4),
                        monthly_cost_archive=round(
                            self._monthly_archive_cost(gb_per_day), 4
                        ),
                        monthly_savings=round(monthly_saving, 4),
                        annual_savings=round(monthly_saving * 12, 2),
                    )
                )
            else:
                tables_with_rules += 1

        # Sort wasted tables: highest monthly cost first
        wasted_tables.sort(key=lambda x: x.monthly_cost_hot, reverse=True)

        # ── Step 3: Totals ───────────────────────────────────────────
        wasted_percentage = (
            (wasted_monthly_cost / total_monthly_cost * 100)
            if total_monthly_cost > 0 else 0.0
        )
        total_annual_cost   = total_monthly_cost  * 12
        wasted_annual_cost  = wasted_monthly_cost * 12
        potential_annual_savings = sum(t.annual_savings for t in wasted_tables)

        # ── Step 4: Rule coverage stats ──────────────────────────────
        rule_counts = [len(rs) for rs in table_rule_mapping.values()]
        avg_rules_per_table      = sum(rule_counts) / len(rule_counts) if rule_counts else 0.0
        tables_with_high_coverage = sum(1 for c in rule_counts if c >= 5)

        # ── Step 5: Assemble summary ─────────────────────────────────
        summary = WasteAnalysisSummary(
            tables_analyzed=len(ingestion_data),
            tables_with_data=len(ingestion_data),
            tables_with_rules=tables_with_rules,
            tables_without_rules=len(wasted_tables),

            # GB figures (per-day for clarity; 90d kept for schema compat)
            total_ingestion_gb_90d=round(total_gb_per_day * 90, 2),
            wasted_ingestion_gb_90d=round(wasted_gb_per_day * 90, 2),
            total_ingestion_gb_per_day=round(total_gb_per_day, 4),
            wasted_ingestion_gb_per_day=round(wasted_gb_per_day, 4),

            # Cost figures
            total_cost_hot_90d=round(total_monthly_cost * 3, 2),   # schema compat
            wasted_cost_hot_90d=round(wasted_monthly_cost * 3, 2), # schema compat
            total_monthly_cost=round(total_monthly_cost, 2),
            wasted_monthly_cost=round(wasted_monthly_cost, 2),
            total_annual_cost=round(total_annual_cost, 2),
            wasted_annual_cost=round(wasted_annual_cost, 2),
            potential_annual_savings=round(potential_annual_savings, 2),

            wasted_percentage=round(wasted_percentage, 2),
            top_wasted_tables=wasted_tables[:10],

            rule_coverage_stats={
                "avg_rules_per_table": round(avg_rules_per_table, 1),
                "tables_with_high_coverage": tables_with_high_coverage,
                "tables_with_zero_coverage": len(wasted_tables),
            },
        )

        logger.info(
            f"[WASTE] Analysis complete: "
            f"${summary.wasted_monthly_cost:.2f}/month wasted "
            f"({summary.wasted_percentage}%) "
            f"out of ${summary.total_monthly_cost:.2f}/month total | "
            f"Potential annual savings: ${summary.potential_annual_savings:,.2f}"
        )

        return summary