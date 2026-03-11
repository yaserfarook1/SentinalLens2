/**
 * Report Export Utilities
 * Handle file downloads and export formatting
 */

/**
 * Trigger a browser file download
 */
export function downloadFile(
  content: string | Blob,
  filename: string,
  mimeType: string = "application/octet-stream"
): void {
  try {
    // Convert string to Blob if needed
    const blob = content instanceof Blob
      ? content
      : new Blob([content], { type: mimeType });

    // Create download link
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.style.display = "none";

    // Trigger download
    document.body.appendChild(link);
    link.click();

    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error("Failed to download file:", error);
    throw new Error(`Failed to download file: ${filename}`);
  }
}

/**
 * Download report as JSON
 */
export function downloadJSON(
  data: any,
  filename: string = "report.json"
): void {
  const json = JSON.stringify(data, null, 2);
  downloadFile(json, filename, "application/json");
}

/**
 * Download report as CSV
 */
export function downloadCSV(
  data: string,
  filename: string = "report.csv"
): void {
  downloadFile(data, filename, "text/csv");
}

/**
 * Download report as text
 */
export function downloadText(
  data: string,
  filename: string = "report.txt"
): void {
  downloadFile(data, filename, "text/plain");
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch (error) {
    console.error("Failed to copy to clipboard:", error);
    throw new Error("Failed to copy to clipboard");
  }
}

/**
 * Format expiration date for display
 */
export function formatExpirationDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    const today = new Date();
    const daysUntilExpiry = Math.floor(
      (date.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
    );

    if (daysUntilExpiry < 0) {
      return "Expired";
    } else if (daysUntilExpiry === 0) {
      return "Expires today";
    } else if (daysUntilExpiry === 1) {
      return "Expires tomorrow";
    } else if (daysUntilExpiry <= 7) {
      return `Expires in ${daysUntilExpiry} days`;
    } else {
      return `Expires on ${date.toLocaleDateString()}`;
    }
  } catch {
    return "Expiration unknown";
  }
}
