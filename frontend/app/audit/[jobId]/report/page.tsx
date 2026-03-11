"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { CostSummaryTable } from "@/components/tables/CostSummaryTable";
import { TableFilters } from "@/components/tables/TableFilters";
import { Report, TableRecommendation, WasteAnalysisSummary } from "@/lib/types";
import { formatCurrency } from "@/lib/formatters";
import { getConfidenceColor, getTierColor } from "@/lib/colors";
import Link from "next/link";
import {
  downloadFile,
  downloadJSON,
  downloadText,
  copyToClipboard,
  formatExpirationDate,
} from "@/utils/report-export";

export default function ReportPage() {
  const params = useParams();
  const jobId = params.jobId as string;

  const [report, setReport] = useState<Report | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [reportSavedAt, setReportSavedAt] = useState<string | null>(null);
  const [reportExpiresAt, setReportExpiresAt] = useState<string | null>(null);

  // Filter state for each tab
  const [filteredArchive, setFilteredArchive] = useState<
    TableRecommendation[]
  >([]);
  const [filteredLowUsage, setFilteredLowUsage] = useState<
    TableRecommendation[]
  >([]);
  const [filteredActive, setFilteredActive] = useState<TableRecommendation[]>(
    []
  );

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setIsLoading(true);
        const data = await api.getReport(jobId);
        setReport(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch report"
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchReport();
  }, [jobId]);

  // Download handlers
  const handleDownloadJSON = async () => {
    if (!report) return;
    try {
      setIsDownloading(true);
      const blob = await api.exportReportAsJSON(jobId);
      downloadFile(
        blob,
        `report-${report.workspace_name}-${jobId}.json`,
        "application/json"
      );
      setSaveStatus({
        success: true,
        message: "✅ Report downloaded as JSON",
      });
    } catch (err) {
      setSaveStatus({
        success: false,
        message: `❌ Failed to download: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    } finally {
      setIsDownloading(false);
      setTimeout(() => setSaveStatus(null), 4000);
    }
  };

  const handleDownloadCSV = async () => {
    if (!report) return;
    try {
      setIsDownloading(true);
      const blob = await api.exportReportAsCSV(jobId);
      downloadFile(
        blob,
        `report-${report.workspace_name}-${jobId}.csv`,
        "text/csv"
      );
      setSaveStatus({
        success: true,
        message: "✅ Report downloaded as CSV",
      });
    } catch (err) {
      setSaveStatus({
        success: false,
        message: `❌ Failed to download: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    } finally {
      setIsDownloading(false);
      setTimeout(() => setSaveStatus(null), 4000);
    }
  };

  const handleSaveReport = async () => {
    if (!report) return;
    try {
      setIsSaving(true);
      const result = await api.saveReportToStorage(jobId);

      // Update local state to show saved status
      const now = new Date().toISOString();
      setReportSavedAt(now);
      setReportExpiresAt(result.expires_at);

      // Copy URL to clipboard
      await copyToClipboard(result.blob_url);

      setSaveStatus({
        success: true,
        message: `✅ Report saved! ${formatExpirationDate(result.expires_at)} (URL copied to clipboard)`,
      });

      // Auto-redirect to dashboard after 3 seconds to show updated saved status
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 3000);
    } catch (err) {
      setSaveStatus({
        success: false,
        message: `❌ Failed to save: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveStatus(null), 6000);
    }
  };

  const TableRow = ({ table, isArchive }: { table: TableRecommendation; isArchive?: boolean }) => (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="px-4 py-3 font-medium text-gray-900">{table.table_name}</td>
      <td className="px-4 py-3">
        <Badge variant={getTierColor(table.current_tier)}>
          {table.current_tier}
        </Badge>
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {table.ingestion_gb_per_day.toFixed(4)} GB/day
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {formatCurrency(table.monthly_cost_hot)}
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {table.rule_coverage_count}
      </td>
      <td className="px-4 py-3">
        <Badge variant={getConfidenceColor(table.confidence)}>
          {table.confidence}
        </Badge>
      </td>
      <td className="px-4 py-3 text-right font-semibold text-green-600">
        {formatCurrency(table.annual_savings)}
      </td>
      {isArchive && (
        <td className="px-4 py-3 text-right">
          <Button variant="ghost" size="sm">
            Select
          </Button>
        </td>
      )}
    </tr>
  );

  // Lookback label helper
  const lookbackLabel = (days: number | undefined) => {
    if (!days) return "30 days";
    const map: Record<number, string> = {
      1: "Last 1 day", 7: "Last 7 days", 14: "Last 14 days",
      30: "Last 30 days", 60: "Last 60 days", 90: "Last 90 days",
    };
    return map[days] ?? `Last ${days} days`;
  };

  return (
    <ProtectedRoute>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center min-h-screen">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <div className="text-red-600 text-center py-8">{error}</div>
        ) : report ? (
          <>
            {/* Header */}
            <div className="flex justify-between items-start mb-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  Audit Report
                </h1>
                <div className="flex items-center gap-3 mt-1">
                  <p className="text-gray-600">
                    {report.workspace_name} •{" "}
                    {new Date(report.timestamp).toLocaleDateString()}
                  </p>
                  {/* Time range badge */}
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                    🕐 {lookbackLabel(report.days_lookback)}
                  </span>
                  {/* Saved to blob storage badge */}
                  {reportSavedAt && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                      💾 Saved to Blob
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleDownloadJSON}
                  disabled={isDownloading || isSaving}
                >
                  📥 JSON
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleDownloadCSV}
                  disabled={isDownloading || isSaving}
                >
                  📊 CSV
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSaveReport}
                  disabled={isDownloading || isSaving}
                >
                  💾 Save Report
                </Button>
                <Link href={`/audit/${jobId}/approve`}>
                  <Button size="sm" className="bg-green-600 hover:bg-green-700">
                    ✅ Approve & Migrate
                  </Button>
                </Link>
              </div>

              {/* Status Message */}
              {saveStatus && (
                <div
                  className={`mt-2 p-2 rounded text-sm ${
                    saveStatus.success
                      ? "bg-green-50 text-green-800 border border-green-200"
                      : "bg-red-50 text-red-800 border border-red-200"
                  }`}
                >
                  {saveStatus.message}
                </div>
              )}
            </div>

            {/* Executive Summary */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <p className="text-sm text-gray-600 font-medium">Tables Analyzed</p>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                      {report.summary.total_tables_analyzed}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <p className="text-sm text-gray-600 font-medium">Archive Candidates</p>
                    <p className="text-3xl font-bold text-red-600 mt-2">
                      {report.archive_candidates.length}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <p className="text-sm text-gray-600 font-medium">Monthly Savings</p>
                    <p className="text-3xl font-bold text-green-600 mt-2">
                      {formatCurrency(report.summary.total_monthly_savings)}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <p className="text-sm text-gray-600 font-medium">Annual Savings</p>
                    <p className="text-3xl font-bold text-blue-600 mt-2">
                      {formatCurrency(report.summary.total_annual_savings)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Total Cost Banner */}
            <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg flex flex-wrap gap-6 text-sm">
              <div>
                <span className="text-gray-500">Total ingestion/month: </span>
                <span className="font-semibold text-gray-900">
                  {report.summary.total_ingestion_gb_per_month?.toFixed(1) ?? "—"} GB
                </span>
              </div>
              <div>
                <span className="text-gray-500">Current monthly cost: </span>
                <span className="font-semibold text-gray-900">
                  {formatCurrency(report.summary.total_monthly_cost_hot)}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Cost after archiving: </span>
                <span className="font-semibold text-green-700">
                  {formatCurrency(report.summary.total_monthly_cost_archive)}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Data window: </span>
                <span className="font-semibold text-blue-700">
                  {lookbackLabel(report.days_lookback)}
                </span>
              </div>
            </div>

            {/* Detailed Analysis */}
            <Card className="mb-8">
              <CardHeader>
                <CardTitle>Detailed Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="archive" className="w-full">
                  <TabsList>
                    <TabsTrigger value="archive">
                      Archive Candidates ({report.archive_candidates.length})
                    </TabsTrigger>
                    <TabsTrigger value="low-usage">
                      Low Usage ({report.low_usage_candidates.length})
                    </TabsTrigger>
                    <TabsTrigger value="active">
                      Active ({report.active_tables.length})
                    </TabsTrigger>
                    <TabsTrigger value="cost-breakdown">
                      Cost Summary ({report.summary.total_tables_analyzed})
                    </TabsTrigger>
                    <TabsTrigger value="warnings">
                      Warnings ({report.warnings.length})
                    </TabsTrigger>
                  </TabsList>

                  {/* Archive Candidates */}
                  <TabsContent value="archive">
                    <div className="mt-6">
                      {report.archive_candidates.length === 0 ? (
                        <p className="text-gray-600 text-center py-8">
                          No archive candidates found
                        </p>
                      ) : (
                        <>
                          <TableFilters
                            tables={report.archive_candidates}
                            onFilter={setFilteredArchive}
                          />
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead>
                                <tr className="border-b border-gray-200">
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Table Name
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
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Confidence
                                  </th>
                                  <th className="text-right px-4 py-3 font-semibold text-gray-900">
                                    Annual Savings
                                  </th>
                                  <th className="px-4 py-3"></th>
                                </tr>
                              </thead>
                              <tbody>
                                {filteredArchive.length === 0 ? (
                                  <tr>
                                    <td
                                      colSpan={8}
                                      className="px-4 py-8 text-center text-gray-600"
                                    >
                                      No tables match the selected filters
                                    </td>
                                  </tr>
                                ) : (
                                  filteredArchive.map((table) => (
                                    <TableRow
                                      key={table.table_name}
                                      table={table}
                                      isArchive
                                    />
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  </TabsContent>

                  {/* Low Usage */}
                  <TabsContent value="low-usage">
                    <div className="mt-6">
                      {report.low_usage_candidates.length === 0 ? (
                        <p className="text-gray-600 text-center py-8">
                          No low usage tables found
                        </p>
                      ) : (
                        <>
                          <TableFilters
                            tables={report.low_usage_candidates}
                            onFilter={setFilteredLowUsage}
                          />
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead>
                                <tr className="border-b border-gray-200">
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Table Name
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
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Confidence
                                  </th>
                                  <th className="text-right px-4 py-3 font-semibold text-gray-900">
                                    Annual Savings
                                  </th>
                                </tr>
                              </thead>
                              <tbody>
                                {filteredLowUsage.length === 0 ? (
                                  <tr>
                                    <td
                                      colSpan={7}
                                      className="px-4 py-8 text-center text-gray-600"
                                    >
                                      No tables match the selected filters
                                    </td>
                                  </tr>
                                ) : (
                                  filteredLowUsage.map((table) => (
                                    <TableRow
                                      key={table.table_name}
                                      table={table}
                                    />
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  </TabsContent>

                  {/* Active Tables */}
                  <TabsContent value="active">
                    <div className="mt-6">
                      {report.active_tables.length === 0 ? (
                        <p className="text-gray-600 text-center py-8">No active tables</p>
                      ) : (
                        <>
                          <TableFilters
                            tables={report.active_tables}
                            onFilter={setFilteredActive}
                          />
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead>
                                <tr className="border-b border-gray-200">
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Table Name
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
                                  <th className="text-left px-4 py-3 font-semibold text-gray-900">
                                    Status
                                  </th>
                                </tr>
                              </thead>
                              <tbody>
                                {filteredActive.length === 0 ? (
                                  <tr>
                                    <td
                                      colSpan={6}
                                      className="px-4 py-8 text-center text-gray-600"
                                    >
                                      No tables match the selected filters
                                    </td>
                                  </tr>
                                ) : (
                                  filteredActive.map((table) => (
                                    <tr
                                      key={table.table_name}
                                      className="border-b border-gray-100 hover:bg-gray-50"
                                    >
                                      <td className="px-4 py-3 font-medium text-gray-900">
                                        {table.table_name}
                                      </td>
                                      <td className="px-4 py-3">
                                        <Badge variant={getTierColor(table.current_tier)}>
                                          {table.current_tier}
                                        </Badge>
                                      </td>
                                      <td className="px-4 py-3 text-right text-gray-600">
                                        {table.ingestion_gb_per_day.toFixed(4)} GB/day
                                      </td>
                                      <td className="px-4 py-3 text-right text-gray-600">
                                        {formatCurrency(table.monthly_cost_hot)}
                                      </td>
                                      <td className="px-4 py-3 text-right text-gray-600">
                                        {table.rule_coverage_count}
                                      </td>
                                      <td className="px-4 py-3">
                                        <Badge variant="success">Keep</Badge>
                                      </td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  </TabsContent>

                  {/* Cost Summary */}
                  <TabsContent value="cost-breakdown">
                    <div className="mt-6">
                      <CostSummaryTable
                        tables={[
                          ...report.archive_candidates,
                          ...report.low_usage_candidates,
                          ...report.active_tables,
                        ]}
                      />
                    </div>
                  </TabsContent>

                  {/* Warnings */}
                  <TabsContent value="warnings">
                    <div className="mt-6">
                      {report.warnings.length === 0 ? (
                        <p className="text-gray-600 text-center py-8">No warnings</p>
                      ) : (
                        <div className="space-y-4">
                          {report.warnings.map((warning, idx) => (
                            <div key={idx} className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                              <div className="flex gap-3">
                                <span className="text-xl">⚠️</span>
                                <div className="flex-1">
                                  <p className="font-semibold text-yellow-900">
                                    {warning.warning_type} - {warning.table_name}
                                  </p>
                                  <p className="text-yellow-800 text-sm mt-1">{warning.description}</p>
                                  <p className="text-yellow-700 text-sm mt-2 font-medium">
                                    Recommendation: {warning.recommendation}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Waste Analysis */}
            {report.waste_analysis && (
              <Card className="mb-8">
                <CardHeader>
                  <CardTitle>Waste Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                      <p className="text-sm text-red-600 font-medium">Wasted Cost/Month</p>
                      <p className="text-2xl font-bold text-red-700 mt-2">
                        {formatCurrency(report.waste_analysis.wasted_monthly_cost ?? report.waste_analysis.wasted_cost_hot_90d / 3)}
                      </p>
                      <p className="text-xs text-red-600 mt-1">
                        {report.waste_analysis.wasted_percentage.toFixed(1)}% of total cost
                      </p>
                    </div>

                    <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                      <p className="text-sm text-purple-600 font-medium">Potential Annual Savings</p>
                      <p className="text-2xl font-bold text-purple-700 mt-2">
                        {formatCurrency(report.waste_analysis.potential_annual_savings ?? report.waste_analysis.wasted_cost_hot_90d * 4)}
                      </p>
                      <p className="text-xs text-purple-600 mt-1">If unused tables archived</p>
                    </div>

                    <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                      <p className="text-sm text-yellow-600 font-medium">Unused Tables</p>
                      <p className="text-2xl font-bold text-yellow-700 mt-2">
                        {report.waste_analysis.tables_without_rules}
                      </p>
                      <p className="text-xs text-yellow-600 mt-1">With data but no rules</p>
                    </div>

                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <p className="text-sm text-blue-600 font-medium">Total Tables Analyzed</p>
                      <p className="text-2xl font-bold text-blue-700 mt-2">
                        {report.waste_analysis.tables_analyzed}
                      </p>
                      <p className="text-xs text-blue-600 mt-1">
                        {report.waste_analysis.tables_with_rules} with rules
                      </p>
                    </div>
                  </div>

                  {/* Top Wasted Tables */}
                  <div className="mt-6">
                    <h3 className="font-semibold text-gray-900 mb-4">Top Wasted Tables</h3>
                    {report.waste_analysis.top_wasted_tables.length === 0 ? (
                      <p className="text-gray-600 text-center py-4">No wasted tables detected</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="border-b border-gray-200">
                              <th className="text-left px-4 py-3 font-semibold text-gray-900">Table Name</th>
                              <th className="text-right px-4 py-3 font-semibold text-gray-900">GB/day</th>
                              <th className="text-right px-4 py-3 font-semibold text-gray-900">Cost/Month</th>
                              <th className="text-right px-4 py-3 font-semibold text-gray-900">Annual Savings</th>
                              <th className="text-center px-4 py-3 font-semibold text-gray-900">Severity</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.waste_analysis.top_wasted_tables.map((table) => (
                              <tr key={table.table_name} className="border-b border-gray-100 hover:bg-gray-50">
                                <td className="px-4 py-3 font-medium text-gray-900">{table.table_name}</td>
                                <td className="px-4 py-3 text-right text-gray-600">
                                  {(table.ingestion_gb_per_day ?? table.ingestion_gb_90d / 90).toFixed(4)}
                                </td>
                                <td className="px-4 py-3 text-right text-red-600 font-semibold">
                                  {formatCurrency(table.monthly_cost_hot ?? table.cost_hot_90d / 3)}
                                </td>
                                <td className="px-4 py-3 text-right text-green-600 font-semibold">
                                  {formatCurrency(table.annual_savings ?? (table.cost_hot_90d / 3) * 12 * 0.994)}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <Badge
                                    variant={
                                      table.waste_potential === "CRITICAL" ? "danger"
                                      : table.waste_potential === "HIGH" ? "warning"
                                      : "default"
                                    }
                                  >
                                    {table.waste_potential}
                                  </Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Rule Coverage Stats */}
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <h3 className="font-semibold text-gray-900 mb-4">Rule Coverage Statistics</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="text-gray-600">Avg Rules per Table</p>
                        <p className="font-semibold text-gray-900 mt-1">
                          {report.waste_analysis.rule_coverage_stats.avg_rules_per_table}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-600">Tables with High Coverage</p>
                        <p className="font-semibold text-gray-900 mt-1">
                          {report.waste_analysis.rule_coverage_stats.tables_with_high_coverage}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-600">Tables with Zero Coverage</p>
                        <p className="font-semibold text-gray-900 mt-1">
                          {report.waste_analysis.rule_coverage_stats.tables_with_zero_coverage}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Metadata */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Audit Metadata</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600">Parse Success Rate</p>
                    <p className="font-semibold text-gray-900 mt-1">
                      {Math.round(report.metadata.kql_parsing_success_rate * 100)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-600">Tables Analyzed</p>
                    <p className="font-semibold text-gray-900 mt-1">{report.metadata.tables_analyzed}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Rules Analyzed</p>
                    <p className="font-semibold text-gray-900 mt-1">{report.metadata.rules_analyzed}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Data Window</p>
                    <p className="font-semibold text-gray-900 mt-1">{lookbackLabel(report.days_lookback)}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Execution Time</p>
                    <p className="font-semibold text-gray-900 mt-1">
                      {report.metadata.agent_completion_time_seconds.toFixed(1)}s
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>
    </ProtectedRoute>
  );
}