<#
.SYNOPSIS
    Sklada paczke wydania do wyslania uzytkownikowi.

.DESCRIPTION
    Dwa rodzaje paczek, bo pierwsza instalacja i aktualizacja to inne problemy:

    AKTUALIZACJA (domyslnie) -- kilka megabajtow, wysylana mailem.
        Zawiera kod i zbudowany interfejs. Rozpakowuje sie na miejsce
        katalogu "program". Binaria bazy i dane leza poza nim, wiec sie
        nie powtarzaja przy kazdym wydaniu.

    PELNA (-Pelna) -- okolo 310 MB, robiona raz, wgrywana osobiscie.
        Dodatkowo binaria PostgreSQL, instalator i pliki .cmd korzenia.

    W obu przypadkach NIE pakujemy frontend/src ani node_modules: na
    komputerze uzytkownika Node.js nie jest potrzebny, bo interfejs jedzie
    gotowy. Nie pakujemy tez testow, dokumentacji, .env ani niczego z dane/.

.PARAMETER Pelna
    Sklada paczke instalacyjna zamiast aktualizacyjnej.

.PARAMETER Mimo
    Pozwala spakowac mimo niezacommitowanych zmian. Wersja dostaje wtedy
    dopisek "brudne-drzewo", zeby po miesiacu dalo sie odroznic, co
    wlasciwie u uzytkownika stoi.
#>
param(
    [switch]$Pelna,
    [switch]$Mimo
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$KatalogProgramu = Katalog-Programu
$KatalogWydan = Join-Path $KatalogProgramu 'wydania'
$Frontend = Join-Path $KatalogProgramu 'frontend'

function Wersja-Projektu {
    $pyproject = Join-Path $KatalogProgramu 'backend\pyproject.toml'
    $trafienie = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' |
        Select-Object -First 1
    if (-not $trafienie) { throw "Nie znalazlem numeru wersji w $pyproject" }
    return $trafienie.Matches[0].Groups[1].Value
}

function Stan-Repozytorium {
    <# Skrot commita i informacja, czy drzewo bylo czyste. #>
    $skrot = (& git -C $KatalogProgramu rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { return @{ Skrot = 'brak-gita'; Czyste = $false } }
    $zmiany = & git -C $KatalogProgramu status --porcelain
    return @{ Skrot = $skrot.Trim(); Czyste = [string]::IsNullOrWhiteSpace(($zmiany -join '')) }
}

function Kopiuj-Do {
    param([string]$Zrodlo, [string]$Cel)
    if (-not (Test-Path -LiteralPath $Zrodlo)) { throw "Brak $Zrodlo" }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Cel) | Out-Null
    Copy-Item -LiteralPath $Zrodlo -Destination $Cel -Recurse -Force
}

# ------------------------------------------------------------------ 1. wersja
$wersja = Wersja-Projektu
$stan = Stan-Repozytorium

if (-not $stan.Czyste) {
    if (-not $Mimo) {
        Pisz ''
        Pisz '  W repozytorium sa niezacommitowane zmiany.' 'Red'
        Pisz '  Paczka wydania musi dac sie odtworzyc z historii, inaczej za pol roku' 'DarkGray'
        Pisz '  nie bedzie wiadomo, co wlasciwie stoi u uzytkownika.' 'DarkGray'
        Pisz ''
        Pisz '  Zacommituj zmiany albo powtorz z przelacznikiem -Mimo.' 'Yellow'
        exit 1
    }
    $wersja = "$wersja-brudne-drzewo"
    Pisz '  Uwaga: pakuje mimo niezacommitowanych zmian.' 'Yellow'
}

$rodzaj = if ($Pelna) { 'instalacja' } else { 'aktualizacja' }
Pisz ''
Pisz "  Skladam paczke: $rodzaj $wersja ($($stan.Skrot))" 'White'
Pisz ''

# -------------------------------------------------------------- 2. interfejs
Pisz '  [1/4] Buduje interfejs...' 'Cyan'
Push-Location $Frontend
try {
    if (-not (Get-Command 'npm' -ErrorAction SilentlyContinue)) {
        throw 'Brak Node.js (npm). Paczki sklada sie na komputerze autora, nie u uzytkownika.'
    }
    if (-not (Test-Path 'node_modules')) {
        & npm install --no-audit --no-fund | Out-Null
    }
    # Log trzymamy w zmiennej i pokazujemy dopiero przy bledzie -- tak samo
    # jak w uruchom.ps1 i z tego samego powodu: bez niego nie wiadomo nic.
    $log = & npm run build
    if ($LASTEXITCODE -ne 0) {
        $log | ForEach-Object { Pisz "        $_" 'DarkGray' }
        throw 'Budowanie interfejsu nie powiodlo sie. Paczki nie sklada sie z zepsutego interfejsu.'
    }
}
finally { Pop-Location }

# ----------------------------------------------------------- 3. kompletowanie
Pisz '  [2/4] Kompletuje pliki...' 'Cyan'

# Katalog roboczy obok celu, nie w TEMP: sciezka TEMP bywa krotka (8.3)
# z tylda w srodku, a Remove-Item probuje wtedy rozwinac ja jak katalog
# domowy i wywala sie na "Users\NAZWA~1 does not exist".
$roboczy = Join-Path $KatalogWydan "_robocze-$PID"
if (Test-Path -LiteralPath $roboczy) { Remove-Item -LiteralPath $roboczy -Recurse -Force }
New-Item -ItemType Directory -Force -Path $roboczy | Out-Null

try {
    # Katalog "program" wyglada tak samo w obu rodzajach paczek. W paczce
    # aktualizacyjnej jest jej cala zawartoscia, w pelnej -- jednym z elementow.
    $celProgramu = if ($Pelna) { Join-Path $roboczy 'program' } else { $roboczy }
    New-Item -ItemType Directory -Force -Path $celProgramu | Out-Null

    foreach ($element in @(
            'backend\src', 'backend\alembic', 'backend\alembic.ini',
            'backend\pyproject.toml', 'backend\uv.lock',
            'frontend\dist',
            'narzedzia'
        )) {
        Kopiuj-Do (Join-Path $KatalogProgramu $element) (Join-Path $celProgramu $element)
    }

    # Skrypty pakowania i hooki gita nie maja czego szukac u uzytkownika.
    Remove-Item -LiteralPath (Join-Path $celProgramu 'narzedzia\spakuj-wydanie.ps1') `
        -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $celProgramu 'narzedzia\hooki') `
        -Recurse -Force -ErrorAction SilentlyContinue

    # __pycache__ potrafi niesc skompilowany kod z poprzedniej wersji.
    Get-ChildItem -Path $celProgramu -Filter '__pycache__' -Recurse -Directory -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    $znacznik = @"
wersja    = $wersja
rodzaj    = $rodzaj
commit    = $($stan.Skrot)
zbudowano = $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@
    Set-Content -LiteralPath (Join-Path $celProgramu 'WERSJA.txt') -Value $znacznik -Encoding UTF8

    if ($Pelna) {
        Pisz '        + binaria PostgreSQL (to potrwa)...' 'DarkGray'
        $silnik = Join-Path (Katalog-Silnika) 'pgsql'
        if (-not (Test-Path -LiteralPath $silnik)) {
            throw "Brak binariow bazy w $silnik. Uruchom najpierw: narzedzia\lokalny-postgres.ps1 setup"
        }
        Kopiuj-Do $silnik (Join-Path $roboczy 'silnik-bazy\pgsql')
        Kopiuj-Do (Join-Path $KatalogProgramu 'instalator') (Join-Path $roboczy 'instalator')
        # Pliki .cmd korzenia leza w repozytorium pod instalator\korzen, zeby nie
        # mieszaly sie z tymi, ktorych uzywa autor. W paczce ida na wierzch.
        Copy-Item -Path (Join-Path $KatalogProgramu 'instalator\korzen\*') -Destination $roboczy -Force
        Remove-Item -LiteralPath (Join-Path $roboczy 'instalator\korzen') -Recurse -Force
    }

    # ------------------------------------------------------------------ 4. zip
    Pisz '  [3/4] Pakuje...' 'Cyan'
    New-Item -ItemType Directory -Force -Path $KatalogWydan | Out-Null
    $nazwa = if ($Pelna) { "najem-instalacja-$wersja.zip" } else { "najem-$wersja.zip" }
    $plikZip = Join-Path $KatalogWydan $nazwa
    if (Test-Path -LiteralPath $plikZip) { Remove-Item -LiteralPath $plikZip -Force }

    Compress-Archive -Path (Join-Path $roboczy '*') -DestinationPath $plikZip -CompressionLevel Optimal

    Pisz '  [4/4] Gotowe.' 'Cyan'
    $rozmiar = [math]::Round((Get-Item -LiteralPath $plikZip).Length / 1MB, 1)
    Pisz ''
    Pisz "  $plikZip" 'Green'
    Pisz "  rozmiar: $rozmiar MB" 'DarkGray'
    Pisz ''
    if ($Pelna) {
        Pisz '  Rozpakuj to u uzytkownika i uruchom Zainstaluj.cmd.' 'DarkGray'
    }
    else {
        Pisz '  Wyslij ten plik uzytkownikowi. Przeciaga go na Aktualizuj.cmd.' 'DarkGray'
    }
}
finally {
    Remove-Item -LiteralPath $roboczy -Recurse -Force -ErrorAction SilentlyContinue
}
