# Test ingestion volume query using REST API
# This diagnoses why get_ingestion_volume is failing

$subscriptionId = "a1ba82d0-9b2b-4d22-827a-88e607cf6ca8"
$resourceGroup = "PCS-Sentinel-RG"
$workspaceName = "PCS-Sentinel-Demo"

Write-Host "Testing Ingestion Volume Query" -ForegroundColor Cyan
Write-Host ""

# Get token
Write-Host "1. Getting management token..." -ForegroundColor Yellow
$token = az account get-access-token --resource https://management.azure.com/ | ConvertFrom-Json
$headers = @{
    "Authorization" = "Bearer $($token.accessToken)"
    "Content-Type" = "application/json"
}

# First, verify the workspace exists
$workspaceUri = "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.OperationalInsights/workspaces/$workspaceName?api-version=2021-06-01"

Write-Host "2. Verifying workspace exists..." -ForegroundColor Yellow
Write-Host "   URI: $workspaceUri" -ForegroundColor Gray

try {
    $wsResponse = Invoke-RestMethod -Uri $workspaceUri -Method GET -Headers $headers
    Write-Host "   SUCCESS: Workspace found" -ForegroundColor Green
    Write-Host "   Workspace ID: $($wsResponse.id)" -ForegroundColor Gray
    Write-Host "   Location: $($wsResponse.location)" -ForegroundColor Gray
} catch {
    Write-Host "   ERROR: Workspace not found or not accessible" -ForegroundColor Red
    Write-Host "   Details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Now test the Usage table query using the query API
Write-Host ""
Write-Host "3. Testing Usage table query via Log Analytics Query API..." -ForegroundColor Yellow

# Get token for the query API
$queryToken = az account get-access-token --resource https://api.loganalytics.io/ | ConvertFrom-Json
$queryHeaders = @{
    "Authorization" = "Bearer $($queryToken.accessToken)"
    "Content-Type" = "application/json"
}

# Try query with full workspace ID
$workspaceId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.OperationalInsights/workspaces/$workspaceName"

$query = @{
    "query" = "Usage | take 10"
} | ConvertTo-Json

$queryUri = "https://api.loganalytics.io/v1$workspaceId/query"
Write-Host "   URI: $queryUri" -ForegroundColor Gray
Write-Host "   Query: Usage | take 10" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri $queryUri -Method POST -Headers $queryHeaders -Body $query -TimeoutSec 30
    Write-Host "   SUCCESS: Usage table query worked!" -ForegroundColor Green
    Write-Host "   Rows returned: $($response.tables[0].rows.Count)" -ForegroundColor Gray
    if ($response.tables[0].rows.Count -gt 0) {
        Write-Host "   Sample: $($response.tables[0].rows[0])" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ERROR: Query failed" -ForegroundColor Red
    Write-Host "   Details: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Response body:" -ForegroundColor Gray
    if ($_.ErrorDetails) {
        Write-Host "   $($_.ErrorDetails.Message)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Test complete" -ForegroundColor Cyan
