"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useApi } from "@/hooks/useApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { AnalyticsRule } from "@/lib/types";
import { extractSeverityFromKQL, getSeverityColor } from "@/utils/kql-parser";

const PAGE_SIZE = 50;

export default function RulesPage() {
  const params = useParams();
  const workspace_id = params.workspace_id as string;
  const api = useApi();

  // Data states
  const [rules, setRules] = useState<AnalyticsRule[]>([]);
  const [filteredRules, setFilteredRules] = useState<AnalyticsRule[]>([]);

  // Filter states
  const [searchTerm, setSearchTerm] = useState("");
  const [ruleTypeFilter, setRuleTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);

  // Loading/error states
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch rules on mount
  useEffect(() => {
    const fetchRules = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const fetchedRules = await api.getAnalyticsRules(workspace_id);
        setRules(fetchedRules);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to fetch analytics rules";
        setError(errorMessage);
        console.error("[RULES] Error fetching rules:", err);
      } finally {
        setIsLoading(false);
      }
    };

    if (workspace_id) {
      fetchRules();
    }
  }, [workspace_id, api]);

  // Get unique rule types for filter
  const ruleTypes = useMemo(
    () => Array.from(new Set(rules.map((r) => r.rule_type))).sort(),
    [rules]
  );

  // Get severity distribution
  const severityDistribution = useMemo(() => {
    const dist: Record<string, number> = {
      Critical: 0,
      High: 0,
      Medium: 0,
      Low: 0,
      Unknown: 0,
    };

    rules.forEach((rule) => {
      const severity = extractSeverityFromKQL(rule.kql_query);
      dist[severity]++;
    });

    return dist;
  }, [rules]);

  // Apply filters
  useEffect(() => {
    let filtered = rules;

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (rule) =>
          rule.rule_name.toLowerCase().includes(term) ||
          rule.rule_id.toLowerCase().includes(term)
      );
    }

    // Rule type filter
    if (ruleTypeFilter !== "all") {
      filtered = filtered.filter((rule) => rule.rule_type === ruleTypeFilter);
    }

    // Status filter
    if (statusFilter !== "all") {
      const isEnabled = statusFilter === "enabled";
      filtered = filtered.filter((rule) => rule.enabled === isEnabled);
    }

    setFilteredRules(filtered);
    setCurrentPage(1); // Reset to first page when filters change
  }, [rules, searchTerm, ruleTypeFilter, statusFilter]);

  // Pagination
  const totalPages = Math.ceil(filteredRules.length / PAGE_SIZE);
  const paginatedRules = useMemo(() => {
    const startIdx = (currentPage - 1) * PAGE_SIZE;
    const endIdx = startIdx + PAGE_SIZE;
    return filteredRules.slice(startIdx, endIdx);
  }, [filteredRules, currentPage]);

  const startIdx = (currentPage - 1) * PAGE_SIZE + 1;
  const endIdx = Math.min(currentPage * PAGE_SIZE, filteredRules.length);

  return (
    <ProtectedRoute>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Analytics Rules</h1>
          <p className="text-gray-600 mt-1">
            View and analyze all analytics rules in your workspace
          </p>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-red-800 font-semibold">Error loading rules</h3>
                  <p className="text-red-700 mt-1">{error}</p>
                </div>
                <Button
                  onClick={() => window.location.reload()}
                  variant="default"
                  size="sm"
                >
                  Retry
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-blue-600">
                      {rules.length}
                    </div>
                    <p className="text-gray-600 text-sm mt-1">Total Rules</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-red-600">
                      {severityDistribution.Critical}
                    </div>
                    <p className="text-gray-600 text-sm mt-1">Critical</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-orange-600">
                      {severityDistribution.High}
                    </div>
                    <p className="text-gray-600 text-sm mt-1">High</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-yellow-600">
                      {severityDistribution.Medium}
                    </div>
                    <p className="text-gray-600 text-sm mt-1">Medium</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-blue-600">
                      {severityDistribution.Low}
                    </div>
                    <p className="text-gray-600 text-sm mt-1">Low</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Filters */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Filters</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {/* Search */}
                  <input
                    type="text"
                    placeholder="Search by name or ID..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />

                  {/* Rule Type Filter */}
                  <select
                    value={ruleTypeFilter}
                    onChange={(e) => setRuleTypeFilter(e.target.value)}
                    className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="all">All Rule Types</option>
                    {ruleTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>

                  {/* Status Filter */}
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="all">All Status</option>
                    <option value="enabled">Enabled</option>
                    <option value="disabled">Disabled</option>
                  </select>

                  {/* Clear Filters */}
                  <Button
                    onClick={() => {
                      setSearchTerm("");
                      setRuleTypeFilter("all");
                      setStatusFilter("all");
                    }}
                    variant="outline"
                  >
                    Clear Filters
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Results Count */}
            <div className="mb-4 text-sm text-gray-600">
              {filteredRules.length === 0 ? (
                <p>No rules match your filters</p>
              ) : (
                <p>
                  Showing {startIdx}-{endIdx} of {filteredRules.length} rules
                </p>
              )}
            </div>

            {/* Rules Table */}
            {filteredRules.length === 0 ? (
              <Card>
                <CardContent className="pt-12 pb-12">
                  <div className="text-center">
                    <p className="text-gray-500">No rules found matching your criteria</p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <>
                <Card className="mb-6">
                  <CardContent className="pt-6">
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-gray-200">
                            <th className="text-left px-4 py-3 font-semibold text-gray-900">
                              Severity
                            </th>
                            <th className="text-left px-4 py-3 font-semibold text-gray-900">
                              Name
                            </th>
                            <th className="text-left px-4 py-3 font-semibold text-gray-900">
                              Rule Type
                            </th>
                            <th className="text-center px-4 py-3 font-semibold text-gray-900">
                              Status
                            </th>
                            <th className="text-left px-4 py-3 font-semibold text-gray-900">
                              Tables Referenced
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedRules.map((rule) => {
                            const severity = extractSeverityFromKQL(rule.kql_query);
                            const severityColor = getSeverityColor(severity);
                            return (
                              <tr
                                key={rule.rule_id}
                                className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                              >
                                <td className="px-4 py-3">
                                  <span
                                    className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${severityColor}`}
                                  >
                                    {severity}
                                  </span>
                                </td>
                                <td className="px-4 py-3">
                                  <div className="text-gray-900 font-medium">
                                    {rule.rule_name}
                                  </div>
                                  <div className="text-gray-500 text-sm">{rule.rule_id}</div>
                                </td>
                                <td className="px-4 py-3 text-gray-600 text-sm">
                                  {rule.rule_type}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <span
                                    className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                                      rule.enabled
                                        ? "bg-green-100 text-green-800"
                                        : "bg-gray-100 text-gray-800"
                                    }`}
                                  >
                                    {rule.enabled ? "Enabled" : "Disabled"}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-gray-600 text-sm">
                                  {rule.tables_referenced.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                      {rule.tables_referenced.slice(0, 3).map((table) => (
                                        <span
                                          key={table}
                                          className="inline-block bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs"
                                        >
                                          {table}
                                        </span>
                                      ))}
                                      {rule.tables_referenced.length > 3 && (
                                        <span className="inline-block text-gray-500 px-2 py-1 text-xs">
                                          +{rule.tables_referenced.length - 3} more
                                        </span>
                                      )}
                                    </div>
                                  ) : (
                                    <span className="text-gray-400">None</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>

                {/* Pagination */}
                {totalPages > 1 && (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex justify-between items-center">
                        <div className="text-sm text-gray-600">
                          Page {currentPage} of {totalPages}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() =>
                              setCurrentPage((p) => Math.max(1, p - 1))
                            }
                            disabled={currentPage === 1}
                            variant="outline"
                            size="sm"
                          >
                            Previous
                          </Button>

                          {/* Page numbers */}
                          <div className="flex gap-1">
                            {Array.from({ length: totalPages }, (_, i) => i + 1)
                              .filter((page) => {
                                const distance = Math.abs(page - currentPage);
                                return distance <= 1 || page === 1 || page === totalPages;
                              })
                              .map((page, idx, arr) => (
                                <React.Fragment key={page}>
                                  {idx > 0 && arr[idx - 1] !== page - 1 && (
                                    <span className="px-2 py-1">...</span>
                                  )}
                                  <Button
                                    onClick={() => setCurrentPage(page)}
                                    variant={
                                      page === currentPage ? "default" : "outline"
                                    }
                                    size="sm"
                                  >
                                    {page}
                                  </Button>
                                </React.Fragment>
                              ))}
                          </div>

                          <Button
                            onClick={() =>
                              setCurrentPage((p) => Math.min(totalPages, p + 1))
                            }
                            disabled={currentPage === totalPages}
                            variant="outline"
                            size="sm"
                          >
                            Next
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}
