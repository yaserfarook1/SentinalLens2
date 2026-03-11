$workspaceName = "PCS-Sentinel-Demo"

$token = az account get-access-token --resource https://api.loganalytics.io/ | ConvertFrom-Json
$headers = @{"Authorization" = "Bearer $($token.accessToken)"; "Content-Type" = "application/json"}

$query = "Usage | where TimeGenerated >= ago(30d) | where DataType != 'Usage' | summarize TotalGB = sum(Quantity) / 1000 by DataType | extend AvgGBPerDay = TotalGB / 30 | sort by TotalGB desc | take 10"

$body = @{"query" = $query} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "https://api.loganalytics.io/v1/workspaces/$workspaceName/query" -Method POST -Headers $headers -Body $body

Write-Host "Row count: $($response.tables[0].rows.Count)"

if ($response.tables[0].rows.Count -gt 0) {
    foreach ($row in $response.tables[0].rows) {
        Write-Host "$($row[0]): $($row[1]) GB, $($row[2]) GB/day"
    }
}
