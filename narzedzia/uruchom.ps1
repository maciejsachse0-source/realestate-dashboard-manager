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
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$KatalogRepo = Katalog-Programu
$SkryptBazy = Join-Path $PSScriptRoot 'lokalny-postgres.ps1'
$SkryptStopu = Join-Path $PSScriptRoot 'zatrzymaj.ps1'
$Backend = Join-Path $KatalogRepo 'backend'
$Frontend = Join-Path $KatalogRepo 'frontend'
$Adres = 'http://127.0.0.1:8010'
#: Ustawiane, gdy program juz dzialal i baza nalezy do tamtego uruchomienia.
$ZostawBaze = $false

#: Konfiguracja nalezy do danych, nie do programu. W repozytorium wychodzi
#: z tego <repo>\.env, czyli to samo co zawsze.
$env:NAJEM_PLIK_ENV = Plik-Env

#: To samo srodowisko Pythona, ktore zbudowal instalator. Bez tego uv szuka
#: go w program\backend\.venv -- a tego katalogu u uzytkownika nie ma, bo
#: aktualizacja podmienia caly katalog "program". Pierwszy start konczylby
#: sie budowaniem drugiego srodowiska: kilka minut i internet, po kazdej
#: aktualizacji od nowa. W ukladzie deweloperskim zmiennej nie ustawiamy
#: wcale, wiec uv bierze backend\.venv i nic sie dla autora nie zmienia.
$srodowisko = Katalog-Srodowiska
if ($srodowisko) { $env:UV_PROJECT_ENVIRONMENT = $srodowisko }

$Host.UI.RawUI.WindowTitle = 'System Zarzadzania Umowami Najmu'

function Krok($numer, $tekst) { Write-Host "[$numer/5] $tekst" -ForegroundColor Cyan }
function Blad($tekst) { Write-Host "`n  BLAD: $tekst`n" -ForegroundColor Red }

function Ostrzez-O-Kopii {
    <#
    .SYNOPSIS
        Krzyczy przy starcie, gdy kopii zapasowej dawno nie bylo.

    .DESCRIPTION
        Zadanie kopii chodzi z Harmonogramu w UKRYTYM oknie. Gdy dysk kopii
        zniknie -- pendrive wyjety z portu, zmieniona litera dysku -- kopie
        przestana sie robic i nikt sie o tym nie dowie. Bez chmury nie ma
        drugiego miejsca, wiec jedyna ochrona jest to, ze czlowiek to zobaczy.

        Start programu to jedyny moment, w ktorym on na pewno patrzy na ekran.
    #>
    param([int]$IleDniToDuzo = 3)

    if (-not (Katalog-Instalacji)) { return }

    $plik = Join-Path (Katalog-Danych) 'stan-kopii.txt'
    if (-not (Test-Path -LiteralPath $plik)) {
        Write-Host ''
        Write-Host '  UWAGA: kopia zapasowa nie wykonala sie ani razu.' -ForegroundColor Yellow
        Write-Host '  Awaria dysku skasowalaby baze i dokumenty naraz.' -ForegroundColor DarkGray
        Write-Host ''
        return
    }

    # Kazde pole czytamy osobno i ostroznie. Uciety albo recznie zepsuty plik
    # nie moze wywrocic startu programu ani -- co gorsza -- udawac awarii
    # kopii, ktorej nie bylo.
    $tresc = @(Get-Content -LiteralPath $plik -Encoding UTF8 -ErrorAction SilentlyContinue)

    function Pole($nazwa) {
        $trafienie = $tresc | Select-String "^$nazwa\s*=\s*(.+)$" | Select-Object -First 1
        if ($trafienie) { return $trafienie.Matches[0].Groups[1].Value.Trim() }
        return ''
    }

    $data = Pole 'data'
    $wynik = Pole 'wynik'

    $kiedy = [datetime]::MinValue
    $dataCzytelna = [datetime]::TryParse($data, [ref]$kiedy)

    if (-not $dataCzytelna -or -not $wynik) {
        Write-Host ''
        Write-Host '  UWAGA: nie umiem odczytac stanu kopii zapasowej.' -ForegroundColor Yellow
        Write-Host "  Zajrzyj do: $plik" -ForegroundColor DarkGray
        Write-Host ''
        return
    }

    $dni = [int]((Get-Date) - $kiedy).TotalDays

    if ($wynik -ne 'OK') {
        Write-Host ''
        Write-Host "  UWAGA: ostatnia kopia zapasowa ($data) NIE UDALA SIE." -ForegroundColor Red
        Write-Host '  Sprawdz, czy dysk na kopie jest podlaczony.' -ForegroundColor Yellow
        Write-Host ''
    }
    elseif ($dni -gt $IleDniToDuzo) {
        Write-Host ''
        Write-Host "  UWAGA: ostatnia kopia zapasowa byla $dni dni temu ($data)." -ForegroundColor Yellow
        Write-Host '  Sprawdz, czy dysk na kopie jest podlaczony.' -ForegroundColor DarkGray
        Write-Host ''
    }
}

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

# U uzytkownika nikt nie zajrzy przez ramie w okno programu, a komunikat
# o bledzie znika razem z nim. Transcript zapisuje cala sesje, razem z tym,
# co wypisuje uvicorn, i nie wymaga przekierowania strumieni: "2>&1"
# w PowerShell 5.1 opakowuje kazda linie stderr w ErrorRecord i przerywa
# skrypt. W repozytorium nie zapisujemy nic -- tam log jest na ekranie.
$Transkrypcja = $false
if (Katalog-Instalacji) {
    $katalogLogow = Katalog-Logow
    New-Item -ItemType Directory -Force -Path $katalogLogow | Out-Null
    Get-ChildItem -Path $katalogLogow -Filter 'aplikacja-*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 14 |
        Remove-Item -Force -ErrorAction SilentlyContinue
    $plikLogu = Join-Path $katalogLogow "aplikacja-$(Get-Date -Format 'yyyy-MM-dd').log"
    Start-Transcript -Path $plikLogu -Append -ErrorAction SilentlyContinue | Out-Null
    $Transkrypcja = $?
}

Write-Host ''
Write-Host '  System Zarzadzania Umowami Najmu' -ForegroundColor White
Write-Host '  --------------------------------' -ForegroundColor DarkGray
Write-Host ''

try {
    # ---------------------------------------------------------------- 1. narzedzia
    Krok 1 'Sprawdzam srodowisko...'
    # Tylko uv. Node.js sprawdzamy dopiero w kroku 4 i wylacznie wtedy, gdy
    # naprawde trzeba budowac interfejs. Paczka wydania niesie gotowy
    # frontend/dist bez zrodel, wiec na komputerze uzytkownika Node nie jest
    # do niczego potrzebny -- a wymaganie go tutaj zatrzymywalo caly program
    # na pierwszym kroku, zanim cokolwiek zdazylo wstac.
    if (-not (Get-Command 'uv' -ErrorAction SilentlyContinue)) {
        Blad "Brakuje programu 'uv'. Zajrzyj do README.md, sekcja 'Instalacja od zera'."
        Read-Host 'Nacisnij Enter, zeby zamknac'
        exit 1
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

        if (-not (Get-Command 'npm' -ErrorAction SilentlyContinue)) {
            Blad @'
Trzeba zbudowac interfejs, ale brakuje programu Node.js (npm).
To nie powinno zdarzyc sie na komputerze uzytkownika: paczka wydania
niesie gotowy interfejs. Jesli widzisz to u siebie, zainstaluj Node.js
(README.md, sekcja "Instalacja od zera"). Jesli u uzytkownika --
paczka zostala zlozona blednie i trzeba wydac ja od nowa.
'@
            Read-Host 'Nacisnij Enter, zeby zamknac'
            exit 1
        }

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
    Ostrzez-O-Kopii

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
    if ($Transkrypcja) { Stop-Transcript -ErrorAction SilentlyContinue | Out-Null }
}
