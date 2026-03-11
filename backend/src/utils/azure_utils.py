"""
Azure utilities for resource ID parsing and common operations.
"""

from typing import Dict, Tuple


def parse_azure_resource_id(resource_id: str) -> Dict[str, str]:
    """
    Parse Azure resource ID to extract components.

    Expected format:
    /subscriptions/{subscription}/resourceGroups/{resource_group}/
    providers/Microsoft.OperationalInsights/workspaces/{workspace_name}

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Dictionary with extracted components:
        - subscription: Subscription ID
        - resource_group: Resource group name
        - resource_name: Last segment (workspace name)
    """
    parts = resource_id.split("/") if resource_id else []

    return {
        "subscription": parts[2] if len(parts) > 2 else "unknown",
        "resource_group": parts[4] if len(parts) > 4 else "unknown",
        "resource_name": parts[-1] if parts else "unknown"
    }


def extract_workspace_details(workspace_id: str) -> Tuple[str, str]:
    """
    Extract resource group and workspace name from workspace ID.

    Args:
        workspace_id: Azure workspace resource ID

    Returns:
        Tuple of (resource_group, workspace_name)
    """
    parsed = parse_azure_resource_id(workspace_id)
    return parsed["resource_group"], parsed["resource_name"]
