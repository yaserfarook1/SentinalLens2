"""
Azure API Service Layer

Wraps all Azure SDK calls for Sentinel, Log Analytics, and Monitor APIs.
All methods use Managed Identity for authentication.
All API calls are logged (metadata only, never data contents).
"""

from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.mgmt.securityinsight import SecurityInsights
from azure.mgmt.loganalytics import LogAnalyticsManagementClient
from azure.monitor.query import LogsQueryClient
from azure.core.exceptions import AzureError
import logging
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio

from src.config import settings
from src.models.schemas import (
    AnalyticsRule, Workbook, HuntQuery, DataConnector, TableIngestionData, TierType
)

logger = logging.getLogger(__name__)


class AzureApiService:
    """Service for all Azure API interactions"""

    def __init__(self):
        """Initialize Azure clients"""
        # Get credential (Managed Identity in prod, DefaultAzureCredential in dev)
        self.credential = settings.credential

        # Initialize clients
        self.sentinel_client = SecurityInsights(
            credential=self.credential,
            subscription_id=settings.AZURE_SUBSCRIPTION_ID
        )
        self.log_analytics_client = LogAnalyticsManagementClient(
            credential=self.credential,
            subscription_id=settings.AZURE_SUBSCRIPTION_ID
        )
        self.logs_query_client = LogsQueryClient(credential=self.credential)

        logger.info("[AUDIT] Azure API service initialized")

    async def list_workspaces(self) -> List[Dict[str, str]]:
        """
        List all Log Analytics workspaces in the subscription.

        Returns:
            List of workspaces with name and ID
        """
        try:
            logger.info(f"[AUDIT] Listing workspaces in subscription: {settings.AZURE_SUBSCRIPTION_ID}")
            logger.debug(f"[AUDIT] Using credential type: {type(self.credential).__name__}")

            workspaces = []

            # Use Resource Management Client to list workspaces
            from azure.mgmt.resource import ResourceManagementClient
            resource_client = ResourceManagementClient(
                credential=self.credential,
                subscription_id=settings.AZURE_SUBSCRIPTION_ID
            )

            logger.debug("[AUDIT] ResourceManagementClient created, listing workspaces...")

            # List all Log Analytics workspaces by resource type
            workspaces_list = resource_client.resources.list(
                filter="resourceType eq 'Microsoft.OperationalInsights/workspaces'"
            )

            # Convert generator to list to trigger the actual API call
            workspaces_list = list(workspaces_list)
            logger.debug(f"[AUDIT] Resource list API returned {len(workspaces_list)} items")

            for resource in workspaces_list:
                resource_group = resource.id.split("/")[4] if "/" in resource.id else "unknown"
                workspace_data = {
                    "workspace_id": resource.id,
                    "workspace_name": resource.name,
                    "subscription_id": settings.AZURE_SUBSCRIPTION_ID,
                    "resource_group": resource_group
                }
                logger.debug(f"[AUDIT] Found workspace: {resource.name} in {resource_group}")
                workspaces.append(workspace_data)

            logger.info(f"[AUDIT] Successfully listed {len(workspaces)} workspaces")
            return workspaces

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list workspaces: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

    async def list_workspace_tables(
        self, resource_group: str, workspace_name: str
    ) -> List[TableIngestionData]:
        """
        Fetch all tables in a workspace with tier and retention info.

        Returns:
            List of tables with metadata
        """
        try:
            logger.info(f"[AUDIT] Fetching tables for workspace: {workspace_name}")

            # Get all tables from Log Analytics via REST API
            import requests

            tables = []

            # Build REST API URL for tables
            api_url = (
                f"https://management.azure.com/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}/"
                f"resourcegroups/{resource_group}/providers/microsoft.operationalinsights/"
                f"workspaces/{workspace_name}/tables?api-version=2021-12-01-preview"
            )

            # Get access token from credential
            token = self.credential.get_token("https://management.azure.com/.default").token

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            logger.debug(f"[AUDIT] Calling REST API: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"[AUDIT] REST API returned {response.status_code}: {response.text}")
                raise Exception(f"Failed to list tables: HTTP {response.status_code}")

            data = response.json()
            table_count = 0

            # Parse tables from response
            for table_data in data.get("value", []):
                try:
                    # Extract table name (works for both dict and object)
                    if isinstance(table_data, dict):
                        table_name = table_data.get("name", "")
                    else:
                        table_name = getattr(table_data, "name", "")

                    # Skip tables with no name
                    if not table_name:
                        continue

                    # Default values for tier and retention (in case properties are missing)
                    tier_str = "Hot"
                    retention = 30

                    # Try to extract tier and retention from properties if available
                    try:
                        if isinstance(table_data, dict):
                            properties = table_data.get("properties", {})
                            if properties:
                                tier_str = properties.get("retentionInDaysType", "Hot")
                                retention = properties.get("totalRetentionInDays", 30)
                        else:
                            # SDK Table object - properties may not exist
                            properties = getattr(table_data, "properties", None)
                            if properties:
                                if isinstance(properties, dict):
                                    tier_str = properties.get("retentionInDaysType", "Hot")
                                    retention = properties.get("totalRetentionInDays", 30)
                                else:
                                    tier_str = getattr(properties, "retention_in_days_type", "Hot")
                                    retention = getattr(properties, "retention_in_days", 30)
                    except Exception:
                        # If properties extraction fails, use defaults (already set above)
                        logger.debug(f"[AUDIT] Could not extract properties for table {table_name}, using defaults")

                    # Determine tier
                    if "Archive" in str(tier_str):
                        tier = TierType.ARCHIVE
                    elif "Basic" in str(tier_str):
                        tier = TierType.BASIC
                    else:
                        tier = TierType.HOT

                    tables.append(
                        TableIngestionData(
                            table_name=table_name,
                            current_tier=tier,
                            retention_days=int(retention) if retention else 30,
                            ingestion_gb_per_day=0.0,  # Will be populated by get_ingestion_volume
                            ingestion_gb_per_month=0.0
                        )
                    )
                    table_count += 1
                    logger.debug(f"[AUDIT] Found table: {table_name} (tier={tier}, retention={retention})")

                except Exception as e:
                    logger.warning(f"[AUDIT] Failed to parse table {getattr(table_data, 'name', 'unknown')}: {str(e)}")
                    continue

            logger.info(f"[AUDIT] Successfully listed {table_count} tables")
            return tables

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list tables: {str(e)}", exc_info=True)
            raise

    async def get_ingestion_volume(
        self,
        resource_group: str,
        workspace_name: str,
        days_lookback: int = 90
    ) -> Dict[str, float]:
        """
        Query Azure Log Analytics Usage table for billable ingestion per table.

        The Usage table is the built-in billing table - single source of truth for costs.
        This matches the Microsoft Sentinel cost workbook approach.

        Returns:
            Dictionary mapping table_name -> gb_per_day average
        """
        try:
            logger.info(
                f"[AUDIT] Fetching ingestion volume from Usage table for {days_lookback} days"
            )

            # Get workspace object to extract customer_id (GUID)
            # LogsQueryClient expects workspace GUID, not ARM resource path
            logger.info(f"[AUDIT] Fetching workspace details for customer_id...")
            workspace = self.log_analytics_client.workspaces.get(
                resource_group_name=resource_group,
                workspace_name=workspace_name
            )
            workspace_id = workspace.customer_id

            logger.info(f"[AUDIT] Workspace customer_id (GUID): {workspace_id}")
            logger.info(f"[AUDIT] Resource Group: {resource_group}")
            logger.info(f"[AUDIT] Workspace Name: {workspace_name}")
            logger.info(f"[AUDIT] Lookback Period: {days_lookback} days")

            # Query Usage table - the official billing data source
            # Usage table columns: DataType (table name), Quantity (MB), IsBillable
            kql_query = f"""
            Usage
            | where TimeGenerated > ago({days_lookback}d)
            | where IsBillable == true
            | summarize TotalMB = sum(Quantity) by DataType
            | extend TotalGB = TotalMB / 1024
            | extend AvgGBPerDay = TotalGB / {days_lookback}
            | where AvgGBPerDay > 0
            | project TableName = DataType, AvgGBPerDay, TotalGB
            """

            logger.info(f"[AUDIT] Executing KQL query against Usage table...")
            logger.debug(f"[AUDIT] KQL Query:\n{kql_query}")

            response = self.logs_query_client.query_workspace(
                workspace_id=workspace_id,
                query=kql_query,
                timespan=timedelta(days=days_lookback)
            )

            # Parse results
            ingestion_data = {}
            if response.tables and len(response.tables) > 0 and response.tables[0].rows:
                rows_count = len(response.tables[0].rows)
                logger.info(f"[AUDIT] ✅ SUCCESS: Query returned {rows_count} tables with billable ingestion")

                # Log first row for debugging
                if response.tables[0].rows:
                    first_row = response.tables[0].rows[0]
                    logger.info(f"[AUDIT] Sample: {first_row[0]} = {first_row[1]:.4f} GB/day ({first_row[2]:.2f} GB total)")

                for row in response.tables[0].rows:
                    table_name = str(row[0]).strip() if row[0] else None
                    avg_gb_per_day = float(row[1]) if row[1] is not None else 0.0

                    if table_name and avg_gb_per_day > 0:
                        ingestion_data[table_name] = avg_gb_per_day
                        logger.info(f"[AUDIT] ✅ {table_name}: {avg_gb_per_day:.4f} GB/day = ${avg_gb_per_day * 30 * 4.3:.2f}/month")
            else:
                logger.warning(f"[AUDIT] ⚠️ EMPTY RESULT: Query executed but returned no rows")
                logger.warning(f"[AUDIT] REASON: Usage table may not exist or contains no billable data in this workspace")
                logger.warning(f"[AUDIT] TO DIAGNOSE: Run this KQL query manually in Azure Portal > Logs:")
                logger.warning(f"[AUDIT]   Usage | take 10")
                logger.warning(f"[AUDIT] If that returns 0 rows, Usage table doesn't exist in your workspace")

            logger.info(f"[AUDIT] ✅ Ingestion data ready: {len(ingestion_data)} tables with data")
            return ingestion_data

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            logger.error(f"[AUDIT] ❌ INGESTION QUERY FAILED")
            logger.error(f"[AUDIT] Error Type: {error_type}")
            logger.error(f"[AUDIT] Error Message: {error_msg}")
            logger.error(f"[AUDIT] Workspace: {workspace_name} (RG: {resource_group})")

            # Provide diagnostic hints based on error type
            if "PathNotFoundError" in error_type or "404" in error_msg:
                logger.error(f"[AUDIT] ")
                logger.error(f"[AUDIT] 🔍 DIAGNOSTIC: This is a 404 error - the endpoint cannot find your workspace")
                logger.error(f"[AUDIT] POSSIBLE CAUSES:")
                logger.error(f"[AUDIT]   1. Usage table doesn't exist in this workspace")
                logger.error(f"[AUDIT]   2. Workspace has no billable data ingestion (new/empty workspace)")
                logger.error(f"[AUDIT]   3. Permissions issue accessing Log Analytics")
                logger.error(f"[AUDIT] ")
                logger.error(f"[AUDIT] ACTION: Check if Usage table exists by running in Azure Portal:")
                logger.error(f"[AUDIT]   Logs > Type 'Usage' > Run")
                logger.error(f"[AUDIT] If that fails, the Usage table doesn't exist - no ingestion cost data available")
            elif "Unauthorized" in error_type or "401" in error_msg:
                logger.error(f"[AUDIT] 🔍 DIAGNOSTIC: Authentication failed")
                logger.error(f"[AUDIT] POSSIBLE CAUSES:")
                logger.error(f"[AUDIT]   1. Service principal doesn't have read permissions on workspace")
                logger.error(f"[AUDIT]   2. Token expired or invalid")
                logger.error(f"[AUDIT] ACTION: Verify service principal has 'Log Analytics Reader' role")
            elif "TimeoutError" in error_type or "timeout" in error_msg.lower():
                logger.error(f"[AUDIT] 🔍 DIAGNOSTIC: Query timed out")
                logger.error(f"[AUDIT] POSSIBLE CAUSES:")
                logger.error(f"[AUDIT]   1. Usage table has too much data (large workspace)")
                logger.error(f"[AUDIT]   2. Network/API latency issue")
                logger.error(f"[AUDIT] ACTION: Try reducing lookback days or check Azure service status")
            else:
                logger.error(f"[AUDIT] 🔍 DIAGNOSTIC: Unknown error - check logs above for details")

            logger.error(f"[AUDIT] RESULT: Audit will continue with $0 ingestion (no cost data)")
            logger.error(f"[AUDIT] Full traceback:", exc_info=True)
            return {}

    async def list_analytics_rules(
        self, resource_group: str, workspace_name: str
    ) -> List[AnalyticsRule]:
        """
        Fetch all analytics rules (Scheduled, NRT) from workspace via REST API.

        Returns:
            List of analytics rules with KQL queries
        """
        try:
            logger.info(f"[AUDIT] Fetching analytics rules")

            rules = []

            # Build REST API URL for analytics rules in Sentinel workspace
            api_url = (
                f"https://management.azure.com/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}/"
                f"resourceGroups/{resource_group}/providers/Microsoft.OperationalInsights/"
                f"workspaces/{workspace_name}/providers/Microsoft.SecurityInsights/"
                f"alertRules?api-version=2023-12-01-preview"
            )

            # Get access token
            token = self.credential.get_token("https://management.azure.com/.default").token

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            logger.debug(f"[AUDIT] Calling REST API: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"[AUDIT] Failed to list analytics rules: HTTP {response.status_code}")
                return []

            data = response.json()
            alert_rules = data.get("value", [])

            rule_count = 0
            enabled_rules = []
            disabled_rules = []

            for rule_data in alert_rules:
                try:
                    # Extract rule info from REST API response (dict format)
                    rule_name = rule_data.get("name", "") if isinstance(rule_data, dict) else getattr(rule_data, "name", "")
                    rule_id = rule_data.get("id", "") if isinstance(rule_data, dict) else getattr(rule_data, "id", "")

                    # Extract rule type and enabled status
                    rule_type = rule_data.get("kind", "Scheduled") if isinstance(rule_data, dict) else "Scheduled"
                    enabled = rule_data.get("properties", {}).get("enabled", False) if isinstance(rule_data, dict) else False

                    # Track enabled/disabled for debugging
                    if enabled:
                        enabled_rules.append(rule_name)
                    else:
                        disabled_rules.append(rule_name)

                    # Only include enabled rules (matches Sentinel UI "Active" filter)
                    if enabled:
                        # Extract KQL query from properties (may be empty for some rule types)
                        kql_query = ""
                        if isinstance(rule_data, dict):
                            properties = rule_data.get("properties", {})
                            kql_query = properties.get("query", "") if isinstance(properties, dict) else ""
                        else:
                            properties = getattr(rule_data, "properties", {})
                            kql_query = properties.get("query", "") if isinstance(properties, dict) else ""

                        # Add rule regardless of whether it has KQL (count all enabled rules)
                        rules.append(
                            AnalyticsRule(
                                rule_id=rule_id,
                                rule_name=rule_name,
                                rule_type=rule_type,
                                kql_query=kql_query,
                                enabled=enabled,
                                tables_referenced=[]  # Will be populated by KQL parser
                            )
                        )
                        rule_count += 1

                except Exception as e:
                    rule_name = rule_data.get("name", "unknown") if isinstance(rule_data, dict) else getattr(rule_data, "name", "unknown")
                    logger.warning(f"[AUDIT] Failed to parse rule {rule_name}: {str(e)}")
                    continue

            logger.info(
                f"[AUDIT] Successfully listed {rule_count} analytics rules "
                f"(Total in API: {len(alert_rules)}, Enabled: {len(enabled_rules)}, Disabled: {len(disabled_rules)})"
            )

            # Log all enabled rules for debugging the count discrepancy
            if enabled_rules:
                logger.info(f"[AUDIT] Enabled rules count: {len(enabled_rules)}")
                # Log in batches to avoid truncation
                for i in range(0, len(enabled_rules), 25):
                    batch = enabled_rules[i:i+25]
                    logger.info(f"[AUDIT] Rules {i+1}-{min(i+25, len(enabled_rules))}: {batch}")

            return rules

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list analytics rules: {str(e)}")
            raise

    async def list_workbooks(
        self, resource_group: str, workspace_name: str
    ) -> List[Workbook]:
        """
        Fetch all workbooks and extract KQL queries.

        Returns:
            List of workbooks with KQL queries
        """
        try:
            logger.info("[AUDIT] Fetching workbooks")

            workbooks = []

            # Get all workbooks from Sentinel
            try:
                # Try workbooks API first
                if hasattr(self.sentinel_client, 'workbooks'):
                    try:
                        workbook_list = self.sentinel_client.workbooks.list(
                            resource_group_name=resource_group
                        )
                    except (AttributeError, TypeError) as e:
                        logger.warning(f"[AUDIT] Failed to access workbooks API: {str(e)}, skipping workbooks")
                        return []
                else:
                    # Fallback: workbooks API not available in this SDK version
                    logger.warning("[AUDIT] Workbooks API not available, skipping workbooks")
                    return []
            except Exception as e:
                logger.warning(f"[AUDIT] Failed to list workbooks: {str(e)}, skipping")
                return []

            workbook_count = 0
            for wb in workbook_list:
                try:
                    # Extract KQL queries from workbook (simplified)
                    kql_queries = self._extract_kql_from_workbook(wb)

                    workbooks.append(
                        Workbook(
                            workbook_id=wb.id,
                            workbook_name=wb.name,
                            kql_queries=kql_queries,
                            tables_referenced=[]  # Will be populated by KQL parser
                        )
                    )
                    workbook_count += 1

                except Exception as e:
                    logger.warning(f"[AUDIT] Failed to parse workbook {wb.name}: {str(e)}")
                    continue

            logger.info(f"[AUDIT] Successfully listed {workbook_count} workbooks")
            return workbooks

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list workbooks: {str(e)}")
            raise

    async def list_hunt_queries(
        self, resource_group: str, workspace_name: str
    ) -> List[HuntQuery]:
        """
        Fetch all hunt/saved queries.

        Returns:
            List of hunt queries with KQL
        """
        try:
            logger.info("[AUDIT] Fetching hunt queries")

            hunt_queries = []

            # Get all saved searches (hunt queries)
            try:
                saved_searches_result = self.log_analytics_client.saved_searches.list_by_workspace(
                    resource_group_name=resource_group,
                    workspace_name=workspace_name
                )
                # SDK returns a result object, extract the value property
                if hasattr(saved_searches_result, 'value'):
                    saved_searches = list(saved_searches_result.value) if saved_searches_result.value else []
                else:
                    logger.warning("[AUDIT] SavedSearchesListResult has no 'value' attribute, skipping hunt queries")
                    return []
            except (TypeError, AttributeError) as e:
                logger.warning(f"[AUDIT] Failed to list hunt queries: {str(e)}, skipping")
                return []

            query_count = 0
            for search in saved_searches:
                try:
                    kql_query = getattr(search, 'query', '')

                    if kql_query:
                        hunt_queries.append(
                            HuntQuery(
                                query_id=search.id,
                                query_name=search.name,
                                kql_query=kql_query,
                                tables_referenced=[]  # Will be populated by KQL parser
                            )
                        )
                        query_count += 1

                except Exception as e:
                    logger.warning(f"[AUDIT] Failed to parse hunt query {search.name}: {str(e)}")
                    continue

            logger.info(f"[AUDIT] Successfully listed {query_count} hunt queries")
            return hunt_queries

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list hunt queries: {str(e)}")
            raise

    async def list_data_connectors(
        self, resource_group: str, workspace_name: str
    ) -> List[DataConnector]:
        """
        List all active data connectors and their table mappings via REST API.

        Returns:
            List of connectors with tables they feed
        """
        try:
            logger.info("[AUDIT] Fetching data connectors")

            connectors = []

            # Build REST API URL for data connectors in Sentinel workspace
            api_url = (
                f"https://management.azure.com/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}/"
                f"resourceGroups/{resource_group}/providers/Microsoft.OperationalInsights/"
                f"workspaces/{workspace_name}/providers/Microsoft.SecurityInsights/"
                f"dataConnectors?api-version=2023-12-01-preview"
            )

            # Get access token
            token = self.credential.get_token("https://management.azure.com/.default").token

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            logger.debug(f"[AUDIT] Calling REST API: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"[AUDIT] Failed to list data connectors: HTTP {response.status_code}")
                return []

            data = response.json()
            connector_list = data.get("value", [])

            connector_count = 0
            for connector_data in connector_list:
                try:
                    # Extract connector info from REST API response (dict format)
                    connector_name = connector_data.get("name", "")
                    connector_id = connector_data.get("id", "")
                    connector_type = connector_data.get("kind", "")

                    # Extract table mappings from properties
                    tables = []
                    properties = connector_data.get("properties", {})
                    if isinstance(properties, dict):
                        # Extract table names from various connector property fields
                        if "dataTypes" in properties and isinstance(properties["dataTypes"], dict):
                            tables = list(properties["dataTypes"].keys())

                    connectors.append(
                        DataConnector(
                            connector_name=connector_name,
                            connector_id=connector_id,
                            connector_type=connector_type,
                            tables_fed=tables
                        )
                    )
                    connector_count += 1

                except Exception as e:
                    connector_name = connector_data.get("name", "unknown") if isinstance(connector_data, dict) else "unknown"
                    logger.warning(f"[AUDIT] Failed to parse connector {connector_name}: {str(e)}")
                    continue

            logger.info(f"[AUDIT] Successfully listed {connector_count} data connectors")
            return connectors

        except Exception as e:
            logger.error(f"[AUDIT] Failed to list data connectors: {str(e)}")
            raise

    # ===== HELPER METHODS =====

    def _get_table_tier(self, table) -> TierType:
        """Extract tier from table object"""
        tier_str = getattr(table.properties, 'retention_in_days_type', 'Hot')
        if 'Archive' in tier_str:
            return TierType.ARCHIVE
        elif 'Basic' in tier_str:
            return TierType.BASIC
        return TierType.HOT

    def _get_table_retention(self, table) -> int:
        """Extract retention days from table object"""
        return getattr(table.properties, 'retention_in_days', 30)

    def _extract_kql_from_workbook(self, workbook) -> List[str]:
        """Extract KQL queries from workbook JSON"""
        # Simplified - in production would parse workbook JSON structure
        return []

    def _get_connector_tables(self, connector) -> List[str]:
        """Extract table names that connector feeds"""
        # Simplified - in production would parse connector configuration
        return []


# ===== SINGLETON INSTANCE =====
azure_api_service = AzureApiService()
