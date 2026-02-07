# Create a desktop shortcut that launches the PMIS starter script (start_stack.ps1)
# Run this once to place a "PMIS Start.lnk" on your Desktop.

$scriptFile = $MyInvocation.MyCommand.Definition
$scriptsDir = Split-Path -Parent $scriptFile
$startScript = Join-Path $scriptsDir 'start_stack.ps1'
if (-not (Test-Path $startScript)){
    Write-Error "start_stack.ps1 not found at $startScript"
    exit 1
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'PMIS Start.lnk'

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""
$shortcut.WorkingDirectory = $scriptsDir
$shortcut.IconLocation = "$startScript,0"
$shortcut.Save()

Write-Host "Created shortcut on Desktop: $shortcutPath" -ForegroundColor Green
Write-Host "Double-click it to open the PMIS starter (opens console windows and browser)." -ForegroundColor Cyan
