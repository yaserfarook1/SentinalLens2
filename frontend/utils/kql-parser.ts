/**
 * KQL Parser Utilities
 * Functions to extract metadata from KQL (Kusto Query Language) queries
 */

/**
 * Extract severity level from KQL query text
 * Searches for severity keywords in the query and returns the highest severity found
 *
 * @param kql - The KQL query string to parse
 * @returns One of: "Critical", "High", "Medium", "Low", or "Unknown"
 */
export function extractSeverityFromKQL(
  kql: string
): "Critical" | "High" | "Medium" | "Low" | "Unknown" {
  if (!kql || typeof kql !== "string") {
    return "Unknown";
  }

  const lowerKQL = kql.toLowerCase();

  // Check for severity keywords in order of severity
  // Return the highest severity found
  if (
    lowerKQL.includes("critical") ||
    lowerKQL.includes("severity.*critical") ||
    lowerKQL.includes("severity_level.*critical")
  ) {
    return "Critical";
  }

  if (
    lowerKQL.includes("high") &&
    (lowerKQL.includes("severity") ||
      lowerKQL.includes("priority") ||
      lowerKQL.includes("level"))
  ) {
    return "High";
  }

  if (
    lowerKQL.includes("medium") &&
    (lowerKQL.includes("severity") ||
      lowerKQL.includes("priority") ||
      lowerKQL.includes("level"))
  ) {
    return "Medium";
  }

  if (
    lowerKQL.includes("low") &&
    (lowerKQL.includes("severity") ||
      lowerKQL.includes("priority") ||
      lowerKQL.includes("level"))
  ) {
    return "Low";
  }

  return "Unknown";
}

/**
 * Get severity badge color for UI display
 * @param severity - The severity level
 * @returns Tailwind CSS class for the badge
 */
export function getSeverityColor(
  severity: "Critical" | "High" | "Medium" | "Low" | "Unknown"
): string {
  switch (severity) {
    case "Critical":
      return "bg-red-100 text-red-800";
    case "High":
      return "bg-orange-100 text-orange-800";
    case "Medium":
      return "bg-yellow-100 text-yellow-800";
    case "Low":
      return "bg-blue-100 text-blue-800";
    case "Unknown":
      return "bg-gray-100 text-gray-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}
