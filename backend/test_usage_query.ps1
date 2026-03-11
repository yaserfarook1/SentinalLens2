# Test Usage Table Query
# This script tests the same query used by the backend

$subscriptionId = "b8f99f9f-c121-422b-a657-c999df2c5296"
$resourceGroup  = "rg-jayesh"
$workspaceName  = "PCS-Sentinel-Demo"
$workspaceId    = "b03654a4-87da-4464-8743-090ade023e19"

Write-Host "=================================================="
Write-Host "Testing Usage Table Query"
Write-Host "=================================================="
Write-Host "Workspace: $workspaceName"
Write-Host "Workspace ID: $workspaceId"
Write-Host ""

# Query 1: Check if Usage table exists
Write-Host "TEST 1: Does Usage table exist?"
Write-Host "Query: Usage | take 1"
$test1 = az monitor log-analytics query `
    --workspace $workspaceId `
    --analytics-query "Usage | take 1" `
    --timespan P1D `
    -o json 2>&1

if ($test1 -match "error|Error|ERROR" -or $test1 -eq "") {
    Write-Host "❌ FAILED: Usage table does not exist or query error"
    Write-Host "Error: $test1"
} else {
    Write-Host "✅ SUCCESS: Usage table exists"
}

Write-Host ""

# Query 2: Get sample Usage data (last 7 days)
Write-Host "TEST 2: Get sample Usage data (last 7 days)"
Write-Host "Query: Usage | where TimeGenerated > ago(7d) | take 10"
$test2 = az monitor log-analytics query `
    --workspace $workspaceId `
    --analytics-query "Usage | where TimeGenerated > ago(7d) | take 10" `
    --timespan P7D `
    -o json 2>&1

if ($test2 -match "error|Error|ERROR" -or $test2 -eq "") {
    Write-Host "❌ FAILED: Could not retrieve Usage data"
    Write-Host "Error: $test2"
} else {
    try {
        $result = $test2 | ConvertFrom-Json
        $count = $result.Count
        Write-Host "✅ SUCCESS: Retrieved $count records"
        Write-Host "Sample data:"
        $result | Select-Object -First 3 | ForEach-Object {
            Write-Host "  TimeGenerated: $($_.TimeGenerated), DataType: $($_.DataType), Quantity: $($_.Quantity)"
        }
    } catch {
        Write-Host "❌ FAILED: Could not parse JSON response"
        Write-Host "Response: $test2"
    }
}

Write-Host ""

# Query 3: The actual backend query (90 days, aggregated)
Write-Host "TEST 3: Backend Query (90 days, aggregated)"
Write-Host "Query: Usage (aggregated, 90 days)"
$test3 = az monitor log-analytics query `
    --workspace $workspaceId `
    --analytics-query @"
Usage
| where TimeGenerated > ago(90d)
| where DataType != "Usage"
| summarize TotalGB = sum(Quantity) / 1024 by DataType
| extend AvgGBPerDay = TotalGB / 90
| project TableName=DataType, AvgGBPerDay
| order by AvgGBPerDay desc
| take 20
"@ `
    --timespan P90D `
    -o json 2>&1

if ($test3 -match "error|Error|ERROR" -or $test3 -eq "") {
    Write-Host "❌ FAILED: Could not retrieve aggregated data"
    Write-Host "Error: $test3"
} else {
    try {
        $result = $test3 | ConvertFrom-Json
        $count = $result.Count

        if ($count -eq 0) {
            Write-Host "⚠️  No data returned - Usage table might be empty"
        } else {
            Write-Host "✅ SUCCESS: Retrieved $count tables with ingestion data"
            Write-Host "Top 10 tables:"
            $result | Select-Object -First 10 | ForEach-Object {
                $table = $_.TableName
                $gb = [math]::Round($_.AvgGBPerDay, 4)
                Write-Host "  $table : $gb GB/day"
            }
        }
    } catch {
        Write-Host "❌ FAILED: Could not parse JSON response"
        Write-Host "Response: $test3"
    }
}

Write-Host ""
Write-Host "=================================================="
Write-Host "Testing complete"
Write-Host "=================================================="
