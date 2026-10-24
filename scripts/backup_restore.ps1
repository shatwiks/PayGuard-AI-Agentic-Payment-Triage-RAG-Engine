# ==============================================================================
# PayGuard AI — Staging Database Backup and Disaster Recovery Utility (PowerShell)
# Usage:
#   .\scripts\backup_restore.ps1 -Action backup [-FilePath "backup.dump"]
#   .\scripts\backup_restore.ps1 -Action restore -FilePath "backup.dump" [-TargetDb "payguard_staging_db"]
# ==============================================================================

param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("backup", "restore")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [string]$FilePath = "",

    [Parameter(Mandatory=$false)]
    [string]$TargetDb = "payguard_staging_db",

    [Parameter(Mandatory=$false)]
    [string]$ContainerName = "payguard_staging_db",

    [Parameter(Mandatory=$false)]
    [string]$DbUser = "payguard_staging_user"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if ($Action -eq "backup") {
    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        $FilePath = "payguard_backup_$timestamp.dump"
    }
    Write-Host "=== Initiating Staging PostgreSQL Backup ===" -ForegroundColor Cyan
    Write-Host "Container: $ContainerName"
    Write-Host "Database:  $TargetDb"
    Write-Host "Target:    $FilePath"

    docker exec -t $ContainerName pg_dump -Fc -U $DbUser -d $TargetDb > $FilePath
    if ($LASTEXITCODE -eq 0) {
        Write-Host "-> Backup completed successfully: $FilePath" -ForegroundColor Green
    } else {
        Write-Host "-> Backup failed!" -ForegroundColor Red
        exit 1
    }
} elseif ($Action -eq "restore") {
    if ([string]::IsNullOrWhiteSpace($FilePath) -or !(Test-Path $FilePath)) {
        Write-Host "ERROR: Valid backup file path required for restore!" -ForegroundColor Red
        exit 1
    }

    Write-Host "=== Initiating Staging PostgreSQL Restore ===" -ForegroundColor Cyan
    Write-Host "Container: $ContainerName"
    Write-Host "Target DB: $TargetDb"
    Write-Host "Source:    $FilePath"

    docker cp $FilePath "$($ContainerName):/tmp/restore_temp.dump"
    docker exec -t $ContainerName pg_restore -U $DbUser -d $TargetDb --clean --if-exists /tmp/restore_temp.dump
    docker exec -t $ContainerName rm -f /tmp/restore_temp.dump

    Write-Host "-> Restore completed successfully into $TargetDb." -ForegroundColor Green
}
