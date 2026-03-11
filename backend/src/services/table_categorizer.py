"""
Table Categorizer Service

Maps Sentinel table names to log categories based on Microsoft Sentinel conventions.
Used to enrich reports with category information for better cost analysis.
"""


# Comprehensive mapping of table names to categories
TABLE_CATEGORY_MAP = {
    # Azure Active Directory / Identity
    "SigninLogs": "Azure Active Directory",
    "AuditLogs": "Azure Active Directory",
    "AADNonInteractiveUserSignInLogs": "Azure Active Directory",
    "AADManagedIdentitySignInLogs": "Azure Active Directory",
    "AADServicePrincipalSignInLogs": "Azure Active Directory",
    "AADUserRiskEvents": "Azure Active Directory",
    "AADRiskyUsers": "Azure Active Directory",
    "AADProvisioningLogs": "Azure Active Directory",
    "AADIdentityProtectionAllRiskEvents": "Azure Active Directory",
    "IdentityLogonEvents": "Microsoft Defender for Identity",
    "IdentityDirectoryEvents": "Microsoft Defender for Identity",
    "IdentityInfo": "Azure Active Directory",

    # Windows Security Events
    "SecurityEvent": "Windows Security Events",
    "WindowsEvent": "Windows Security Events",
    "CommonSecurityLog": "Syslog/CEF",
    "Syslog": "Syslog/CEF",

    # Microsoft Defender for Endpoint
    "DeviceProcessEvents": "Microsoft Defender for Endpoint",
    "DeviceEvents": "Microsoft Defender for Endpoint",
    "DeviceFileEvents": "Microsoft Defender for Endpoint",
    "DeviceNetworkEvents": "Microsoft Defender for Endpoint",
    "DeviceRegistryEvents": "Microsoft Defender for Endpoint",
    "DeviceNetworkInfo": "Microsoft Defender for Endpoint",
    "DeviceLogonEvents": "Microsoft Defender for Endpoint",
    "DeviceInfo": "Microsoft Defender for Endpoint",
    "DeviceImageLoadEvents": "Microsoft Defender for Endpoint",
    "DeviceFileCertificateInfo": "Microsoft Defender for Endpoint",

    # User Entity Behavior Analytics (UEBA)
    "BehaviorAnalytics": "User Entity Behavior Analytics",
    "UserPeerAnalytics": "User Entity Behavior Analytics",

    # Microsoft Defender for Cloud
    "SecurityAlert": "Microsoft Defender for Cloud",
    "SecurityAlertStatus": "Microsoft Defender for Cloud",
    "SecurityBaselineSummary": "Microsoft Defender for Cloud",
    "SecurityBaseline": "Microsoft Defender for Cloud",
    "SecurityNestedRecommendation": "Microsoft Defender for Cloud",
    "SecurityRecommendation": "Microsoft Defender for Cloud",
    "SecurityRegulatoryCompliance": "Microsoft Defender for Cloud",
    "SecureScoreControls": "Microsoft Defender for Cloud",
    "SecureScores": "Microsoft Defender for Cloud",

    # Microsoft Defender for Cloud Apps
    "CloudAppEvents": "Microsoft Defender for Cloud Apps",

    # Microsoft Defender for Office 365
    "EmailEvents": "Microsoft Defender for Office 365",
    "EmailAttachmentInfo": "Microsoft Defender for Office 365",
    "EmailUrlInfo": "Microsoft Defender for Office 365",
    "EmailPostDeliveryEvents": "Microsoft Defender for Office 365",
    "UrlClickEvents": "Microsoft Defender for Office 365",

    # Microsoft Defender Alert Evidence
    "AlertEvidence": "Microsoft Defender Alert Evidence",
    "AlertInfo": "Sentinel",

    # Azure Diagnostics
    "AzureDiagnostics": "Azure Diagnostics",
    "AzureActivity": "Azure Diagnostics",
    "AzureMetrics": "Azure Metrics",
    "AzurePolicyEvaluationDetails": "Azure Diagnostics",

    # Application Insights
    "AppTraces": "Application Insights",
    "AppExceptions": "Application Insights",
    "AppMetrics": "Application Insights",
    "AppRequests": "Application Insights",
    "AppPerformanceCounters": "Application Insights",
    "ApplicationInsights": "Application Insights",
    "ExceptionEvents": "Application Insights",

    # Update Management
    "Update": "Update Management",
    "UpdateSummary": "Update Management",
    "UpdateRunProgress": "Update Management",
    "WaaSUpdateStatus": "Update Management",

    # Compliance/Audit
    "OfficeActivity": "Compliance/Audit",
    "AuditEvent": "Compliance/Audit",

    # Sentinel
    "Watchlist": "Sentinel",
    "SentinelAudit": "Sentinel",

    # Management
    "LAQueryLogs": "Management",

    # Threat Intelligence
    "ThreatIntelIndicators": "Threat Intelligence",
    "ThreatIntelObjects": "Threat Intelligence",

    # Network
    "NetworkAccessTraffic": "Network",
    "NetworkAccessConnectionEvents": "Network",
    "HTTPProxy": "Network",
    "URLFilter": "Network",
    "DnsEvents": "Network",

    # Compliance/Security
    "ProtectionStatus": "Compliance/Security",
    "SecurityAttackPathData": "Microsoft Defender for Cloud",

    # Intune
    "IntuneDevices": "Intune",
    "IntuneAuditLogs": "Intune",
    "IntuneOperationalLogs": "Intune",
    "IntuneDeviceComplianceOrg": "Intune",

    # Microsoft Graph & Power Platform
    "MicrosoftGraphActivityLogs": "Azure Active Directory",
    "MicrosoftServicePrincipalSignInLogs": "Azure Active Directory",
    "PowerPlatformAdminActivity": "Power Platform",
    "PowerBIActivity": "Power Platform",
    "PowerAutomateActivity": "Power Platform",

    # Data Connectors
    "CiscoASAConnection": "Network",
    "CiscoASADns": "Network",
    "CiscoASAFirewall": "Network",
    "Fortinet_FortiGate_log": "Network",
    "PaloAltoNetworks_PAN_OS": "Network",

    # Storage
    "StorageBlob": "Azure Diagnostics",
    "StorageQueue": "Azure Diagnostics",
    "StorageTable": "Azure Diagnostics",
    "StorageFile": "Azure Diagnostics",

    # Kubernetes
    "ContainerLog": "Kubernetes",
    "ContainerLogV2": "Kubernetes",
    "KubeEvents": "Kubernetes",
    "KubeNodeInventory": "Kubernetes",
    "KubePodInventory": "Kubernetes",
    "HealthStateChangeEvents": "Kubernetes",

    # Infrastructure/Monitoring
    "Heartbeat": "Infrastructure",
    "Perf": "Infrastructure",

    # Workflow/Automation
    "WorkflowRuntime": "Azure Diagnostics",

    # Web Application Firewall
    "WAFLogs": "Network",
    "AppServiceHTTPLogs": "Application Insights",
    "ApiManagementGatewayLogs": "Azure Diagnostics",

    # Information Protection
    "MicrosoftPurviewInformationProtection": "Compliance/Security",
    "PurviewSecurityLogs": "Compliance/Security",

    # Remote Network
    "RemoteNetworkHealthLogs": "Network",

    # SQL Security
    "SqlAtpStatus": "Microsoft Defender for Cloud",
    "SqlVulnerabilityAssessmentScanStatus": "Microsoft Defender for Cloud",

    # Cloud Security
    "Anomalies": "Microsoft Defender for Cloud",

    # Miscellaneous
    "Event": "Infrastructure",
    "W3CIISLog": "Infrastructure",
}


def get_table_category(table_name: str) -> str:
    """
    Get the log category for a Sentinel table.

    Args:
        table_name: Name of the Sentinel table

    Returns:
        Category name (e.g., "Azure Active Directory", "Windows Security Events")
        Returns "Custom Log" for tables ending in _CL
        Returns "Other" for unknown tables
    """
    # Check explicit mapping first
    if table_name in TABLE_CATEGORY_MAP:
        return TABLE_CATEGORY_MAP[table_name]

    # Check for custom logs (user-defined tables)
    if table_name.endswith("_CL"):
        return "Custom Log"

    # Default for unknown tables
    return "Other"


def categorize_tables(tables: list) -> dict:
    """
    Categorize a list of tables and return grouped results.

    Args:
        tables: List of TableIngestionData or TableRecommendation objects with table_name

    Returns:
        Dict mapping category -> list of tables in that category
    """
    from collections import defaultdict
    categorized = defaultdict(list)

    for table in tables:
        category = get_table_category(table.table_name)
        categorized[category].append(table)

    return dict(categorized)
