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
$SkryptStopu = Join-Path $PSScriptRoot 'zatrzymaj.ps1'
$Backend = Join-Path $KatalogRepo 'backend'
$Frontend = Join-Path $KatalogRepo 'frontend'
$Adres = 'http://127.0.0.1:8010'
#: Ustawiane, gdy program juz dzialal i baza nalezy do tamtego uruchomienia.
$ZostawBaze = $false

$Host.UI.RawUI.WindowTitle = 'System Zarzadzania Umowami Najmu'

function Krok($numer, $tekst) { Write-Host "[$numer/5] $tekst" -ForegroundColor Cyan }
function Blad($tekst) { Write-Host "`n  BLAD: $tekst`n" -ForegroundColor Red }

function Powod-Przebudowy {
    <#
    .SYNOPSIS
        Mowi, dlaczego trzeba zbudowac interfejs. Pusty tekst = nie trzeba.

    .DESCRIPTION
        Wczesniej warunkiem bylo samo istnienie pliku dist\index.html. Skutek:
        po pierwszym zbudowaniu skrot nie przebudowywal interfejsu juz nigdy.
        Backend startowal z biezacego kodu, front z bundla sprzed zmian, a dla
        osoby klikajacej ikonke wygladalo to tak, jakby zmiany nie istnialy.

        Dlatego porownujemy czasy: gdy ktorykolwiek plik zrodlowy jest nowszy
        od zbudowanego index.html, budujemy od nowa.
    #>
    param(
        [Parameter(Mandatory)] [string]$Dist,
        [Parameter(Mandatory)] [string]$Frontend,
        [switch]$Wymuszono
    )

    if ($Wymuszono) { return 'Wymuszono przebudowe interfejsu.' }
    if (-not (Test-Path $Dist)) { return 'Interfejsu jeszcze nie zbudowano, robie to teraz.' }

    $zbudowano = (Get-Item $Dist).LastWriteTime

    # Wszystko, co realnie wplywa na zawartosc bundla. node_modules celowo poza
    # lista: instalacja skladnikow dotyka tysiecy plikow i przebudowywalaby
    # interfejs przy kazdym uruchomieniu.
    $zrodla = @(
        (Join-Path $Frontend 'src'),
        (Join-Path $Frontend 'index.html'),
        (Join-Path $Frontend 'package.json'),
        (Join-Path $Frontend 'vite.config.ts')
    )

    foreach ($sciezka in $zrodla) {
        if (-not (Test-Path $sciezka)) { continue }
        $nowszy = Get-ChildItem -Path $sciezka -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -gt $zbudowano } |
            Select-Object -First 1
        if ($nowszy) {
            return "Interfejs zmienil sie od ostatniego uruchomienia ($($nowszy.Name)), buduje od nowa."
        }
    }

    return ''
}

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
    $powodBudowy = Powod-Przebudowy -Dist $dist -Frontend $Frontend -Wymuszono:$PrzebudujInterfejs

    if ($powodBudowy) {
        Write-Host "      $powodBudowy" -ForegroundColor DarkGray
        Push-Location $Frontend
        try {
            if (-not (Test-Path 'node_modules')) {
                Write-Host '      Instaluje skladniki interfejsu...' -ForegroundColor DarkGray
                & npm install --no-audit --no-fund | Out-Null
            }
            # Bez "| Out-Null": przy bledzie budowania log jest jedyna
            # informacja, co poszlo nie tak. Trzymamy go w zmiennej i pokazujemy
            # dopiero wtedy, gdy cos sie wywroci. Zadnego "2>&1" - PowerShell 5.1
            # opakowuje kazda linie stderr w ErrorRecord i przerywa skrypt.
            $logBudowy = & npm run build
            if ($LASTEXITCODE -ne 0) {
                $logBudowy | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
                throw 'Budowanie interfejsu nie powiodlo sie.'
            }
            Write-Host '      Interfejs zbudowany.' -ForegroundColor DarkGray
        }
        finally { Pop-Location }
    }
    else {
        Write-Host '      Interfejs aktualny.' -ForegroundColor DarkGray
    }

    # ---------------------------------------------------------------- 5. aplikacja
    Krok 5 'Startuje aplikacje...'

    # Zajety port 8010 prawie zawsze znaczy, ze program juz raz uruchomiono
    # i nadal dziala. Uvicorn wypisalby wtedy blad WinError 10048, ktory nikomu
    # nic nie mowi, i zakonczyl sie od razu, zamykajac to okno.
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port 8010 -InformationLevel Quiet -WarningAction SilentlyContinue) {
        Write-Host ''
        Write-Host '  Program juz dziala.' -ForegroundColor Green
        Write-Host ''
        Write-Host '    [1] Otworz go w przegladarce' -ForegroundColor Gray
        Write-Host '    [2] Uruchom od nowa, zatrzymujac to, co dziala' -ForegroundColor Gray
        Write-Host ''
        Write-Host '  Wybierz 2, jesli program zachowuje sie dziwnie albo nie widac' -ForegroundColor DarkGray
        Write-Host '  ostatnich zmian. Poprzednie uruchomienie ma w pamieci stary kod.' -ForegroundColor DarkGray
        Write-Host ''
        $wybor = Read-Host '  Twoj wybor [1]'

        if ($wybor -eq '2') {
            Write-Host ''
            Write-Host '      Zatrzymuje poprzednie uruchomienie...' -ForegroundColor DarkGray
            & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptStopu -TylkoAplikacja
            if ($LASTEXITCODE -ne 0) {
                throw 'Nie udalo sie zwolnic portu 8010. Zamknij okno programu recznie i sprobuj ponownie.'
            }

            # Okno, ktore wlasnie zamknelismy, w swoim bloku finally zatrzymuje
            # takze baze. Dlatego stawiamy ja z powrotem, zamiast zakladac, ze
            # stoi, bo krok 2 wykonal sie chwile przed tym zatrzymaniem.
            # Bez "| Out-Null": potok czeka, az zamknie sie uchwyt stdout, a ten
            # dziedziczy uruchomiony postgres.exe, wiec skrypt wisialby w
            # nieskonczonosc mimo dzialajacej bazy. Krok 2 wola to tak samo.
            Start-Sleep -Seconds 2
            & powershell -ExecutionPolicy Bypass -File $SkryptBazy start
            if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie uruchomic bazy danych.' }
        }
        else {
            Write-Host "  Otwieram go pod adresem: $Adres" -ForegroundColor Green
            if (-not $BezPrzegladarki) { Start-Process $Adres }
            Read-Host '  Nacisnij Enter, zeby zamknac to okno'
            # Baza nalezy do tamtego uruchomienia, wiec jej nie zatrzymujemy.
            $ZostawBaze = $true
            exit 0
        }
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
