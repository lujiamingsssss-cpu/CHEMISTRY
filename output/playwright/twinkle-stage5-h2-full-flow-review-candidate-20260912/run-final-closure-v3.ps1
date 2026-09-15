$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$python = (Resolve-Path (Join-Path $repo '..\..\.venv\Scripts\python.exe')).Path
$collector = Join-Path $PSScriptRoot 'collect-formal-closure-v3.js'
$candidateRoot = Join-Path $repo 'output\playwright\twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2'
$sessionDir = Join-Path $candidateRoot 'session'
$sessionName = 'twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2'
$formalUrl = 'http://127.0.0.1:8765/output/twinkle-stage5-h2-full-flow-review/index.html'
$runRecordPath = Join-Path $candidateRoot 'run-record.json'
$rawResultPath = Join-Path $candidateRoot 'raw-browser-result.json'
$transcriptPath = Join-Path $candidateRoot 'playwright-cli-output.txt'
$utf8 = [Text.UTF8Encoding]::new($false)

if (Test-Path -LiteralPath $candidateRoot) {
    throw "Refusing to reuse closure candidate directory: $candidateRoot"
}
New-Item -ItemType Directory -Path $sessionDir | Out-Null

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

$formalPaths = [ordered]@{
    reviewPage = Join-Path $repo 'output\twinkle-stage5-h2-full-flow-review\index.html'
    reviewManifest = Join-Path $repo 'output\twinkle-stage5-h2-full-flow-review\review-manifest.json'
    machineResults = Join-Path $repo 'output\twinkle-stage5-h2-full-flow-review\machine-results.json'
    browserResults = Join-Path $repo 'output\playwright\twinkle-stage5-h2-full-flow-review\browser-results.json'
}
$formalBefore = [ordered]@{}
foreach ($entry in $formalPaths.GetEnumerator()) { $formalBefore[$entry.Key] = Get-Sha256 $entry.Value }

$runRecord = [ordered]@{
    schema = 'twinkle-stage5-h2-closure-run-record-v3'
    runId = 'diagnostic-first-closure-v3-20260914-v2'
    mode = 'single-pass-diagnostic-first-promote-if-green'
    lifecycleStatus = 'starting'
    startedAt = [DateTimeOffset]::Now.ToString('o')
    endedAt = $null
    collector = [ordered]@{
        path = 'output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912/collect-formal-closure-v3.js'
        sha256 = Get-Sha256 $collector
        exitCode = $null
        rawResultCaptured = $false
    }
    formalBefore = $formalBefore
    formalAfter = $null
    artifacts = [ordered]@{
        rawBrowserResult = $null
        transcript = 'playwright-cli-output.txt'
        screenshots = @()
    }
    summary = [ordered]@{ pass = 0; fail = 0; blocked = 0; error = 0 }
    promotion = [ordered]@{ eligible = $false; performed = $false; reason = 'not-evaluated' }
    errors = @()
}

$server = $null
$opened = $false
$runExit = 1
try {
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @('-m', 'http.server', '8765', '--bind', '127.0.0.1') `
        -WorkingDirectory $repo `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $candidateRoot 'http-stdout.log') `
        -RedirectStandardError (Join-Path $candidateRoot 'http-stderr.log') `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
        try {
            $response = Invoke-WebRequest -Uri $formalUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch {
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Formal review server did not become ready.' }

    Push-Location $sessionDir
    try {
        & npx.cmd --yes --package '@playwright/cli' playwright-cli --session $sessionName open about:blank
        if ($LASTEXITCODE -ne 0) { throw "Playwright open failed with exit code $LASTEXITCODE." }
        $opened = $true
        $collectorOutput = @(& npx.cmd --yes --package '@playwright/cli' playwright-cli --session $sessionName run-code --filename $collector 2>&1 | ForEach-Object { "$_" })
        $runExit = $LASTEXITCODE
        [IO.File]::WriteAllText($transcriptPath, ($collectorOutput -join [Environment]::NewLine), $utf8)
        $collectorOutput | Write-Output
        $runRecord.collector.exitCode = $runExit

        $resultLine = $null
        for ($index = 0; $index -lt $collectorOutput.Count - 1; $index += 1) {
            if ($collectorOutput[$index].Trim() -eq '### Result') {
                $resultLine = $collectorOutput[$index + 1].Trim()
                break
            }
        }
        if ($runExit -ne 0) { throw "Collector command failed with exit code $runExit." }
        if (-not $resultLine) { throw 'Collector completed without a JSON result.' }

        $rawResult = $resultLine | ConvertFrom-Json
        [IO.File]::WriteAllText($rawResultPath, ($rawResult | ConvertTo-Json -Depth 100), $utf8)
        $runRecord.collector.rawResultCaptured = $true
        $runRecord.artifacts.rawBrowserResult = 'raw-browser-result.json'
        $runRecord.artifacts.screenshots = @($rawResult.screenshots.PSObject.Properties | ForEach-Object { $_.Value.name })
        foreach ($status in @('pass', 'fail', 'blocked', 'error')) {
            $runRecord.summary[$status] = @($rawResult.outcomes | Where-Object { $_.status -eq $status }).Count
        }
        $runRecord.lifecycleStatus = 'completed'
    } finally {
        Pop-Location
    }
} catch {
    $runRecord.lifecycleStatus = 'error'
    $runRecord.errors = @($runRecord.errors) + @($_.Exception.Message)
} finally {
    if ($opened) {
        Push-Location $sessionDir
        try {
            & npx.cmd --yes --package '@playwright/cli' playwright-cli --session $sessionName close | Out-Null
        } catch {
            $runRecord.errors = @($runRecord.errors) + @("browser close failed: $($_.Exception.Message)")
        } finally {
            Pop-Location
        }
    }
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
        Wait-Process -Id $server.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    $formalAfter = [ordered]@{}
    foreach ($entry in $formalPaths.GetEnumerator()) { $formalAfter[$entry.Key] = Get-Sha256 $entry.Value }
    $runRecord.formalAfter = $formalAfter
    $runRecord.endedAt = [DateTimeOffset]::Now.ToString('o')
    [IO.File]::WriteAllText($runRecordPath, ($runRecord | ConvertTo-Json -Depth 100), $utf8)
}

Write-Output "RUN_RECORD=$runRecordPath"
Write-Output "RAW_RESULT_CAPTURED=$($runRecord.collector.rawResultCaptured)"
if ($runRecord.lifecycleStatus -ne 'completed') { exit 1 }
exit $runExit
