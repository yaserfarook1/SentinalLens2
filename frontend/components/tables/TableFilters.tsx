"use client";

import React, { useState, useMemo, useEffect } from "react";
import { TableRecommendation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  TableFilterOptions,
  filterTables,
  getUniqueTiers,
  getFilterStats,
  getRuleCountLabel,
} from "@/utils/table-filters";

interface TableFiltersProps {
  tables: TableRecommendation[];
  onFilter: (filtered: TableRecommendation[]) => void;
}

export function TableFilters({ tables, onFilter }: TableFiltersProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [tierFilter, setTierFilter] = useState<string[]>([]);
  const [confidenceFilter, setConfidenceFilter] = useState<
    ("HIGH" | "MEDIUM" | "LOW")[]
  >([]);
  const [ingestionMin, setIngestionMin] = useState(0);
  const [ingestionMax, setIngestionMax] = useState(999);
  const [ruleCountFilter, setRuleCountFilter] = useState<
    "all" | "zero" | "few" | "many"
  >("all");

  // Initialize tier filter with all available tiers
  useMemo(() => {
    const uniqueTiers = getUniqueTiers(tables);
    if (tierFilter.length === 0 && uniqueTiers.length > 0) {
      setTierFilter(uniqueTiers);
    }
  }, [tables]);

  // Initialize confidence filter with all levels
  useMemo(() => {
    if (confidenceFilter.length === 0) {
      setConfidenceFilter(["HIGH", "MEDIUM", "LOW"]);
    }
  }, []);

  // Get max ingestion for slider
  const maxIngestionInData = Math.ceil(
    Math.max(...tables.map((t) => t.ingestion_gb_per_day), 1)
  );

  // Build filter options
  const filters: TableFilterOptions = {
    searchTerm: searchTerm || undefined,
    tiers: tierFilter.length > 0 ? tierFilter : undefined,
    confidence: confidenceFilter.length > 0 ? confidenceFilter : undefined,
    ingestionMin: ingestionMin > 0 ? ingestionMin : undefined,
    ingestionMax: ingestionMax < maxIngestionInData ? ingestionMax : undefined,
    ruleCountFilter: ruleCountFilter !== "all" ? ruleCountFilter : undefined,
  };

  // Apply filters (compute only, don't call onFilter here)
  const filtered = useMemo(() => {
    return filterTables(tables, filters);
  }, [filters, tables]);

  // Notify parent of filtered results via separate effect
  useEffect(() => {
    onFilter(filtered);
  }, [filtered, onFilter]);

  // Get stats
  const stats = useMemo(
    () => getFilterStats(tables, filters),
    [tables, filters]
  );

  // Toggle tier filter
  const toggleTier = (tier: string) => {
    setTierFilter((prev) =>
      prev.includes(tier) ? prev.filter((t) => t !== tier) : [...prev, tier]
    );
  };

  // Toggle confidence filter
  const toggleConfidence = (level: "HIGH" | "MEDIUM" | "LOW") => {
    setConfidenceFilter((prev) =>
      prev.includes(level) ? prev.filter((c) => c !== level) : [...prev, level]
    );
  };

  // Reset all filters
  const resetFilters = () => {
    setSearchTerm("");
    setTierFilter(getUniqueTiers(tables));
    setConfidenceFilter(["HIGH", "MEDIUM", "LOW"]);
    setIngestionMin(0);
    setIngestionMax(maxIngestionInData);
    setRuleCountFilter("all");
  };

  return (
    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-4">
      {/* Filter Header */}
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-900">Filters</h3>
        {(searchTerm ||
          tierFilter.length < getUniqueTiers(tables).length ||
          confidenceFilter.length < 3 ||
          ingestionMin > 0 ||
          ingestionMax < maxIngestionInData ||
          ruleCountFilter !== "all") && (
          <button
            onClick={resetFilters}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Reset All
          </button>
        )}
      </div>

      {/* Search Input */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Search Table Name
        </label>
        <input
          type="text"
          placeholder="Filter by table name..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* 3-Column Layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tier Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Pricing Tier
          </label>
          <div className="space-y-2">
            {getUniqueTiers(tables).map((tier) => (
              <label key={tier} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={tierFilter.includes(tier)}
                  onChange={() => toggleTier(tier)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{tier}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Confidence Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Confidence Level
          </label>
          <div className="space-y-2">
            {(["HIGH", "MEDIUM", "LOW"] as const).map((level) => (
              <label key={level} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={confidenceFilter.includes(level)}
                  onChange={() => toggleConfidence(level)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{level}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Ingestion Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Ingestion (GB/day)
          </label>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">Min</label>
              <input
                type="number"
                min="0"
                max={maxIngestionInData}
                value={ingestionMin}
                onChange={(e) => setIngestionMin(Number(e.target.value))}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Max</label>
              <input
                type="number"
                min="0"
                max={maxIngestionInData}
                value={ingestionMax}
                onChange={(e) => setIngestionMax(Number(e.target.value))}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Rule Count Filter */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Rule Coverage
        </label>
        <div className="flex gap-3 flex-wrap">
          {(["all", "zero", "few", "many"] as const).map((option) => (
            <label key={option} className="flex items-center gap-2">
              <input
                type="radio"
                name="ruleCount"
                value={option}
                checked={ruleCountFilter === option}
                onChange={(e) =>
                  setRuleCountFilter(
                    e.target.value as "all" | "zero" | "few" | "many"
                  )
                }
                className="rounded"
              />
              <span className="text-sm text-gray-700">
                {option === "all"
                  ? "All"
                  : getRuleCountLabel(option as "zero" | "few" | "many")}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Filter Summary */}
      <div className="pt-2 border-t border-gray-200 flex items-center gap-3">
        <Badge variant="default">
          Showing {stats.filteredCount} of {stats.totalTables} tables
        </Badge>
        {stats.hiddenCount > 0 && (
          <span className="text-sm text-gray-600">
            {stats.hiddenCount} hidden by filters
          </span>
        )}
        {stats.filteredCount > 0 && (
          <>
            <span className="text-sm text-gray-600">•</span>
            <span className="text-sm text-gray-600">
              ${stats.totalCost.toFixed(2)}/month •{" "}
              ${stats.totalSavings.toFixed(0)}/year
            </span>
          </>
        )}
      </div>
    </div>
  );
}
