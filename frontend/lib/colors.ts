/**
 * Utility functions for consistent color/badge styling across the application
 */

export type BadgeVariant = "default" | "secondary" | "success" | "warning" | "danger";

/**
 * Get badge variant color for confidence level
 */
export const getConfidenceColor = (confidence: string): BadgeVariant => {
  switch (confidence) {
    case "HIGH":
      return "success";
    case "MEDIUM":
      return "warning";
    case "LOW":
      return "danger";
    default:
      return "default";
  }
};

/**
 * Get badge variant color for storage tier
 */
export const getTierColor = (tier: string): BadgeVariant => {
  switch (tier) {
    case "Hot":
      return "danger";
    case "Basic":
      return "warning";
    case "Archive":
      return "success";
    default:
      return "default";
  }
};

/**
 * Get status badge color for audit status
 */
export const getStatusColor = (status: string): string => {
  switch (status) {
    case "COMPLETED":
      return "bg-green-100 text-green-800";
    case "FAILED":
      return "bg-red-100 text-red-800";
    case "RUNNING":
      return "bg-blue-100 text-blue-800";
    case "QUEUED":
      return "bg-yellow-100 text-yellow-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};
