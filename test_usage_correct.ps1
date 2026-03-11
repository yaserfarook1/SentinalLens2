$subscriptionId = "a1ba82d0-9b2b-4d22-827a-88e607cf6ca8"
$resourceGroup = "PCS-Sentinel-RG"
$workspaceName = "PCS-Sentinel-Demo"

$token = az account get-access-token --resource https://management.azure.com/ | ConvertFrom-Json
$headers = @{"Authorization" = "Bearer $($token.accessToken)"; "Content-Type" = "application/json"}

# Construct the full workspace ID
$workspaceId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/microsoft.operationalinsights/workspaces/$workspaceName"

Write-Host "Testing Usage table with full workspace ID..."
Write-Host "Workspace ID: $workspaceId"
Write-Host ""

# Using the correct endpoint format for Log Analytics Query
$query = @{
    "query" = "Usage | take 5"
} | ConvertTo-Json

# Try the correct endpoint
$uri = "https://api.loganalytics.io/v1/workspaces/$workspaceId/query"

Write-Host "Calling: $uri"
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $uri -Method POST -Headers $headers -Body $query
    Write-Host "SUCCESS! Got response"
    Write-Host "Tables: $($response.tables.Count)"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "Trying alternative endpoint format..."

    # Try another format
    $uri2 = "https://api.loganalytics.io/v1$workspaceId/query"
    Write-Host "Trying: $uri2"

    try {
        $response = Invoke-RestMethod -Uri $uri2 -Method POST -Headers $headers -Body $query
        Write-Host "SUCCESS with alternative format!"
    } catch {
        Write-Host "ERROR: $($_.Exception.Message)"
    }
}
