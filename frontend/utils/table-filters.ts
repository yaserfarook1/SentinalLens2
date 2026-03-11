/**
 * Table Filtering Utilities
 * Helper functions for filtering TableRecommendation arrays
 */

import { TableRecommendation } from "@/lib/types";

export interface TableFilterOptions {
  searchTerm?: string;
  tiers?: string[];
  confidence?: ("HIGH" | "MEDIUM" | "LOW")[];
  ingestionMin?: number;
  ingestionMax?: number;
  ruleCountFilter?: "all" | "zero" | "few" | "many";
}

/**
 * Categorize rule count into buckets
 */
export function getRuleCountCategory(
  count: number
): "zero" | "few" | "many" {
  if (count === 0) return "zero";
  if (count <= 2) return "few";
  return "many";
}

/**
 * Filter tables based on multiple criteria
 */
export function filterTables(
  tables: TableRecommendation[],
  filters: TableFilterOptions
): TableRecommendation[] {
  return tables.filter((table) => {
    // Search by table name
    if (filters.searchTerm) {
      const search = filters.searchTerm.toLowerCase();
      if (!table.table_name.toLowerCase().includes(search)) {
        return false;
      }
    }

    // Filter by tier
    if (filters.tiers && filters.tiers.length > 0) {
      if (!filters.tiers.includes(table.current_tier)) {
        return false;
      }
    }

    // Filter by confidence
    if (filters.confidence && filters.confidence.length > 0) {
      if (!filters.confidence.includes(table.confidence)) {
        return false;
      }
    }

    // Filter by ingestion range
    if (filters.ingestionMin !== undefined) {
      if (table.ingestion_gb_per_day < filters.ingestionMin) {
        return false;
      }
    }

    if (filters.ingestionMax !== undefined) {
      if (table.ingestion_gb_per_day > filters.ingestionMax) {
        return false;
      }
    }

    // Filter by rule count category
    if (filters.ruleCountFilter && filters.ruleCountFilter !== "all") {
      const category = getRuleCountCategory(table.rule_coverage_count);
      if (category !== filters.ruleCountFilter) {
        return false;
      }
    }

    return true;
  });
}

/**
 * Get unique tiers from tables
 */
export function getUniqueTiers(tables: TableRecommendation[]): string[] {
  const tiers = new Set(tables.map((t) => t.current_tier));
  return Array.from(tiers).sort();
}

/**
 * Get statistics for filter options
 */
export function getFilterStats(
  tables: TableRecommendation[],
  filters: TableFilterOptions
) {
  const filtered = filterTables(tables, filters);
  const totalTables = tables.length;
  const filteredCount = filtered.length;
  const totalCost = filtered.reduce((sum, t) => sum + t.monthly_cost_hot, 0);
  const totalIngestion = filtered.reduce(
    (sum, t) => sum + t.ingestion_gb_per_day,
    0
  );
  const totalSavings = filtered.reduce((sum, t) => sum + t.annual_savings, 0);

  return {
    totalTables,
    filteredCount,
    totalCost,
    totalIngestion,
    totalSavings,
    hiddenCount: totalTables - filteredCount,
  };
}

/**
 * Get display text for rule count category
 */
export function getRuleCountLabel(category: "zero" | "few" | "many"): string {
  const labels = {
    zero: "No Rules (0)",
    few: "Few Rules (1-2)",
    many: "Many Rules (3+)",
  };
  return labels[category];
}
