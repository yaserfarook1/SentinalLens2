/**
 * Utility functions for audit-related operations
 */

import { AuditHistoryItem } from "@/lib/types";

/**
 * Get the most recent completed audit from a list
 * Returns undefined if no completed audits exist
 */
export function getMostRecentCompletedAudit(
  audits: AuditHistoryItem[]
): AuditHistoryItem | undefined {
  return audits
    .filter((a) => a.status === "COMPLETED")
    .sort(
      (a, b) =>
        new Date(b.completed_at || b.created_at).getTime() -
        new Date(a.completed_at || a.created_at).getTime()
    )[0];
}

/**
 * Count audits by status
 */
export function countByStatus(
  audits: AuditHistoryItem[],
  status: string
): number {
  return audits.filter((a) => a.status === status).length;
}
