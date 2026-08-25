<#
.SYNOPSIS
    Tworzy skrot na pulpicie. Uruchom raz, po instalacji.
#>
$ErrorActionPreference = 'Stop'
$KatalogRepo = Split-Path -Parent $PSScriptRoot
$Cel = Join-Path $KatalogRepo 'Uruchom system najmu.cmd'
$Pulpit = [Environment]::GetFolderPath('Desktop')
$Skrot = Join-Path $Pulpit 'System Najmu.lnk'

$powloka = New-Object -ComObject WScript.Shell
$link = $powloka.CreateShortcut($Skrot)
$link.TargetPath = $Cel
$link.WorkingDirectory = $KatalogRepo
$link.Description = 'System Zarzadzania Umowami Najmu'
$link.IconLocation = "$env:SystemRoot\System32\imageres.dll,174"
$link.Save()

Write-Host "Skrot utworzony na pulpicie: $Skrot" -ForegroundColor Green
