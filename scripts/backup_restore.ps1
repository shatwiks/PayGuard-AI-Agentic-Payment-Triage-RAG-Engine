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

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if ($Action -eq "backup") {
    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        $FilePath = "payguard_backup_$timestamp.dump"
    }
    Write-Host "=== Initiating Staging PostgreSQL Backup ===" -ForegroundColor Cyan
    Write-Host "Container: $ContainerName"
    Write-Host "Database:  $TargetDb"
    Write-Host "Target:    $FilePath"

    docker exec $ContainerName pg_dump -Fc -U $DbUser -d $TargetDb -f /tmp/backup_temp.dump
    $dumpExit = $LASTEXITCODE
    if ($dumpExit -ne 0) {
        docker exec $ContainerName rm -f /tmp/backup_temp.dump 2>$null
        Write-Host "-> Backup failed during pg_dump (exit code $dumpExit)!" -ForegroundColor Red
        exit $dumpExit
    }

    docker cp "$($ContainerName):/tmp/backup_temp.dump" $FilePath
    $cpExit = $LASTEXITCODE
    docker exec $ContainerName rm -f /tmp/backup_temp.dump 2>$null

    if ($cpExit -ne 0 -or !(Test-Path $FilePath) -or ((Get-Item $FilePath).Length -eq 0)) {
        Write-Host "-> Backup failed: output archive missing or empty!" -ForegroundColor Red
        exit 1
    }

    Write-Host "-> Backup completed successfully: $FilePath ($((Get-Item $FilePath).Length) bytes)" -ForegroundColor Green
} elseif ($Action -eq "restore") {
    if ([string]::IsNullOrWhiteSpace($FilePath) -or !(Test-Path $FilePath) -or ((Get-Item $FilePath).Length -eq 0)) {
        Write-Host "ERROR: Valid, non-empty backup file path required for restore!" -ForegroundColor Red
        exit 1
    }

    Write-Host "=== Initiating Staging PostgreSQL Restore ===" -ForegroundColor Cyan
    Write-Host "Container: $ContainerName"
    Write-Host "Target DB: $TargetDb"
    Write-Host "Source:    $FilePath"

    docker cp $FilePath "$($ContainerName):/tmp/restore_temp.dump"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to copy backup archive into container!" -ForegroundColor Red
        exit 1
    }

    docker exec $ContainerName pg_restore -U $DbUser -d $TargetDb --clean --if-exists --no-owner --no-privileges /tmp/restore_temp.dump
    $restoreExit = $LASTEXITCODE
    docker exec $ContainerName rm -f /tmp/restore_temp.dump 2>$null

    if ($restoreExit -ne 0) {
        Write-Host "-> Restore failed with exit code $restoreExit!" -ForegroundColor Red
        exit $restoreExit
    }

    Write-Host "-> Restore completed successfully into $TargetDb." -ForegroundColor Green
}
