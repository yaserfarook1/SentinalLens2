/**
 * Cost Summary Table Component
 * Displays all tables sorted by monthly cost with ingestion and category details
 */

import React, { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { TableRecommendation } from "@/lib/types";
import { formatCurrency } from "@/lib/formatters";
import { getTierColor } from "@/lib/colors";

interface CostSummaryTableProps {
  tables: TableRecommendation[];
}

export function CostSummaryTable({ tables }: CostSummaryTableProps) {
  const [showZeroCost, setShowZeroCost] = useState(false);

  // Memoize sorted tables and totals to avoid recalculation on every render
  const data = useMemo(() => {
    const allTables = [...tables].sort((a, b) => b.monthly_cost_hot - a.monthly_cost_hot);

    // Filter out $0 cost tables if toggle is off
    const displayTables = showZeroCost
      ? allTables
      : allTables.filter(t => t.monthly_cost_hot > 0);

    const totalIngestion = allTables.reduce((sum, t) => sum + t.ingestion_gb_per_day, 0);
    const totalCost = allTables.reduce((sum, t) => sum + t.monthly_cost_hot, 0);
    const zeroCostCount = allTables.filter(t => t.monthly_cost_hot === 0).length;

    return { displayTables, allTables, totalIngestion, totalCost, zeroCostCount };
  }, [tables, showZeroCost]);

  if (data.allTables.length === 0) {
    return <p className="text-gray-600 text-center py-8">No tables found</p>;
  }

  return (
    <div className="space-y-4">
      {data.zeroCostCount > 0 && (
        <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <input
            type="checkbox"
            id="show-zero-cost"
            checked={showZeroCost}
            onChange={(e) => setShowZeroCost(e.target.checked)}
            className="rounded"
          />
          <label htmlFor="show-zero-cost" className="text-sm text-blue-900 cursor-pointer flex-1">
            Show {data.zeroCostCount} tables with $0 cost ({showZeroCost ? "hide" : "show"})
          </label>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left px-4 py-3 font-semibold text-gray-900">
              Table Name
            </th>
            <th className="text-left px-4 py-3 font-semibold text-gray-900">
              Category
            </th>
            <th className="text-left px-4 py-3 font-semibold text-gray-900">
              Tier
            </th>
            <th className="text-right px-4 py-3 font-semibold text-gray-900">
              Ingestion (GB/day)
            </th>
            <th className="text-right px-4 py-3 font-semibold text-gray-900">
              Cost/Month
            </th>
            <th className="text-right px-4 py-3 font-semibold text-gray-900">
              Rules
            </th>
          </tr>
        </thead>
        <tbody>
          {data.displayTables.map((table) => (
            <tr
              key={table.table_name}
              className="border-b border-gray-100 hover:bg-gray-50"
            >
              <td className="px-4 py-3 font-medium text-gray-900">
                {table.table_name}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                  {table.log_category || "Other"}
                </span>
              </td>
              <td className="px-4 py-3">
                <Badge variant={getTierColor(table.current_tier)}>
                  {table.current_tier}
                </Badge>
              </td>
              <td className="px-4 py-3 text-right text-gray-600">
                {table.ingestion_gb_per_day.toFixed(2)} GB/day
              </td>
              <td className="px-4 py-3 text-right font-semibold text-gray-900">
                {formatCurrency(table.monthly_cost_hot)}
              </td>
              <td className="px-4 py-3 text-right text-gray-600">
                {table.rule_coverage_count}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-gray-200 bg-gray-50 font-semibold">
            <td colSpan={3} className="px-4 py-3 text-gray-900">
              TOTALS
            </td>
            <td className="px-4 py-3 text-right text-gray-900">
              {data.totalIngestion.toFixed(2)} GB/day
            </td>
            <td className="px-4 py-3 text-right text-gray-900">
              {formatCurrency(data.totalCost)}
            </td>
            <td></td>
          </tr>
        </tfoot>
      </table>
      </div>
    </div>
  );
}
