$workspaceName = "PCS-Sentinel-Demo"

Write-Host "Checking Usage table for ingestion data..." -ForegroundColor Cyan
Write-Host ""

$token = az account get-access-token --resource https://api.loganalytics.io/ | ConvertFrom-Json
$accessToken = $token.accessToken

$headers = @{
    "Authorization" = "Bearer $accessToken"
    "Content-Type" = "application/json"
}

$query = "Usage | where TimeGenerated >= ago(30d) | where DataType != 'Usage' | summarize TotalGB = sum(Quantity) / 1000 by DataType | extend AvgGBPerDay = TotalGB / 30 | project TableName=DataType, TotalGB, AvgGBPerDay | sort by TotalGB desc | take 20"

$body = @{ "query" = $query } | ConvertTo-Json

Write-Host "Sending query to Log Analytics..." -ForegroundColor Yellow

$response = Invoke-RestMethod `
    -Uri "https://api.loganalytics.io/v1/workspaces/$workspaceName/query" `
    -Method POST `
    -Headers $headers `
    -Body $body

if ($response.tables -and $response.tables[0].rows.Count -gt 0) {
    Write-Host "SUCCESS: Found ingestion data!" -ForegroundColor Green
    Write-Host ""
    Write-Host "TableName                    Total GB (30d)      Avg GB/day" -ForegroundColor Gray
    Write-Host "===========================================" -ForegroundColor Gray

    foreach ($row in $response.tables[0].rows) {
        $tableName = $row[0]
        $totalGB = [math]::Round($row[1], 2)
        $avgGBPerDay = [math]::Round($row[2], 4)
        Write-Host "$tableName : $totalGB GB : $avgGBPerDay GB/day"
    }
} else {
    Write-Host "ERROR: No ingestion data found" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done" -ForegroundColor Cyan
