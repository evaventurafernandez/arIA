[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("download", "import-source", "refresh-core", "refresh-pub", "publish-stats")]
    [string]$Step,

    [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,

    [string]$LogRoot = ""
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

function Write-TaskLog {
    param([string]$Message)

    $Line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    [System.IO.File]::AppendAllText($LogPath, $Line + [Environment]::NewLine, $Utf8NoBom)
    Write-Host $Line
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

try {
    Set-Location -LiteralPath $ResolvedRepoRoot
    $PythonExe = Resolve-PythonExe

    Write-TaskLog "Inicio paso '$Step' en $ResolvedRepoRoot"

    switch ($Step) {
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

    Write-TaskLog "Fin OK paso '$Step'"
    exit 0
}
catch {
    Write-TaskLog ("ERROR paso '{0}': {1}" -f $Step, $_.Exception.Message)
    exit 1
}
