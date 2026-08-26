<#
.SYNOPSIS
    Uruchamia caly system jednym poleceniem. Dla osoby, ktora nie programuje.

.DESCRIPTION
    Po kolei: sprawdza srodowisko, wstaje baza, aktualizuje jej schemat,
    buduje interfejs (jesli trzeba), startuje aplikacje i otwiera przegladarke.
    Zamkniecie tego okna zatrzymuje caly system.
#>
param(
    [switch]$BezPrzegladarki,
    [switch]$PrzebudujInterfejs
)

$ErrorActionPreference = 'Stop'
$KatalogRepo = Split-Path -Parent $PSScriptRoot
$SkryptBazy = Join-Path $PSScriptRoot 'lokalny-postgres.ps1'
$Backend = Join-Path $KatalogRepo 'backend'
$Frontend = Join-Path $KatalogRepo 'frontend'
$Adres = 'http://127.0.0.1:8010'
#: Ustawiane, gdy program juz dzialal i baza nalezy do tamtego uruchomienia.
$ZostawBaze = $false

$Host.UI.RawUI.WindowTitle = 'System Zarzadzania Umowami Najmu'

function Krok($numer, $tekst) { Write-Host "[$numer/5] $tekst" -ForegroundColor Cyan }
function Blad($tekst) { Write-Host "`n  BLAD: $tekst`n" -ForegroundColor Red }

Write-Host ''
Write-Host '  System Zarzadzania Umowami Najmu' -ForegroundColor White
Write-Host '  --------------------------------' -ForegroundColor DarkGray
Write-Host ''

try {
    # ---------------------------------------------------------------- 1. narzedzia
    Krok 1 'Sprawdzam srodowisko...'
    foreach ($program in @('uv', 'npm')) {
        if (-not (Get-Command $program -ErrorAction SilentlyContinue)) {
            Blad "Brakuje programu '$program'. Zajrzyj do README.md, sekcja 'Instalacja od zera'."
            Read-Host 'Nacisnij Enter, zeby zamknac'
            exit 1
        }
    }

    # ---------------------------------------------------------------- 2. baza
    Krok 2 'Uruchamiam baze danych...'
    if (-not (Test-Path (Join-Path $KatalogRepo 'tools\pgsql\bin\pg_ctl.exe'))) {
        Write-Host '      Pierwsze uruchomienie: pobieram baze danych. To potrwa kilka minut.' -ForegroundColor Yellow
        & powershell -ExecutionPolicy Bypass -File $SkryptBazy setup
    }
    else {
        & powershell -ExecutionPolicy Bypass -File $SkryptBazy start
    }
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie uruchomic bazy danych.' }

    # ---------------------------------------------------------------- 3. schemat
    Krok 3 'Aktualizuje strukture bazy...'
    Push-Location $Backend
    try {
        & uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Aktualizacja struktury bazy nie powiodla sie.' }
    }
    finally { Pop-Location }

    # ---------------------------------------------------------------- 4. interfejs
    Krok 4 'Przygotowuje interfejs...'
    $dist = Join-Path $Frontend 'dist\index.html'
    if ($PrzebudujInterfejs -or -not (Test-Path $dist)) {
        Push-Location $Frontend
        try {
            if (-not (Test-Path 'node_modules')) {
                Write-Host '      Instaluje skladniki interfejsu...' -ForegroundColor DarkGray
                & npm install --no-audit --no-fund | Out-Null
            }
            & npm run build | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Budowanie interfejsu nie powiodlo sie.' }
        }
        finally { Pop-Location }
    }
    else {
        Write-Host '      Interfejs juz zbudowany.' -ForegroundColor DarkGray
    }

    # ---------------------------------------------------------------- 5. aplikacja
    Krok 5 'Startuje aplikacje...'

    # Zajety port 8010 prawie zawsze znaczy, ze program juz raz uruchomiono
    # i nadal dziala. Uvicorn wypisalby wtedy blad WinError 10048, ktory nikomu
    # nic nie mowi, i zakonczyl sie od razu, zamykajac to okno.
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port 8010 -InformationLevel Quiet -WarningAction SilentlyContinue) {
        Write-Host ''
        Write-Host '  Program juz dziala.' -ForegroundColor Green
        Write-Host "  Otwieram go pod adresem: $Adres" -ForegroundColor Green
        Write-Host ''
        Write-Host '  Jesli chcesz go uruchomic od nowa, najpierw zamknij tamto okno' -ForegroundColor DarkGray
        Write-Host '  albo kliknij "Zatrzymaj system.cmd".' -ForegroundColor DarkGray
        Write-Host ''
        if (-not $BezPrzegladarki) { Start-Process $Adres }
        Read-Host '  Nacisnij Enter, zeby zamknac to okno'
        # Baza nalezy do tamtego uruchomienia, wiec jej nie zatrzymujemy.
        $ZostawBaze = $true
        exit 0
    }

    Write-Host ''
    Write-Host "  Gotowe. Program dziala pod adresem: $Adres" -ForegroundColor Green
    Write-Host '  Zamkniecie tego okna zatrzymuje program.' -ForegroundColor DarkGray
    Write-Host ''

    if (-not $BezPrzegladarki) {
        Start-Job -ScriptBlock { Start-Sleep -Seconds 3; Start-Process $using:Adres } | Out-Null
    }

    Push-Location $Backend
    try {
        & uv run uvicorn najem.main:app --host 127.0.0.1 --port 8010
        # Uvicorn to program zewnetrzny: jego blad nie rzuca wyjatku, wiec bez
        # tego sprawdzenia okno zamknelo by sie w ulamku sekundy, zanim ktokolwiek
        # zdazylby przeczytac komunikat. Dla osoby klikajacej ikonke wyglada to
        # tak, jakby klikniecie nie zrobilo nic.
        if ($LASTEXITCODE -ne 0) { throw "Aplikacja zakonczyla sie bledem (kod $LASTEXITCODE)." }
    }
    finally { Pop-Location }
}
catch {
    Blad $_.Exception.Message
    Read-Host 'Nacisnij Enter, zeby zamknac'
    exit 1
}
finally {
    if (-not $ZostawBaze) {
        Write-Host ''
        Write-Host '  Zatrzymuje baze danych...' -ForegroundColor DarkGray
        & powershell -ExecutionPolicy Bypass -File $SkryptBazy stop | Out-Null
        Write-Host '  System zatrzymany.' -ForegroundColor DarkGray
    }
}
