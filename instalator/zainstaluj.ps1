<#
.SYNOPSIS
    Zaklada instalacje programu na komputerze uzytkownika. Uruchamiane raz.

.DESCRIPTION
    Rozpakowana paczka pelna wyglada tak:

        C:\SystemNajmu\
          program\           kod, podmieniany przy kazdej aktualizacji
          silnik-bazy\pgsql  binaria PostgreSQL, niezalezne od wersji
          instalator\        ten skrypt, aktualizator, cofanie
          *.cmd              to, co klika uzytkownik

    Ten skrypt doklada do tego katalog "dane" i doprowadza program do stanu
    uzywalnosci. Wszystko jest idempotentne: powtorne uruchomienie niczego
    nie psuje i nie nadpisuje istniejacej konfiguracji.

    POTRZEBNY INTERNET, ale tylko teraz. uv sciaga interpreter Pythona
    i biblioteki. Codzienna praca programu nie wychodzi do sieci ani razu
    (koncepcja, sekcja 8.1).
#>

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'wspolne.ps1')

$Korzen = Split-Path -Parent $PSScriptRoot
$KatalogProgramu = Join-Path $Korzen 'program'
$KatalogDanych = Join-Path $Korzen 'dane'
$PlikEnv = Join-Path $KatalogDanych '.env'
$SkryptBazy = Join-Path $KatalogProgramu 'narzedzia\lokalny-postgres.ps1'

$Host.UI.RawUI.WindowTitle = 'Instalacja Systemu Najmu'

Pisz ''
Pisz '  Instalacja Systemu Najmu' 'White'
Pisz '  ------------------------' 'DarkGray'
Pisz ''
Pisz "  Katalog instalacji: $Korzen" 'DarkGray'
Pisz ''

try {
    # ------------------------------------------------------------ 1. uv
    Krok 1 'Sprawdzam srodowisko...'
    if (-not (Test-Path -LiteralPath $KatalogProgramu)) {
        Zakoncz-Bledem "Brak katalogu $KatalogProgramu. Paczka nie zostala rozpakowana w calosci."
    }
    if (-not (Get-Command 'uv' -ErrorAction SilentlyContinue)) {
        Pisz ''
        Pisz '  Brakuje programu "uv". To jedyna rzecz, ktora trzeba zainstalowac' 'Red'
        Pisz '  osobno. Instalacja trwa minute i nie wymaga uprawnien administratora:' 'DarkGray'
        Pisz ''
        Pisz '      https://docs.astral.sh/uv/getting-started/installation/' 'White'
        Pisz ''
        Pisz '  Potem uruchom ten plik jeszcze raz.' 'DarkGray'
        Pisz ''
        Read-Host '  Nacisnij Enter, zeby zamknac'
        exit 1
    }

    # -------------------------------------------------------- 2. katalogi
    Krok 2 'Zakladam katalogi na dane...'
    foreach ($podkatalog in @('', 'dokumenty', 'kopie', 'logi')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $KatalogDanych $podkatalog) | Out-Null
    }
    Pisz "      $KatalogDanych" 'DarkGray'
    Pisz '      Tego katalogu aktualizacja nie dotyka. Nigdy.' 'DarkGray'

    # ------------------------------------------------------ 3. konfiguracja
    Krok 3 'Przygotowuje konfiguracje...'
    if (Test-Path -LiteralPath $PlikEnv) {
        Pisz '      Konfiguracja juz istnieje, zostawiam ja bez zmian.' 'DarkGray'
    }
    else {
        Pisz ''
        Pisz '      Gdzie maja trafiac kopie zapasowe?' 'White'
        Pisz '      Dysk zewnetrzny, OneDrive albo sciezka sieciowa -- byle POZA' 'DarkGray'
        Pisz '      tym komputerem. Dokumenty nie sa kopiowane do programu, tylko' 'DarkGray'
        Pisz '      linkowane, wiec awaria dysku zabiera baze i pliki naraz.' 'DarkGray'
        Pisz '      Mozna zostawic puste i ustawic to pozniej w pliku dane\.env.' 'DarkGray'
        Pisz ''
        # Cudzyslowy wokol podstawienia sa konieczne. Bez konsoli (uruchomienie
        # z potoku, z zadania, ze zdalnej sesji) Read-Host zwraca $null,
        # a .Trim() na nim konczy instalacje komunikatem "You cannot call
        # a method on a null-valued expression" -- w polowie zakladania
        # katalogow i bez slowa o tym, co wlasciwie poszlo nie tak.
        # Rzutowanie ([string]$null) tu NIE pomaga: w PowerShellu 5.1 daje
        # z powrotem $null, nie pusty napis. Sprawdzone, nie zgadywane.
        $katalogKopii = "$(Read-Host '      Katalog kopii')".Trim().Trim('"')

        $tresc = @"
# Konfiguracja instalacji. Aktualizacja programu tego pliku nie dotyka.
# Zalozony przez instalator $(Get-Date -Format 'yyyy-MM-dd HH:mm').

SRODOWISKO=prod

DATABASE_URL=postgresql+psycopg://najem:najem@127.0.0.1:5434/najem

API_HOST=127.0.0.1
API_PORT=8010

# Dokumenty wgrywane przez program. Kopiowane sa tylko te; dokumenty
# wskazane na dysku zostaja odnosnikami i leza tam, gdzie lezaly.
KATALOG_DOKUMENTOW=$(Join-Path $KatalogDanych 'dokumenty')

# Katalog z dokumentami na dysku wskazuje sie w programie, na ekranie
# "Dokumenty z dysku". Ustawienie z bazy przykrywa to, co tutaj.
KATALOG_SKANU=

STREFA_PREZENTACJI=Europe/Warsaw

KATALOG_KOPII=$katalogKopii
"@
        Set-Content -LiteralPath $PlikEnv -Value $tresc -Encoding UTF8
        Pisz "      $PlikEnv" 'DarkGray'
    }

    # ------------------------------------------------------------- 4. baza
    Krok 4 'Zakladam baze danych...'
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy setup
    if ($LASTEXITCODE -ne 0) { Zakoncz-Bledem 'Nie udalo sie zalozyc bazy danych.' }

    Krok 5 'Buduje strukture bazy...'
    Pisz '      Za pierwszym razem uv pobiera Pythona i biblioteki. Kilka minut.' 'DarkGray'
    $env:NAJEM_PLIK_ENV = $PlikEnv
    # Poza katalogiem "program", zeby aktualizacja tego nie kasowala.
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $Korzen 'srodowisko'
    Push-Location (Join-Path $KatalogProgramu 'backend')
    try {
        & uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Budowanie struktury bazy nie powiodlo sie.' }
    }
    finally { Pop-Location }

    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy stop

    # -------------------------------------------------- 6. skrot i kopie
    Krok 6 'Tworze skrot i zadanie kopii zapasowej...'
    $cel = Join-Path $Korzen 'Uruchom system najmu.cmd'
    $skrot = Join-Path ([Environment]::GetFolderPath('Desktop')) 'System Najmu.lnk'
    $powloka = New-Object -ComObject WScript.Shell
    $link = $powloka.CreateShortcut($skrot)
    $link.TargetPath = $cel
    $link.WorkingDirectory = $Korzen
    $link.Description = 'System Zarzadzania Umowami Najmu'
    $link.IconLocation = "$env:SystemRoot\System32\imageres.dll,174"
    $link.Save()
    Pisz "      $skrot" 'DarkGray'

    & powershell -ExecutionPolicy Bypass -NoProfile `
        -File (Join-Path $KatalogProgramu 'narzedzia\zaplanuj-kopie.ps1')

    Set-Content -LiteralPath (Join-Path $KatalogDanych 'historia-wersji.txt') `
        -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  instalacja"

    Pisz ''
    Pisz '  Gotowe.' 'Green'
    Pisz ''
    Pisz '  Na pulpicie jest skrot "System Najmu". Kliknij go dwa razy.' 'DarkGray'
    Pisz '  Pierwsze uruchomienie trwa dluzej niz kolejne.' 'DarkGray'
    Pisz ''
    Pisz '  Katalog z dokumentami wskazuje sie juz w samym programie,' 'DarkGray'
    Pisz '  na ekranie "Dokumenty z dysku".' 'DarkGray'
    Pisz ''
}
catch {
    Zakoncz-Bledem $_.Exception.Message
}

Read-Host '  Nacisnij Enter, zeby zamknac'
