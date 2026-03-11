# ============================================================
# SENTINEL WORKSPACE AUDIT SCRIPT - COMPLETE
# ============================================================
$subscriptionId = "b8f99f9f-c121-422b-a657-c999df2c5296"
$resourceGroup  = "rg-jayesh"
$workspaceName  = "PCS-Sentinel-Demo"
$workspaceId    = "b03654a4-87da-4464-8743-090ade023e19"

# Fix extension warning that corrupts JSON output
az config set extension.use_dynamic_install=yes_without_prompt 2>$null

# ============================================================
# SECTION 1: ANALYTICAL RULES
# ============================================================
Write-Host "`n===== SECTION 1: ANALYTICAL RULES =====" -ForegroundColor Cyan

$allRules = @()
$url = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.OperationalInsights/workspaces/$workspaceName/providers/Microsoft.SecurityInsights/alertRules?api-version=2023-12-01-preview"
do {
    $response = az rest --method get --url $url | ConvertFrom-Json
    $allRules += $response.value
    $url = $response.nextLink
} while ($url)

$validRules = $allRules | Where-Object {
    $_.properties.enabled -eq $true -and
    $_.properties.severity -ne $null -and
    $_.properties.severity -ne "" -and
    $_.properties.displayName -ne $null -and
    $_.properties.displayName -ne ""
}

$brokenRules = $allRules | Where-Object {
    $_.properties.enabled -eq $true -and
    ($_.properties.severity -eq $null -or $_.properties.severity -eq "")
}

Write-Host "Total Rules    : $($allRules.Count)"
Write-Host "Valid Enabled  : $($validRules.Count)"
Write-Host "Disabled       : $(($allRules | Where-Object { $_.properties.enabled -eq $false }).Count)"
Write-Host "Broken Rules   : $($brokenRules.Count)"

Write-Host "`n-- Rules by Severity --"
$validRules | Group-Object { $_.properties.severity } | Sort-Object Count -Descending | ForEach-Object {
    Write-Host "  $($_.Name) : $($_.Count)"
}

Write-Host "`n-- Rules by Type --"
$validRules | Group-Object { $_.kind } | Sort-Object Count -Descending | ForEach-Object {
    Write-Host "  $($_.Name) : $($_.Count)"
}

if ($brokenRules.Count -gt 0) {
    Write-Host "`n-- Broken Rules --" -ForegroundColor Yellow
    $brokenRules | ForEach-Object {
        Write-Host "  $($_.properties.displayName) | Kind: $($_.kind)"
    }
}

# ============================================================
# SECTION 2: ACTIVE TABLES WITH INGESTION DATA
# ============================================================
Write-Host "`n===== SECTION 2: ACTIVE TABLES =====" -ForegroundColor Cyan

$tableQuery = "Usage | where TimeGenerated > ago(90d) | summarize LastIngestion=max(TimeGenerated), TotalGB=sum(Quantity)/1024 by DataType | order by DataType asc"
$rawJson    = az monitor log-analytics query --workspace $workspaceId --analytics-query $tableQuery --timespan P90D --only-show-errors -o json
$rawResult  = $rawJson | ConvertFrom-Json

$activeTables = $rawResult | ForEach-Object {
    [PSCustomObject]@{
        TableName     = $_.DataType
        LastIngestion = $_.LastIngestion
        TotalGB       = [math]::Round([double]$_.TotalGB, 4)
        EstCost90d    = [math]::Round([double]$_.TotalGB * 2.76, 2)
    }
}

$totalGB   = [math]::Round(($activeTables | Measure-Object TotalGB -Sum).Sum, 2)
$totalCost = [math]::Round(($activeTables | Measure-Object EstCost90d -Sum).Sum, 2)

Write-Host "Tables with actual data : $($activeTables.Count)"
Write-Host "Total Ingestion/90d     : $totalGB GB"
Write-Host "Total Est. Cost/90d     : `$$totalCost USD"

Write-Host "`n-- Top 10 Tables by Cost --"
$activeTables | Sort-Object EstCost90d -Descending | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $($_.TableName) | $($_.TotalGB) GB | `$$($_.EstCost90d)/90d"
}

# ============================================================
# SECTION 3: MONITORED MACHINES
# ============================================================
Write-Host "`n===== SECTION 3: MONITORED MACHINES =====" -ForegroundColor Cyan

$serverQuery  = "Heartbeat | where TimeGenerated > ago(90d) | summarize LastHeartbeat=max(TimeGenerated) by Computer, OSType | order by LastHeartbeat desc"
$serverJson   = az monitor log-analytics query --workspace $workspaceId --analytics-query $serverQuery --timespan P90D --only-show-errors -o json
$serverResult = $serverJson | ConvertFrom-Json

Write-Host "Total Machines : $($serverResult.Count)"

Write-Host "`n-- ACTIVE (heartbeat within 7 days) --" -ForegroundColor Green
$serverResult | Where-Object { [datetime]$_.LastHeartbeat -gt (Get-Date).AddDays(-7) } | ForEach-Object {
    Write-Host "  $($_.Computer) | $($_.OSType) | Last: $($_.LastHeartbeat)"
}

Write-Host "`n-- STALE (no heartbeat 7+ days) --" -ForegroundColor Red
$serverResult | Where-Object { [datetime]$_.LastHeartbeat -le (Get-Date).AddDays(-7) } | ForEach-Object {
    Write-Host "  $($_.Computer) | $($_.OSType) | Last: $($_.LastHeartbeat)"
}

# ============================================================
# SECTION 4: RULE vs TABLE MAPPING
# ============================================================
Write-Host "`n===== SECTION 4: RULE vs TABLE MAPPING =====" -ForegroundColor Cyan

$activeTableNames = $activeTables | Select-Object -ExpandProperty TableName

$ruleTableMapping = $validRules | ForEach-Object {
    $query      = $_.properties.query
    $tablesUsed = @()
    if ($query) {
        foreach ($table in $activeTableNames) {
            if ($query -match "\b$table\b") { $tablesUsed += $table }
        }
    }
    [PSCustomObject]@{
        RuleName   = $_.properties.displayName
        Severity   = $_.properties.severity
        Kind       = $_.kind
        TablesUsed = ($tablesUsed -join ", ")
        TableCount = $tablesUsed.Count
    }
}

Write-Host "Rules WITH table matches  : $(($ruleTableMapping | Where-Object { $_.TableCount -gt 0 }).Count)"
Write-Host "Rules with NO table match : $(($ruleTableMapping | Where-Object { $_.TableCount -eq 0 }).Count)"

Write-Host "`n-- Tables Ranked by Rule Coverage --"
$tableUsageCount = @{}
$ruleTableMapping | Where-Object { $_.TableCount -gt 0 } | ForEach-Object {
    $_.TablesUsed -split ", " | Where-Object { $_ -ne "" } | ForEach-Object {
        if ($tableUsageCount.ContainsKey($_)) { $tableUsageCount[$_]++ }
        else { $tableUsageCount[$_] = 1 }
    }
}
$tableUsageCount.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
    Write-Host "  $($_.Key) — $($_.Value) rules"
}

# ============================================================
# SECTION 5: WASTED TABLES
# ============================================================
Write-Host "`n===== SECTION 5: WASTED TABLES (paying but no rules) =====" -ForegroundColor Yellow

$usedTables = @{}
$ruleTableMapping | Where-Object { $_.TableCount -gt 0 } | ForEach-Object {
    $_.TablesUsed -split ", " | Where-Object { $_ -ne "" } | ForEach-Object {
        $usedTables[$_] = $true
    }
}

$wasteTables = $activeTables | Where-Object { $_.TableName -and -not $usedTables.ContainsKey($_.TableName) }
$wasteTables | Sort-Object EstCost90d -Descending | ForEach-Object {
    Write-Host "  $($_.TableName) | $($_.TotalGB) GB | `$$($_.EstCost90d)/90d"
}

$wasteGB   = [math]::Round(($wasteTables | Measure-Object TotalGB -Sum).Sum, 2)
$wasteCost = [math]::Round(($wasteTables | Measure-Object EstCost90d -Sum).Sum, 2)
Write-Host "`nTotal Wasted : $wasteGB GB | `$$wasteCost USD/90d" -ForegroundColor Red
Write-Host "% of total bill wasted : $([math]::Round($wasteCost/$totalCost*100, 1))%" -ForegroundColor Red

# ============================================================
# SECTION 6: EXPORT ALL CSVs
# ============================================================
Write-Host "`n===== SECTION 6: EXPORTING CSVs =====" -ForegroundColor Cyan

# 01 - Valid Rules
$validRules | ForEach-Object {
    [PSCustomObject]@{
        DisplayName  = $_.properties.displayName
        Severity     = $_.properties.severity
        Kind         = $_.kind
        Tactics      = ($_.properties.tactics -join ", ")
        LastModified = $_.properties.lastModifiedUtc
    }
} | Export-Csv -Path "./01_ValidRules.csv" -NoTypeInformation
Write-Host "Exported: 01_ValidRules.csv"

# 02 - Active Tables with cost
$activeTables | Sort-Object EstCost90d -Descending |
    Export-Csv -Path "./02_ActiveTables.csv" -NoTypeInformation
Write-Host "Exported: 02_ActiveTables.csv"

# 03 - Machines
$serverResult | ForEach-Object {
    [PSCustomObject]@{
        Computer      = $_.Computer
        OSType        = $_.OSType
        LastHeartbeat = $_.LastHeartbeat
        Status        = if ([datetime]$_.LastHeartbeat -gt (Get-Date).AddDays(-7)) { "ACTIVE" } else { "STALE" }
    }
} | Export-Csv -Path "./03_Machines.csv" -NoTypeInformation
Write-Host "Exported: 03_Machines.csv"

# 04 - Rule to Table mapping
$ruleTableMapping | Sort-Object TableCount -Descending |
    Export-Csv -Path "./04_RuleTableMapping.csv" -NoTypeInformation
Write-Host "Exported: 04_RuleTableMapping.csv"

# 05 - Wasted tables
$wasteTables | Sort-Object EstCost90d -Descending |
    Export-Csv -Path "./05_WastedTables.csv" -NoTypeInformation
Write-Host "Exported: 05_WastedTables.csv"

Write-Host "`n===== DONE =====" -ForegroundColor Green
Write-Host "Download with:" -ForegroundColor Green
Write-Host "  download ./01_ValidRules.csv"
Write-Host "  download ./02_ActiveTables.csv"
Write-Host "  download ./03_Machines.csv"
Write-Host "  download ./04_RuleTableMapping.csv"
Write-Host "  download ./05_WastedTables.csv"