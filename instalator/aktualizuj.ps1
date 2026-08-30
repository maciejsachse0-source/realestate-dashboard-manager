<#
.SYNOPSIS
    Wgrywa nowa wersje programu z paczki przyslanej przez autora.

.DESCRIPTION
    Kolejnosc jest ulozona tak, zeby na kazdym etapie dalo sie wrocic:

        1. rozpakuj paczke OBOK i sprawdz, czy jest kompletna
        2. dopiero teraz zatrzymaj program
        3. zrzuc baze do dane\kopie
        4. zmien nazwe "program" na "program-poprzednia"
        5. wstaw nowa wersje jako "program"
        6. zaktualizuj strukture bazy
        7. gdy krok 6 sie nie powiedzie -- wroc do poprzedniej wersji

    Punkt 1 przed punktem 2 jest celowy: zepsuta albo niekompletna paczka
    ma sie wylozyc, ZANIM ktokolwiek zatrzyma dzialajacy program.

    Katalog "dane" nie jest tu wymieniony ani razu i to jest cala idea.
    Baza, dokumenty i .env leza poza katalogiem programu, wiec aktualizacja
    fizycznie nie ma jak ich dotknac.

    Ten skrypt lezy w "instalator", poza katalogiem "program", bo w trakcie
    pracy zmienia nazwe tego drugiego. Z tego samego powodu NIE aktualizuje
    sam siebie -- gdyby kiedys wymagal poprawki, robi sie to recznie.
#>
param(
    [Parameter(Position = 0)]
    [string]$Paczka
)

$ErrorActionPreference = 'Stop'

$Korzen = Split-Path -Parent $PSScriptRoot
$KatalogProgramu = Join-Path $Korzen 'program'
$KatalogPoprzedni = Join-Path $Korzen 'program-poprzednia'
$KatalogDanych = Join-Path $Korzen 'dane'
$SkryptBazy = Join-Path $KatalogProgramu 'narzedzia\lokalny-postgres.ps1'
$SkryptStopu = Join-Path $KatalogProgramu 'narzedzia\zatrzymaj.ps1'
$HistoriaWersji = Join-Path $KatalogDanych 'historia-wersji.txt'

$Host.UI.RawUI.WindowTitle = 'Aktualizacja Systemu Najmu'

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }
function Krok($numer, $tekst) { Write-Host "[$numer/6] $tekst" -ForegroundColor Cyan }

function Zakoncz-Bledem($tekst) {
    Pisz ''
    Pisz "  NIE UDALO SIE: $tekst" 'Red'
    Pisz ''
    Pisz '  Program zostal bez zmian. Wyslij ten komunikat autorowi.' 'Yellow'
    Pisz ''
    Read-Host '  Nacisnij Enter, zeby zamknac'
    exit 1
}

function Wskaz-Paczke {
    <# Gdy nikt nie przeciagnal pliku na skrot, pytamy oknem wyboru. #>
    Add-Type -AssemblyName System.Windows.Forms
    $okno = New-Object System.Windows.Forms.OpenFileDialog
    $okno.Title = 'Wskaz paczke z nowa wersja programu'
    $okno.Filter = 'Paczka programu (*.zip)|*.zip'
    if ($okno.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
    return $okno.FileName
}

function Czytaj-Wersje($katalog) {
    $plik = Join-Path $katalog 'WERSJA.txt'
    if (-not (Test-Path -LiteralPath $plik)) { return 'nieznana' }
    $wiersz = Select-String -LiteralPath $plik -Pattern '^wersja\s*=\s*(.+)$' | Select-Object -First 1
    if (-not $wiersz) { return 'nieznana' }
    return $wiersz.Matches[0].Groups[1].Value.Trim()
}

Pisz ''
Pisz '  Aktualizacja Systemu Najmu' 'White'
Pisz '  --------------------------' 'DarkGray'
Pisz ''

if (-not (Test-Path -LiteralPath $KatalogProgramu)) {
    Zakoncz-Bledem "Nie widze katalogu $KatalogProgramu. Czy to na pewno katalog instalacji?"
}

if ([string]::IsNullOrWhiteSpace($Paczka)) { $Paczka = Wskaz-Paczke }
if ([string]::IsNullOrWhiteSpace($Paczka)) { Pisz '  Przerwane.' 'DarkGray'; exit 0 }
if (-not (Test-Path -LiteralPath $Paczka)) { Zakoncz-Bledem "Nie ma pliku: $Paczka" }

# Rozpakowujemy obok katalogu docelowego, na tym samym dysku. Dzieki temu
# Move-Item na koncu jest zwykla zmiana nazwy, a nie kopiowaniem setek
# megabajtow, i nie dotyka TEMP, ktorego krotka sciezka z tylda potrafi
# wywrocic Remove-Item.
$roboczy = Join-Path $Korzen "program-nowa"
$zrzut = $null
$przeniesiono = $false

try {
    # ------------------------------------------------------- 1. rozpakowanie
    Krok 1 'Sprawdzam paczke...'
    if (Test-Path -LiteralPath $roboczy) { Remove-Item -LiteralPath $roboczy -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $roboczy | Out-Null

    try { Expand-Archive -LiteralPath $Paczka -DestinationPath $roboczy -Force }
    catch { Zakoncz-Bledem "Nie umiem rozpakowac tego pliku. Czy na pewno to paczka programu?" }

    # Paczka niekompletna jest grozniejsza niz brak paczki: program wstalby
    # i dopiero wtedy zaczal sie sypac. Sprawdzamy wiec konkretne pliki,
    # a nie sam fakt, ze cos sie rozpakowalo.
    foreach ($wymagany in @(
            'WERSJA.txt',
            'backend\src\najem\main.py',
            'backend\alembic.ini',
            'frontend\dist\index.html',
            'narzedzia\uruchom.ps1',
            'narzedzia\sciezki.ps1'
        )) {
        if (-not (Test-Path -LiteralPath (Join-Path $roboczy $wymagany))) {
            Zakoncz-Bledem "Paczka jest niekompletna, brakuje w niej: $wymagany"
        }
    }

    $wersjaStara = Czytaj-Wersje $KatalogProgramu
    $wersjaNowa = Czytaj-Wersje $roboczy

    Pisz ''
    Pisz "      teraz masz wersje : $wersjaStara" 'DarkGray'
    Pisz "      zostanie wgrana   : $wersjaNowa" 'White'
    Pisz ''
    Pisz '      Program zostanie na chwile zatrzymany. Dane, dokumenty' 'DarkGray'
    Pisz '      i ustawienia zostaja nietkniete.' 'DarkGray'
    Pisz ''
    if ((Read-Host '  Wpisz TAK, zeby wgrac') -ne 'TAK') {
        Pisz '  Przerwane. Nic nie zostalo zmienione.' 'DarkGray'
        exit 0
    }

    # ------------------------------------------------------ 2. zatrzymanie
    Krok 2 'Zatrzymuje program...'
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptStopu -TylkoAplikacja

    # ------------------------------------------------------ 3. kopia bazy
    Krok 3 'Robie kopie bazy danych...'
    # Zadnego "| Out-Null" na wywolaniach lokalny-postgres.ps1. Start-Serwer
    # odpala postgres.exe z przekierowanymi strumieniami, a ten dziedziczy
    # uchwyt wyjscia procesu potomnego. Potok czeka wtedy na zamkniecie tego
    # uchwytu, czyli na zatrzymanie bazy -- i aktualizacja wisi w nieskonczonosc
    # mimo poprawnie dzialajacej bazy. Ta sama pulapka siedzi w uruchom.ps1.
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy start
    if ($LASTEXITCODE -ne 0) { Zakoncz-Bledem 'Nie udalo sie uruchomic bazy danych.' }

    $zrzut = Join-Path (Join-Path $KatalogDanych 'kopie') `
        ("przed-$wersjaNowa-$(Get-Date -Format 'yyyy-MM-dd-HHmm').dump")
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy kopia -Plik $zrzut
    if ($LASTEXITCODE -ne 0) { Zakoncz-Bledem 'Nie udalo sie zrobic kopii bazy. Aktualizacji nie zaczynam.' }

    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy stop

    # --------------------------------------------------- 4. podmiana wersji
    Krok 4 'Wstawiam nowa wersje...'
    if (Test-Path -LiteralPath $KatalogPoprzedni) {
        Remove-Item -LiteralPath $KatalogPoprzedni -Recurse -Force
    }
    # Zmiana nazwy, nie junction: Remove-Item na junctionie w PowerShell 5.1
    # potrafi wejsc w cel i skasowac to, na co wskazuje.
    Rename-Item -LiteralPath $KatalogProgramu -NewName 'program-poprzednia'
    $przeniesiono = $true
    Move-Item -LiteralPath $roboczy -Destination $KatalogProgramu

    # ------------------------------------------------------ 5. struktura bazy
    Krok 5 'Aktualizuje strukture bazy...'
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy start
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie uruchomic bazy danych.' }

    $env:NAJEM_PLIK_ENV = Join-Path $KatalogDanych '.env'
    # Srodowisko Pythona ma przezyc podmiane katalogu. Domyslne miejsce to
    # program\backend\.venv, wiec znikaloby przy kazdym wydaniu, a jego
    # odbudowa trwa minute i wymaga internetu albo pelnego cache uv.
    # Program mial nie potrzebowac sieci do pracy -- trzymamy je obok danych.
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $Korzen 'srodowisko'
    Push-Location (Join-Path $KatalogProgramu 'backend')
    try {
        & uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Aktualizacja struktury bazy nie powiodla sie.' }
    }
    finally { Pop-Location }

    # ------------------------------------------------------------ 6. zapis
    Krok 6 'Zapisuje slad...'
    Add-Content -LiteralPath $HistoriaWersji -Encoding UTF8 -Value `
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  $wersjaStara -> $wersjaNowa  (kopia: $(Split-Path -Leaf $zrzut))"

    Pisz ''
    Pisz "  Gotowe. Program ma teraz wersje $wersjaNowa." 'Green'
    Pisz ''
    Pisz '  Uruchom go jak zwykle, skrotem z pulpitu.' 'DarkGray'
    Pisz ''
    Read-Host '  Nacisnij Enter, zeby zamknac'
}
catch {
    # Cofamy sie tylko wtedy, gdy katalogi zdazyly sie zamienic. Zrzutu bazy
    # NIE przywracamy automatycznie: to decyzja czlowieka, nie skryptu.
    if ($przeniesiono) {
        Pisz ''
        Pisz '  Cos poszlo nie tak. Wracam do poprzedniej wersji...' 'Yellow'
        if (Test-Path -LiteralPath $KatalogProgramu) {
            Remove-Item -LiteralPath $KatalogProgramu -Recurse -Force -ErrorAction SilentlyContinue
        }
        Rename-Item -LiteralPath $KatalogPoprzedni -NewName 'program' -ErrorAction SilentlyContinue
        Pisz '  Poprzednia wersja wrocila na miejsce.' 'Green'
    }
    Pisz ''
    Pisz "  BLAD: $($_.Exception.Message)" 'Red'
    if ($zrzut) {
        Pisz ''
        Pisz "  Kopia bazy sprzed aktualizacji: $zrzut" 'DarkGray'
    }
    Pisz ''
    Pisz '  Wyslij ten komunikat autorowi programu.' 'Yellow'
    Pisz ''
    Read-Host '  Nacisnij Enter, zeby zamknac'
    exit 1
}
finally {
    if (Test-Path -LiteralPath $roboczy) {
        Remove-Item -LiteralPath $roboczy -Recurse -Force -ErrorAction SilentlyContinue
    }
}
