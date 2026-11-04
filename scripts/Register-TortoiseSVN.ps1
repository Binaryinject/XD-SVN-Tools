param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$exePath = Join-Path $PSScriptRoot 'XD-SVN-Tools.exe'
$backupPath = Join-Path $PSScriptRoot 'tortoisesvn-settings-backup.json'
$keys = @('HKCU:\Software\TortoiseSVN\DiffTools', 'HKCU:\Software\TortoiseSVN\MergeTools')
if ($Uninstall) {
    if (-not (Test-Path -LiteralPath $backupPath)) { throw 'Settings backup not found.' }
    $savedSettings = Get-Content -LiteralPath $backupPath -Raw | ConvertFrom-Json
    foreach ($entry in $savedSettings) {
        $currentValue = Get-ItemPropertyValue -LiteralPath $entry.Key -Name '.xd' -ErrorAction SilentlyContinue
        if ($currentValue -and $currentValue.IndexOf(('"' + $exePath + '"'), [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw "The .xd setting has changed since registration. Restore it manually: $($entry.Key)"
        }
    }
    foreach ($entry in $savedSettings) {
        if ($entry.HadValue) {
            New-Item -Path $entry.Key -Force | Out-Null
            New-ItemProperty -LiteralPath $entry.Key -Name '.xd' -Value $entry.Value -PropertyType String -Force | Out-Null
        } else {
            Remove-ItemProperty -LiteralPath $entry.Key -Name '.xd' -ErrorAction SilentlyContinue
        }
    }
    $restoredBackupPath = $backupPath + '.restored-' + (Get-Date -Format 'yyyyMMdd-HHmmssfff')
    Move-Item -LiteralPath $backupPath -Destination $restoredBackupPath
    Write-Host 'Previous .xd settings restored. The backup was retained with a restored timestamp.'
    exit 0
}
if (-not (Test-Path -LiteralPath $exePath)) { throw 'XD-SVN-Tools.exe not found. Extract the entire ZIP first.' }
if (Test-Path -LiteralPath $backupPath) { throw 'Backup already exists. Use -Uninstall before registering again.' }
$savedSettings = foreach ($keyPath in $keys) {
    $properties = Get-ItemProperty -LiteralPath $keyPath -ErrorAction SilentlyContinue
    $property = if ($null -ne $properties) { $properties.PSObject.Properties['.xd'] } else { $null }
    [pscustomobject]@{ Key = $keyPath; HadValue = ($null -ne $property); Value = $(if ($property) { $property.Value } else { $null }) }
}
$savedSettings | ConvertTo-Json | Set-Content -LiteralPath $backupPath -Encoding UTF8
$commands = @(
    ('"{0}" diff --base "%base" --mine "%mine"' -f $exePath),
    ('"{0}" merge --base "%base" --mine "%mine" --theirs "%theirs" --merged "%merged"' -f $exePath)
)
for ($i = 0; $i -lt $keys.Length; $i++) {
    New-Item -Path $keys[$i] -Force | Out-Null
    New-ItemProperty -LiteralPath $keys[$i] -Name '.xd' -Value $commands[$i] -PropertyType String -Force | Out-Null
}
Write-Host 'Registered .xd diff and merge tools for the current user. No admin rights required.'
Write-Host 'To restore: powershell -File .\Register-TortoiseSVN.ps1 -Uninstall'
