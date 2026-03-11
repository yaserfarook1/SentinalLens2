"""
Report Export Service - Format Reports for Download

Converts Report objects to various formats:
- JSON: Complete structured format with all data
- CSV: Tabular format for spreadsheet analysis
- TXT: Human-readable text format
- PDF: Professional formatted reports (optional, requires weasyprint)
"""

import json
import csv
import io
from datetime import datetime
from typing import Optional
import logging

from src.models.schemas import Report, TableRecommendation

logger = logging.getLogger(__name__)


class ReportExporter:
    """Export audit reports in multiple formats."""

    @staticmethod
    def export_to_json(report: Report) -> str:
        """
        Export report to JSON format.

        Args:
            report: Report object

        Returns:
            JSON string with complete report data
        """
        try:
            # Convert report to dict, handling datetime serialization
            report_dict = json.loads(report.model_dump_json())

            # Pretty print with indentation
            json_str = json.dumps(report_dict, indent=2, default=str)

            logger.info(f"[EXPORT] Report exported to JSON: job_id={report.job_id}")
            return json_str

        except Exception as e:
            logger.error(f"[EXPORT] JSON export failed: job_id={report.job_id}, error={e}")
            raise RuntimeError(f"Failed to export report to JSON: {e}") from e

    @staticmethod
    def export_to_csv(report: Report) -> str:
        """
        Export all tables to CSV format with summary metrics.

        Args:
            report: Report object

        Returns:
            CSV string with all tables and summary
        """
        try:
            output = io.StringIO()

            # Write header section with report metadata
            output.write("# SENTINEL LENS AUDIT REPORT\n")
            output.write(f"Workspace,{report.workspace_name}\n")
            output.write(f"Report ID,{report.job_id}\n")
            output.write(f"Generated,{report.timestamp.isoformat()}\n")
            output.write(f"Data Window,{report.days_lookback} days\n")
            output.write("\n")

            # Write summary metrics
            output.write("# EXECUTIVE SUMMARY\n")
            output.write(f"Total Tables Analyzed,{report.summary.total_tables_analyzed}\n")
            output.write(f"Archive Candidates,{len(report.archive_candidates)}\n")
            output.write(f"Low Usage Candidates,{len(report.low_usage_candidates)}\n")
            output.write(f"Active Tables,{len(report.active_tables)}\n")
            output.write(f"Total Monthly Cost (Hot),${report.summary.total_monthly_cost_hot:,.2f}\n")
            output.write(f"Total Monthly Cost (Archive),${ report.summary.total_monthly_cost_archive:,.2f}\n")
            output.write(f"Monthly Savings,${report.summary.total_monthly_savings:,.2f}\n")
            output.write(f"Annual Savings,${report.summary.total_annual_savings:,.2f}\n")
            output.write("\n\n")

            # Combine all tables for CSV export
            all_tables = (
                report.archive_candidates +
                report.low_usage_candidates +
                report.active_tables
            )

            # Sort by monthly cost (descending)
            all_tables.sort(key=lambda t: t.monthly_cost_hot, reverse=True)

            # Write table data
            output.write("# DETAILED TABLE ANALYSIS\n")
            writer = csv.writer(output)

            # Header row
            writer.writerow([
                "Table Name",
                "Category",
                "Current Tier",
                "Ingestion (GB/day)",
                "Ingestion (GB/month)",
                "Monthly Cost (Hot)",
                "Monthly Cost (Archive)",
                "Rule Count",
                "Confidence",
                "Annual Savings",
            ])

            # Data rows
            for table in all_tables:
                writer.writerow([
                    table.table_name,
                    table.log_category or "Other",
                    table.current_tier,
                    f"{table.ingestion_gb_per_day:.4f}",
                    f"{table.ingestion_gb_per_month:.2f}",
                    f"${table.monthly_cost_hot:,.2f}",
                    f"${table.monthly_cost_archive:,.2f}",
                    table.rule_coverage_count,
                    table.confidence,
                    f"${table.annual_savings:,.2f}",
                ])

            # Add totals row
            total_ingestion_month = sum(t.ingestion_gb_per_month for t in all_tables)
            total_cost_hot = sum(t.monthly_cost_hot for t in all_tables)
            total_cost_archive = sum(t.monthly_cost_archive for t in all_tables)
            total_savings = sum(t.annual_savings for t in all_tables)

            writer.writerow([
                "TOTALS",
                "",
                "",
                "",
                f"{total_ingestion_month:.2f}",
                f"${total_cost_hot:,.2f}",
                f"${total_cost_archive:,.2f}",
                "",
                "",
                f"${total_savings:,.2f}",
            ])

            output.write("\n\n")

            # Write warnings section if any
            if report.warnings:
                output.write("# WARNINGS & MANUAL REVIEW ITEMS\n")
                for warning in report.warnings:
                    output.write(f"\n{warning.warning_type}")
                    if warning.table_name:
                        output.write(f" - {warning.table_name}")
                    output.write(f"\n{warning.description}\n")
                    output.write(f"Recommendation: {warning.recommendation}\n")

            csv_str = output.getvalue()
            logger.info(f"[EXPORT] Report exported to CSV: job_id={report.job_id}")
            return csv_str

        except Exception as e:
            logger.error(f"[EXPORT] CSV export failed: job_id={report.job_id}, error={e}")
            raise RuntimeError(f"Failed to export report to CSV: {e}") from e

    @staticmethod
    def export_to_txt(report: Report) -> str:
        """
        Export report to human-readable text format.

        Args:
            report: Report object

        Returns:
            Text string with formatted report
        """
        try:
            lines = []

            # Header
            lines.append("=" * 80)
            lines.append("SENTINEL LENS AUDIT REPORT")
            lines.append("=" * 80)
            lines.append(f"\nWorkspace:    {report.workspace_name}")
            lines.append(f"Report ID:    {report.job_id}")
            lines.append(f"Generated:    {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Data Window:  {report.days_lookback} days")
            lines.append(f"\n")

            # Executive Summary
            lines.append("-" * 80)
            lines.append("EXECUTIVE SUMMARY")
            lines.append("-" * 80)
            lines.append(f"Total Tables Analyzed:        {report.summary.total_tables_analyzed}")
            lines.append(f"Archive Candidates:           {len(report.archive_candidates)}")
            lines.append(f"Low Usage Candidates:         {len(report.low_usage_candidates)}")
            lines.append(f"Active Tables:                {len(report.active_tables)}")
            lines.append(f"\nCost Analysis (Monthly):")
            lines.append(f"  Current (Hot Tier):         ${report.summary.total_monthly_cost_hot:>12,.2f}")
            lines.append(f"  After Archiving:            ${report.summary.total_monthly_cost_archive:>12,.2f}")
            lines.append(f"  Potential Savings:          ${report.summary.total_monthly_savings:>12,.2f}")
            lines.append(f"\nAnnual Potential Savings:     ${report.summary.total_annual_savings:,.2f}")
            lines.append(f"\n")

            # Archive Candidates
            if report.archive_candidates:
                lines.append("-" * 80)
                lines.append(f"ARCHIVE CANDIDATES ({len(report.archive_candidates)} tables)")
                lines.append("-" * 80)
                for table in report.archive_candidates:
                    lines.append(f"\n{table.table_name}")
                    lines.append(f"  Tier:              {table.current_tier}")
                    lines.append(f"  Ingestion:         {table.ingestion_gb_per_day:.4f} GB/day")
                    lines.append(f"  Rules:             {table.rule_coverage_count}")
                    lines.append(f"  Confidence:        {table.confidence}")
                    lines.append(f"  Annual Savings:    ${table.annual_savings:,.2f}")

            # Low Usage Candidates
            if report.low_usage_candidates:
                lines.append(f"\n\n-" * 40)
                lines.append(f"LOW USAGE CANDIDATES ({len(report.low_usage_candidates)} tables)")
                lines.append("-" * 80)
                for table in report.low_usage_candidates:
                    lines.append(f"\n{table.table_name}")
                    lines.append(f"  Tier:              {table.current_tier}")
                    lines.append(f"  Ingestion:         {table.ingestion_gb_per_day:.4f} GB/day")
                    lines.append(f"  Rules:             {table.rule_coverage_count}")
                    lines.append(f"  Confidence:        {table.confidence}")
                    lines.append(f"  Annual Savings:    ${table.annual_savings:,.2f}")

            # Warnings
            if report.warnings:
                lines.append(f"\n\n" + "-" * 80)
                lines.append(f"WARNINGS ({len(report.warnings)} items for manual review)")
                lines.append("-" * 80)
                for warning in report.warnings:
                    lines.append(f"\n{warning.warning_type}")
                    if warning.table_name:
                        lines.append(f"Table: {warning.table_name}")
                    lines.append(f"Description: {warning.description}")
                    lines.append(f"Recommendation: {warning.recommendation}")

            # Metadata
            lines.append(f"\n\n" + "=" * 80)
            lines.append("EXECUTION METADATA")
            lines.append("=" * 80)
            lines.append(f"Parse Success Rate:  {report.metadata.kql_parsing_success_rate * 100:.1f}%")
            lines.append(f"Rules Analyzed:      {report.metadata.rules_analyzed}")
            lines.append(f"Workbooks Analyzed:  {report.metadata.workbooks_analyzed}")
            lines.append(f"Execution Time:      {report.metadata.agent_completion_time_seconds:.1f}s")

            txt_str = "\n".join(lines)
            logger.info(f"[EXPORT] Report exported to TXT: job_id={report.job_id}")
            return txt_str

        except Exception as e:
            logger.error(f"[EXPORT] TXT export failed: job_id={report.job_id}, error={e}")
            raise RuntimeError(f"Failed to export report to TXT: {e}") from e


# Singleton instance
report_exporter = ReportExporter()
