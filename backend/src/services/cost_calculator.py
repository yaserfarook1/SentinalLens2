"""
Cost Calculator Service

Calculates ingestion costs and savings estimates.

Pricing (Azure Sentinel pay-as-you-go, 2025):
  - Analytics / Hot tier ingestion:  $4.30 /GB
  - Basic logs ingestion:            $0.65 /GB
  - Archive retention:               $0.026/GB/month  (no ingestion charge)

NOTE: The old version called the Azure Retail Prices API and silently fell back
to wrong constants ($0.10/GB/day = $3.00/GB/month) when the call failed.
That is removed. Pricing is now a single source-of-truth constant set that
matches the Azure workbook figures.  If you need region-specific pricing,
override PRICE_HOT_PER_GB via an environment variable.
"""

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Azure Sentinel Pricing  (USD, pay-as-you-go, East US 2025)
#  Override with env vars if needed for other regions.
# ─────────────────────────────────────────────────────────────
PRICE_HOT_PER_GB     = float(os.getenv("SENTINEL_PRICE_HOT_GB",     "4.30"))
PRICE_BASIC_PER_GB   = float(os.getenv("SENTINEL_PRICE_BASIC_GB",   "0.65"))
PRICE_ARCHIVE_PER_GB = float(os.getenv("SENTINEL_PRICE_ARCHIVE_GB", "0.026"))

DAYS_PER_MONTH  = 30.0
MONTHS_PER_YEAR = 12.0


class CostCalculator:
    """Calculate ingestion costs and savings — all based on gb_per_day input."""

    @staticmethod
    def calculate_table_costs(
        ingestion_gb_per_day: float,
        current_tier,           # TierType enum OR plain string
        target_tier: str = "Archive"
    ) -> Dict[str, float]:
        """
        Calculate monthly / annual costs for a single table.

        Args:
            ingestion_gb_per_day:  Average GB ingested per day.
            current_tier:          Current tier — TierType enum or "Hot"/"Basic"/"Archive" string.
            target_tier:           Target tier for migration (almost always "Archive").

        Returns:
            {
                "daily_cost_hot":      float,
                "daily_cost_archive":  float,
                "monthly_cost_hot":    float,
                "monthly_cost_archive":float,
                "monthly_savings":     float,
                "annual_savings":      float,
            }

        Cost formula (single source of truth):
            monthly_cost = ingestion_gb_per_day × 30 × price_per_gb
        """
        try:
            # Normalise tier to plain string
            tier_str = (
                current_tier.value
                if hasattr(current_tier, "value")
                else str(current_tier)
            )

            # ── Current-tier rates ────────────────────────────────────
            if tier_str == "Basic":
                rate_current = PRICE_BASIC_PER_GB
            elif tier_str == "Archive":
                rate_current = PRICE_ARCHIVE_PER_GB
            else:
                rate_current = PRICE_HOT_PER_GB   # Hot / Analytics (default)

            # ── Target-tier rates (always Archive in practice) ────────
            rate_archive = PRICE_ARCHIVE_PER_GB

            # ── Daily costs ───────────────────────────────────────────
            daily_cost_hot     = ingestion_gb_per_day * rate_current
            daily_cost_archive = ingestion_gb_per_day * rate_archive

            # ── Monthly costs (gb_per_day × 30 × price) ──────────────
            monthly_cost_hot     = ingestion_gb_per_day * DAYS_PER_MONTH * rate_current
            monthly_cost_archive = ingestion_gb_per_day * DAYS_PER_MONTH * rate_archive
            monthly_savings      = max(0.0, monthly_cost_hot - monthly_cost_archive)
            annual_savings       = monthly_savings * MONTHS_PER_YEAR

            logger.debug(
                f"[COST] {ingestion_gb_per_day:.4f} GB/day | "
                f"tier={tier_str} | "
                f"monthly_hot=${monthly_cost_hot:.2f} | "
                f"monthly_savings=${monthly_savings:.2f}"
            )

            return {
                "daily_cost_hot":       round(daily_cost_hot, 6),
                "daily_cost_archive":   round(daily_cost_archive, 6),
                "monthly_cost_hot":     round(monthly_cost_hot, 4),
                "monthly_cost_archive": round(monthly_cost_archive, 4),
                "monthly_savings":      round(monthly_savings, 4),
                "annual_savings":       round(annual_savings, 2),
            }

        except Exception as e:
            logger.error(f"[COST] Cost calculation failed: {e}")
            return {
                "daily_cost_hot":       0.0,
                "daily_cost_archive":   0.0,
                "monthly_cost_hot":     0.0,
                "monthly_cost_archive": 0.0,
                "monthly_savings":      0.0,
                "annual_savings":       0.0,
            }

    @staticmethod
    def aggregate_workspace_savings(tables_data: Dict[str, Dict]) -> Dict[str, float]:
        """
        Aggregate savings across all tables in a workspace.

        Args:
            tables_data: {table_name: cost_dict} where cost_dict is the return
                         value of calculate_table_costs().

        Returns:
            Aggregated totals dict.
        """
        total_monthly_cost_hot     = 0.0
        total_monthly_cost_archive = 0.0
        total_monthly_savings      = 0.0

        for costs in tables_data.values():
            total_monthly_cost_hot     += costs.get("monthly_cost_hot", 0.0)
            total_monthly_cost_archive += costs.get("monthly_cost_archive", 0.0)
            total_monthly_savings      += costs.get("monthly_savings", 0.0)

        annual_savings = total_monthly_savings * MONTHS_PER_YEAR

        return {
            "total_monthly_cost_hot":     round(total_monthly_cost_hot, 2),
            "total_monthly_cost_archive": round(total_monthly_cost_archive, 2),
            "total_monthly_savings":      round(total_monthly_savings, 2),
            "total_annual_savings":       round(annual_savings, 2),
            "savings_percentage": round(
                (total_monthly_savings / total_monthly_cost_hot * 100)
                if total_monthly_cost_hot > 0 else 0.0,
                1
            ),
        }

    @staticmethod
    def get_savings_impact_summary(savings_amount: float) -> str:
        """Human-readable savings impact summary (monthly input → annual output)."""
        annual = savings_amount * MONTHS_PER_YEAR

        if annual > 100_000:
            return f"Substantial savings: ${annual:,.0f}/year could fund critical security initiatives"
        elif annual > 50_000:
            return f"Significant savings: ${annual:,.0f}/year enables important optimisations"
        elif annual > 10_000:
            return f"Meaningful savings: ${annual:,.0f}/year improves operational efficiency"
        elif annual > 1_000:
            return f"Moderate savings: ${annual:,.0f}/year reduces infrastructure costs"
        else:
            return f"Minor savings: ${annual:,.0f}/year from table optimisation"


# ── Singleton ─────────────────────────────────────────────────────────
cost_calculator = CostCalculator()