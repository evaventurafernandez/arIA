[CmdletBinding()]
param(
    [string]$RepoRoot = "",

    [ValidatePattern("^[^\\/]+$")]
    [string]$TaskFolder = "TFG",

    [ValidatePattern("^\d{2}:\d{2}$")]
    [string]$StartTime = "01:00",

    [ValidateRange(1, 120)]
    [int]$StepSpacingMinutes = 15,

    [ValidateRange(1, 24)]
    [int]$ExecutionTimeLimitHours = 6
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not $RepoRoot) {
    $RepoRoot = Join-Path $PSScriptRoot "..\.."
}

$ResolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$RunnerPath = Join-Path $ResolvedRepoRoot "infra\ingest\run_aemet_daily_step.ps1"
if (-not (Test-Path -LiteralPath $RunnerPath)) {
    throw "No existe el runner de tareas: $RunnerPath"
}

function Ensure-TaskSchedulerFolder {
    param([string]$FolderName)

    $Service = New-Object -ComObject "Schedule.Service"
    $Service.Connect()
    $RootFolder = $Service.GetFolder("\")
    try {
        [void]$RootFolder.GetFolder($FolderName)
    }
    catch {
        [void]$RootFolder.CreateFolder($FolderName)
    }
}

function Quote-TaskArgument {
    param([string]$Value)

    return '"' + ($Value -replace '"', '\"') + '"'
}

$BaseTime = [datetime]::ParseExact(
    $StartTime,
    "HH:mm",
    [System.Globalization.CultureInfo]::InvariantCulture
)
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$TaskPath = "\$TaskFolder\"
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited

$Definitions = @(
    [pscustomobject]@{
        Name = "AEMET calor 01 descarga CAP"
        Step = "download"
        Offset = 0
        Description = "Descarga diaria del archivo CAP de AEMET para temperaturas máximas. Procesa ayer en Europe/Madrid."
    },
    [pscustomobject]@{
        Name = "AEMET calor 02 importacion source"
        Step = "import-source"
        Offset = 1
        Description = "Importa a source los CAP descargados de AEMET filtrados a AT;Temperaturas máximas."
    },
    [pscustomobject]@{
        Name = "AEMET calor 03 refresh core"
        Step = "refresh-core"
        Offset = 2
        Description = "Actualiza incrementalmente core.aemet_max_temperature_warning desde source."
    },
    [pscustomobject]@{
        Name = "AEMET calor 04 refresh pub"
        Step = "refresh-pub"
        Offset = 3
        Description = "Actualiza incrementalmente pub.aemet_max_temperature_daily_feature para GeoJSON y MVT."
    },
    [pscustomobject]@{
        Name = "AEMET calor 05 publica estadisticas"
        Step = "publish-stats"
        Offset = 4
        Description = "Publica pub.aemet_max_temperature_daily_stat para el día anterior."
    }
)

Ensure-TaskSchedulerFolder -FolderName $TaskFolder

foreach ($Definition in $Definitions) {
    $TriggerTime = [datetime]::Today.Add($BaseTime.TimeOfDay).AddMinutes($Definition.Offset * $StepSpacingMinutes)
    $Arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Quote-TaskArgument $RunnerPath),
        "-Step", $Definition.Step,
        "-RepoRoot", (Quote-TaskArgument $ResolvedRepoRoot)
    ) -join " "

    $Action = New-ScheduledTaskAction `
        -Execute $PowerShellExe `
        -Argument $Arguments `
        -WorkingDirectory $ResolvedRepoRoot
    $Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
    $Settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours $ExecutionTimeLimitHours)

    $Task = New-ScheduledTask `
        -Action $Action `
        -Trigger $Trigger `
        -Principal $Principal `
        -Settings $Settings `
        -Description $Definition.Description

    Register-ScheduledTask `
        -TaskPath $TaskPath `
        -TaskName $Definition.Name `
        -InputObject $Task `
        -Force | Out-Null

    Write-Host ("Registrada {0}{1} a las {2:HH:mm}" -f $TaskPath, $Definition.Name, $TriggerTime)
}

Write-Host "Carpeta del Programador de tareas: $TaskPath"
