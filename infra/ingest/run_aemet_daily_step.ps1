[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("download", "import-source", "refresh-core", "refresh-pub", "publish-stats", "pipeline")]
    [string]$Step,

    [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,

    [string]$LogRoot = "",

    [switch]$SkipDependencyWait,

    [ValidateRange(1, 360)]
    [int]$DependencyTimeoutMinutes = 120
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ResolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $LogRoot) {
    $LogRoot = Join-Path $ResolvedRepoRoot "data-store\logs\scheduled-tasks\aemet"
}

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot ("{0}_{1}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $Step)
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$StepOrder = @("download", "import-source", "refresh-core", "refresh-pub", "publish-stats")
$script:ActiveStepName = $Step

function Write-TaskLog {
    param([string]$Message)

    $Line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    [System.IO.File]::AppendAllText($LogPath, $Line + [Environment]::NewLine, $Utf8NoBom)
    Write-Host $Line
}

function Get-TargetDateKey {
    return (Get-Date).Date.AddDays(-1).ToString("yyyyMMdd")
}

function Get-StateDir {
    return Join-Path $LogRoot "state"
}

function Get-StepMarkerPath {
    param(
        [string]$TargetDateKey,
        [string]$StepName,
        [string]$Status = "ok"
    )

    return Join-Path (Get-StateDir) ("{0}_{1}.{2}" -f $TargetDateKey, $StepName, $Status)
}

function Clear-StepMarkers {
    param([string]$TargetDateKey)

    New-Item -ItemType Directory -Force -Path (Get-StateDir) | Out-Null
    foreach ($StepName in $StepOrder) {
        foreach ($Status in @("ok", "failed")) {
            $MarkerPath = Get-StepMarkerPath $TargetDateKey $StepName $Status
            if (Test-Path -LiteralPath $MarkerPath) {
                Remove-Item -LiteralPath $MarkerPath -Force
            }
        }
    }
}

function Wait-ForPreviousStep {
    param([string]$StepName)

    if ($SkipDependencyWait) {
        return
    }

    $StepIndex = [array]::IndexOf($StepOrder, $StepName)
    if ($StepIndex -le 0) {
        return
    }

    $TargetDateKey = Get-TargetDateKey
    $PreviousStep = $StepOrder[$StepIndex - 1]
    $OkMarkerPath = Get-StepMarkerPath $TargetDateKey $PreviousStep "ok"
    $FailedMarkerPath = Get-StepMarkerPath $TargetDateKey $PreviousStep "failed"
    $Deadline = (Get-Date).AddMinutes($DependencyTimeoutMinutes)

    Write-TaskLog ("Esperando final OK de '{0}' para {1}" -f $PreviousStep, $TargetDateKey)
    while (-not (Test-Path -LiteralPath $OkMarkerPath)) {
        if (Test-Path -LiteralPath $FailedMarkerPath) {
            throw "El paso previo '$PreviousStep' falló para $TargetDateKey"
        }
        if ((Get-Date) -gt $Deadline) {
            throw "Timeout esperando el paso previo '$PreviousStep' para $TargetDateKey"
        }
        Start-Sleep -Seconds 10
    }
}

function Mark-StepStatus {
    param(
        [string]$StepName,
        [string]$Status
    )

    if ($StepOrder -notcontains $StepName) {
        return
    }

    $TargetDateKey = Get-TargetDateKey
    New-Item -ItemType Directory -Force -Path (Get-StateDir) | Out-Null
    $MarkerPath = Get-StepMarkerPath $TargetDateKey $StepName $Status
    $Content = @(
        "step=$StepName",
        "target_date=$TargetDateKey",
        "status=$Status",
        "completed_at=$(Get-Date -Format o)"
    ) -join [Environment]::NewLine
    [System.IO.File]::WriteAllText($MarkerPath, $Content + [Environment]::NewLine, $Utf8NoBom)
}

function Resolve-PythonExe {
    $Candidates = @(
        (Join-Path $ResolvedRepoRoot "venv\Scripts\python.exe"),
        (Join-Path $ResolvedRepoRoot ".venv\Scripts\python.exe"),
        "python.exe"
    )

    foreach ($Candidate in $Candidates) {
        if ($Candidate -eq "python.exe" -or (Test-Path -LiteralPath $Candidate)) {
            return $Candidate
        }
    }
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-TaskLog ("> {0} {1}" -f $FilePath, ($Arguments -join " "))
    $global:LASTEXITCODE = 0
    & $FilePath @Arguments 2>&1 | ForEach-Object {
        $Text = ($_ | Out-String).TrimEnd()
        if ($Text) {
            Write-TaskLog $Text
        }
    }

    $ExitCode = [int]$global:LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "El comando terminó con código $ExitCode"
    }
}

function Invoke-AemetStep {
    param([string]$StepName)

    switch ($StepName) {
        "download" {
            Invoke-LoggedCommand $PythonExe @(
                "infra/ingest/download_aemet_warnings_historical_sources.py",
                "--elaboration-lookback-days", "3",
                "--block-days", "1",
                "--sleep-seconds", "3",
                "--max-retries", "8"
            )
        }
        "import-source" {
            Invoke-LoggedCommand $PythonExe @(
                "infra/ingest/import_aemet_warnings_source.py",
                "--elaboration-lookback-days", "3"
            )
        }
        "refresh-core" {
            Invoke-LoggedCommand "docker" @(
                "compose", "exec", "-T", "postgres", "psql",
                "-U", "meteovisor",
                "-d", "meteovisor",
                "-f", "/infra/ingest/refresh_aemet_warnings_core.sql"
            )
        }
        "refresh-pub" {
            Invoke-LoggedCommand "docker" @(
                "compose", "exec", "-T", "postgres", "psql",
                "-U", "meteovisor",
                "-d", "meteovisor",
                "-f", "/infra/ingest/refresh_aemet_warnings_pub.sql"
            )
        }
        "publish-stats" {
            Invoke-LoggedCommand $PythonExe @(
                "infra/ingest/publish_aemet_warnings.py"
            )
        }
    }
}

try {
    Set-Location -LiteralPath $ResolvedRepoRoot
    $PythonExe = Resolve-PythonExe

    Write-TaskLog "Inicio paso '$Step' en $ResolvedRepoRoot"

    if ($Step -eq "pipeline") {
        Clear-StepMarkers (Get-TargetDateKey)
        foreach ($PipelineStep in $StepOrder) {
            $script:ActiveStepName = $PipelineStep
            Write-TaskLog "Pipeline ejecuta '$PipelineStep'"
            Invoke-AemetStep $PipelineStep
            Mark-StepStatus $PipelineStep "ok"
        }
    }
    else {
        $script:ActiveStepName = $Step
        if ($Step -eq "download") {
            Clear-StepMarkers (Get-TargetDateKey)
        }
        Wait-ForPreviousStep $Step
        Invoke-AemetStep $Step
        Mark-StepStatus $Step "ok"
    }

    Write-TaskLog "Fin OK paso '$Step'"
    exit 0
}
catch {
    Mark-StepStatus $script:ActiveStepName "failed"
    Write-TaskLog ("ERROR paso '{0}': {1}" -f $Step, $_.Exception.Message)
    exit 1
}
