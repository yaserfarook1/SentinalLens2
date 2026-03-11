"use client";

import React, { useEffect, useState, useMemo } from "react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useApi } from "@/hooks/useApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { AuditHistoryItem } from "@/lib/types";
import { formatCurrency, formatDate } from "@/lib/formatters";
import { getStatusColor } from "@/lib/colors";
import { getMostRecentCompletedAudit, countByStatus } from "@/lib/audit-utils";
import { copyToClipboard } from "@/utils/report-export";
import Link from "next/link";

export default function DashboardPage() {
  const api = useApi();
  const [audits, setAudits] = useState<AuditHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedJobId, setCopiedJobId] = useState<string | null>(null);

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        setIsLoading(true);
        const data = await api.getAudits(1, 50);
        setAudits(data?.items || []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch audits"
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchAudits();
  }, [api]);

  // Memoize calculations to avoid recomputation
  const stats = useMemo(() => ({
    totalSavings: audits.reduce((sum, audit) => sum + (audit.total_monthly_savings || 0), 0),
    averageTables: audits.length > 0 ? Math.round(audits.reduce((sum, audit) => sum + (audit.tables_analyzed || 0), 0) / audits.length) : 0,
    completedCount: countByStatus(audits, "COMPLETED"),
  }), [audits]);

  // Get most recent completed audit for cost breakdown link
  const mostRecentCompleted = useMemo(() => getMostRecentCompletedAudit(audits), [audits]);

  // Handle copying job ID to clipboard
  const handleCopyJobId = async (jobId: string) => {
    try {
      await copyToClipboard(jobId);
      setCopiedJobId(jobId);
      setTimeout(() => setCopiedJobId(null), 2000);
    } catch {
      console.error("Failed to copy job ID");
    }
  };

  return (
    <ProtectedRoute>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-1">
              Monitor your Sentinel cost optimization audits
            </p>
          </div>
          <Link href="/audit/new">
            <Button size="lg" className="bg-blue-600 hover:bg-blue-700">
              New Audit
            </Button>
          </Link>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <p className="text-sm text-gray-600 font-medium">Total Saved YTD</p>
                <p className="text-3xl font-bold text-green-600 mt-2">
                  {formatCurrency(stats.totalSavings)}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <p className="text-sm text-gray-600 font-medium">Avg Tables/Audit</p>
                <p className="text-3xl font-bold text-blue-600 mt-2">
                  {stats.averageTables}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <p className="text-sm text-gray-600 font-medium">Success Rate</p>
                <p className="text-3xl font-bold text-purple-600 mt-2">
                  {audits.length > 0 ? Math.round((stats.completedCount / audits.length) * 100) : 0}%
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Audits Table */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Audits</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-12">
                <LoadingSpinner />
              </div>
            ) : error ? (
              <div className="text-red-600 py-4 text-center">{error}</div>
            ) : audits.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-600 mb-4">No audits yet</p>
                <Link href="/audit/new">
                  <Button>Start Your First Audit</Button>
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left px-4 py-3 font-semibold text-gray-900">
                        Workspace
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-900">
                        Report ID
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-900">
                        Date
                      </th>
                      <th className="text-right px-4 py-3 font-semibold text-gray-900">
                        Tables
                      </th>
                      <th className="text-right px-4 py-3 font-semibold text-gray-900">
                        Savings
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-900">
                        Status
                      </th>
                      <th className="text-right px-4 py-3 font-semibold text-gray-900">
                        Action
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {audits.map((audit) => (
                      <tr
                        key={audit.job_id}
                        className="border-b border-gray-100 hover:bg-gray-50"
                      >
                        <td className="px-4 py-3 text-gray-900">
                          {audit.workspace_name}
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-sm">
                          <div className="flex items-center gap-2">
                            <code className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                              {audit.job_id.substring(0, 12)}...
                            </code>
                            <button
                              onClick={() => handleCopyJobId(audit.job_id)}
                              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                              title="Copy full job ID"
                            >
                              {copiedJobId === audit.job_id ? "✅" : "📋"}
                            </button>
                            {audit.report_saved_at && (
                              <Badge variant="success" className="text-xs">
                                💾 Saved
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-sm">
                          {formatDate(audit.created_at)}
                        </td>
                        <td className="text-right px-4 py-3 text-gray-900">
                          {audit.tables_analyzed || "-"}
                        </td>
                        <td className="text-right px-4 py-3 font-semibold text-green-600">
                          {audit.total_monthly_savings ? formatCurrency(audit.total_monthly_savings) : "-"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(
                              audit.status
                            )}`}
                          >
                            {audit.status}
                          </span>
                        </td>
                        <td className="text-right px-4 py-3 space-x-2">
                          {audit.status === "COMPLETED" && (
                            <div className="flex justify-end gap-2">
                              <Link href={`/audit/${audit.job_id}/report`}>
                                <Button variant="ghost" size="sm">
                                  View Report
                                </Button>
                              </Link>
                              <Link href={`/rules/${audit.workspace_id}`}>
                                <Button variant="ghost" size="sm">
                                  View Rules
                                </Button>
                              </Link>
                            </div>
                          )}
                          {audit.status === "RUNNING" && (
                            <Link href={`/audit/${audit.job_id}/progress`}>
                              <Button variant="ghost" size="sm">
                                View Progress
                              </Button>
                            </Link>
                          )}
                          {(audit.status === "QUEUED" ||
                            audit.status === "FAILED") && (
                            <span className="text-gray-500 text-sm">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Cost Summary Section */}
        {mostRecentCompleted && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle>Cost Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <p className="text-gray-600 text-sm">
                  View detailed cost breakdown by table for your most recent completed audit ({mostRecentCompleted.workspace_name})
                </p>
                <Link
                  href={`/audit/${mostRecentCompleted.job_id}/report#cost-breakdown`}
                >
                  <Button variant="secondary" className="w-full sm:w-auto">
                    View Cost Summary Report
                  </Button>
                </Link>
                <p className="text-gray-500 text-xs mt-2">
                  View the "Cost Summary" tab in the full audit report to see all tables grouped by cost, category, and tier.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ProtectedRoute>
  );
}
