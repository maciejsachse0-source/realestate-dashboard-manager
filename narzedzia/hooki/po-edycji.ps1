<#
.SYNOPSIS
    Hook PostToolUse: formatuje i lintuje plik zaraz po zapisie.

.DESCRIPTION
    Claude Code podaje na wejsciu standardowym JSON z opisem wywolania narzedzia.
    Bierzemy z niego sciezke pliku i uruchamiamy wlasciwe narzedzie.
    Cokolwiek pojdzie nie tak, konczymy zerem: hook nie ma prawa zablokowac pracy.
#>
$ErrorActionPreference = 'Continue'

try {
    $wejscie = [Console]::In.ReadToEnd()
    if (-not $wejscie) { exit 0 }

    $dane = $wejscie | ConvertFrom-Json
    $plik = $dane.tool_input.file_path
    if (-not $plik) { exit 0 }
    if (-not (Test-Path -LiteralPath $plik)) { exit 0 }

    $repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $rozszerzenie = [System.IO.Path]::GetExtension($plik).ToLowerInvariant()

    switch ($rozszerzenie) {
        '.py' {
            if ($plik -notlike "*\backend\*") { exit 0 }
            Push-Location (Join-Path $repo 'backend')
            try {
                & uv run ruff format -q -- "$plik"     2>&1 | Out-Null
                & uv run ruff check --fix -q -- "$plik" 2>&1 | Out-Null
            }
            finally { Pop-Location }
        }
        { $_ -in '.ts', '.tsx' } {
            if ($plik -notlike "*\frontend\*") { exit 0 }
            Push-Location (Join-Path $repo 'frontend')
            try { & npx --no-install oxlint --fix -- "$plik" 2>&1 | Out-Null }
            finally { Pop-Location }
        }
    }
}
catch {
    # Cicho. Nieudane formatowanie nie moze przerwac sesji.
}
exit 0
