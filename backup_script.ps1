# Define paths
$sourcePath = "C:\ServicePulse"  # Folder to back up
$backupFolder = "Z:\servepulse_backup"  # Backup destination
$date = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"  # Date format for filename
$backupFile = "$backupFolder\ServicePulse_Backup_$date.zip"

# Ensure backup folder exists
if (!(Test-Path $backupFolder)) {
    New-Item -ItemType Directory -Path $backupFolder | Out-Null
}

# Create backup (compress the folder)
Compress-Archive -Path $sourcePath -DestinationPath $backupFile -Force

# Delete backups older than 30 days
$files = Get-ChildItem -Path $backupFolder -Filter "ServicePulse_Backup_*.zip" | Sort-Object LastWriteTime -Descending
$cutoffDate = (Get-Date).AddDays(-30)

foreach ($file in $files) {
    if ($file.LastWriteTime -lt $cutoffDate) {
        Remove-Item $file.FullName -Force
    }
}

Write-Output "Backup completed: $backupFile"
