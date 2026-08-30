<#
.SYNOPSIS
    Lokalny PostgreSQL 16 bez Dockera i bez uprawnien administratora.

.DESCRIPTION
    Baza dziala jako zwykly proces w katalogu projektu. Binaria ladujemy do
    tools/, dane trzymamy w pgdata/. Oba katalogi sa w .gitignore.

    Gdy kiedys pojawi sie Docker, wystarczy zatrzymac ten serwer i wstac
    "docker compose up -d db". DATABASE_URL nie zmienia sie ani o litere.

.PARAMETER Polecenie
    setup   pobierz binaria, zaloz baze i uzytkownika (idempotentne)
    start   wystartuj serwer
    stop    zatrzymaj serwer
    status  sprawdz, czy serwer odpowiada
    psql    otworz konsole SQL
    kopia   zrzuc baze do pliku (pg_dump -F c)
    reset   USUWA wszystkie dane i stawia baze od zera

.PARAMETER Plik
    Dla polecenia "kopia": gdzie zapisac zrzut. Bez tego trafia do katalogu
    kopii ze znacznikiem czasu w nazwie.
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'start', 'stop', 'status', 'psql', 'kopia', 'reset')]
    [string]$Polecenie = 'status',

    [string]$Plik
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

#: Gdzie leza binaria i dane, decyduje sciezki.ps1. W repozytorium wychodzi
#: z tego tools\pgsql i pgdata, czyli to samo co zawsze; w instalacji
#: u uzytkownika oba katalogi leza poza katalogiem programu, zeby aktualizacja
#: nie mogla ich dotknac.
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$WersjaPg   = '16.11-1'
$KatalogNarzedzi = Katalog-Silnika
$KatalogPg  = Join-Path $KatalogNarzedzi 'pgsql'
$BinPg      = Join-Path $KatalogPg 'bin'
$KatalogDanych = Katalog-Bazy
$PlikLogu   = Join-Path $KatalogDanych 'serwer.log'
$PlikBledow = Join-Path $KatalogDanych 'serwer-bledy.log'

$Port  = 5434
$Rola  = 'najem'
$Haslo = 'najem'
$Baza  = 'najem'
#: Osobna baza dla testow. Testy nigdy nie dotykaja bazy z prawdziwymi umowami.
$BazaTestowa = 'najem_testy'
$HasloSuper = 'postgres-lokalnie'

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }

function Sprawdz-Binaria {
    if (-not (Test-Path (Join-Path $BinPg 'pg_ctl.exe'))) {
        throw "Brak binariow PostgreSQL. Uruchom najpierw: lokalny-postgres.ps1 setup"
    }
}

function Czy-Dziala {
    Sprawdz-Binaria
    & (Join-Path $BinPg 'pg_isready.exe') -h 127.0.0.1 -p $Port -q 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Pobierz-Binaria {
    if (Test-Path (Join-Path $BinPg 'pg_ctl.exe')) {
        Pisz "Binaria PostgreSQL juz sa, pomijam pobieranie." 'DarkGray'
        return
    }
    New-Item -ItemType Directory -Force -Path $KatalogNarzedzi | Out-Null
    $zip = Join-Path $KatalogNarzedzi 'postgresql.zip'
    $url = "https://get.enterprisedb.com/postgresql/postgresql-$WersjaPg-windows-x64-binaries.zip"

    Pisz "Pobieram PostgreSQL $WersjaPg (okolo 350 MB, jednorazowo)..." 'Cyan'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

    Pisz 'Rozpakowuje...' 'Cyan'
    Expand-Archive -Path $zip -DestinationPath $KatalogNarzedzi -Force
    Remove-Item $zip -Force
    Pisz 'Binaria gotowe.' 'Green'
}

function Zaloz-Baze {
    if (Test-Path (Join-Path $KatalogDanych 'PG_VERSION')) {
        Pisz 'Katalog danych juz istnieje, pomijam initdb.' 'DarkGray'
        return
    }
    New-Item -ItemType Directory -Force -Path $KatalogDanych | Out-Null

    # Plik z haslem obok katalogu danych, nie w $env:TEMP. TEMP bywa sciezka
    # w formacie 8.3 ("C:\Users\HPOMEN~1\..."), a Remove-Item -LiteralPath
    # wywala sie wtedy na "An object at the specified path C:\Users\HPOMEN~1
    # does not exist" -- mimo -ErrorAction SilentlyContinue, bo to wyjatek
    # walidacji argumentu, a nie blad cmdletu.
    #
    # Pulapka byla niewidoczna w rozwoju: ta galaz wykonuje sie WYLACZNIE przy
    # pierwszym zakladaniu bazy, wiec u autora nigdy, a u uzytkownika za kazdym
    # pierwszym uruchomieniem. Znalazla ja dopiero proba generalna instalacji.
    $katalogHasla = Split-Path -Parent $KatalogDanych
    New-Item -ItemType Directory -Force -Path $katalogHasla | Out-Null
    $plikHasla = Join-Path $katalogHasla "najem-pg-haslo-$PID.txt"
    Set-Content -LiteralPath $plikHasla -Value $HasloSuper -NoNewline -Encoding ascii
    try {
        # Provider ICU z locale pl-PL: poprawne sortowanie polskich znakow
        # (a, a z ogonkiem, b, c, c z kreska...). Windowsowe Polish_Poland.1250
        # kloci sie z kodowaniem UTF8, wiec ta droga nie jest opcjonalna.
        Pisz 'Zakladam katalog danych (initdb)...' 'Cyan'
        & (Join-Path $BinPg 'initdb.exe') `
            --pgdata="$KatalogDanych" `
            --username=postgres `
            --pwfile="$plikHasla" `
            --encoding=UTF8 `
            --locale-provider=icu `
            --icu-locale=pl-PL `
            --locale=C `
            --auth-local=trust `
            --auth-host=scram-sha-256 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "initdb zakonczylo sie bledem $LASTEXITCODE" }
    }
    finally {
        Remove-Item -LiteralPath $plikHasla -Force -ErrorAction SilentlyContinue
    }

    Pisz 'Katalog danych gotowy.' 'Green'
}

function Ustaw-Konfiguracje {
    # Serwer slucha wylacznie na petli zwrotnej. Aplikacja jest wewnetrzna
    # (koncepcja, sekcja 8.1), wiec baza nie ma prawa byc widoczna z sieci.
    # Funkcja jest idempotentna: rozpoznaje wlasny wpis po znaczniku.
    $conf = Join-Path $KatalogDanych 'postgresql.conf'
    if (-not (Test-Path -LiteralPath $conf)) { throw "Brak $conf. Katalog danych jest uszkodzony." }

    if (Select-String -LiteralPath $conf -Pattern 'ustawienia projektu najem' -Quiet) {
        Pisz 'Konfiguracja projektu juz dopisana.' 'DarkGray'
        return
    }

    Add-Content -LiteralPath $conf -Encoding ascii -Value @"

# --- ustawienia projektu najem ---
port = $Port
listen_addresses = 'localhost'
max_connections = 50
shared_buffers = 256MB
log_timezone = 'UTC'
timezone = 'UTC'
"@
    Pisz 'Konfiguracja projektu dopisana.' 'Green'
}

function Zaloz-Role {
    $env:PGPASSWORD = $HasloSuper
    $psql = Join-Path $BinPg 'psql.exe'

    $istnieje = & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc `
        "SELECT 1 FROM pg_roles WHERE rolname = '$Rola'"
    if ($istnieje -ne '1') {
        & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -c `
            "CREATE ROLE $Rola LOGIN PASSWORD '$Haslo'" | Out-Null
        Pisz "Utworzono role $Rola." 'Green'
    }

    # Uprawnienie CREATEDB jest potrzebne, zeby testy mogly zalozyc sobie wlasna
    # baze. Bez niego pytest pracowalby na tej samej bazie, co program, i kazdy
    # przebieg mieszalby sie z prawdziwymi umowami.
    & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -c `
        "ALTER ROLE $Rola CREATEDB" | Out-Null

    foreach ($nazwa in @($Baza, $BazaTestowa)) {
        $bazaIstnieje = & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc `
            "SELECT 1 FROM pg_database WHERE datname = '$nazwa'"
        if ($bazaIstnieje -ne '1') {
            & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -c `
                "CREATE DATABASE $nazwa OWNER $Rola ENCODING 'UTF8'" | Out-Null
            Pisz "Utworzono baze $nazwa." 'Green'
        }
    }
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

function Czyj-Serwer {
    <#
        Zwraca katalog danych serwera, ktory odpowiada na naszym porcie,
        albo $null, gdy nie da sie tego ustalic.

        Czy-Dziala sprawdza tylko, czy COS odpowiada na 5434 -- nie czy to
        nasz serwer. Przy dwoch instalacjach na jednym komputerze druga cicho
        podlacza sie do bazy pierwszej i puszcza na niej migracje. Zdarzylo
        sie to naprawde, przy probie generalnej instalacji.
    #>
    $psql = Join-Path $BinPg 'psql.exe'
    if (-not (Test-Path -LiteralPath $psql)) { return $null }
    $env:PGPASSWORD = $HasloSuper
    try {
        $katalog = & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc 'SHOW data_directory' 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($katalog)) { return $null }
        return $katalog.Trim()
    }
    catch { return $null }
    finally { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }
}

function Sprawdz-Czy-Nasz {
    <# Wyklada sie glosno, gdy na porcie stoi cudzy serwer. #>
    $czyj = Czyj-Serwer
    if (-not $czyj) {
        throw @"
Na porcie $Port odpowiada serwer, z ktorym nie umiem sie polaczyc.
To nie jest baza tej instalacji. Zatrzymaj tamten serwer i sprobuj ponownie.
"@
    }
    # Postgres podaje sciezke z ukosnikami w druga strone niz Windows.
    $nasz = (Resolve-Path -LiteralPath $KatalogDanych).Path.Replace('\', '/').TrimEnd('/')
    $jego = $czyj.Replace('\', '/').TrimEnd('/')
    if ($nasz -ne $jego) {
        throw @"
Na porcie $Port dziala JUZ INNA baza tego programu:
    ta instalacja : $nasz
    na porcie     : $jego
Nie ruszam jej, bo migracje poszlyby na cudze dane. Zatrzymaj tamten
program (Zatrzymaj system.cmd w jego katalogu) i sprobuj ponownie.
"@
    }
}

function Start-Serwer {
    Sprawdz-Binaria
    if (Czy-Dziala) {
        if (Test-Path -LiteralPath (Join-Path $KatalogDanych 'PG_VERSION')) { Sprawdz-Czy-Nasz }
        Pisz "Baza juz dziala na porcie $Port." 'DarkGray'
        return
    }

    New-Item -ItemType Directory -Force -Path $KatalogDanych | Out-Null

    # Startujemy postgres.exe bezposrednio, a nie przez "pg_ctl start".
    # Na Windowsie pg_ctl przekazuje dziecku wlasne uchwyty konsoli i nie oddaje
    # sterowania, wiec skrypt wywolany nieinteraktywnie wisi mimo dzialajacej bazy.
    # Start-Process z przekierowaniem strumieni odlacza proces czysto.
    Start-Process -FilePath (Join-Path $BinPg 'postgres.exe') `
        -ArgumentList "-D `"$KatalogDanych`"" `
        -RedirectStandardOutput $PlikLogu `
        -RedirectStandardError $PlikBledow `
        -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 60; $i++) {
        if (Czy-Dziala) { Pisz "Baza dziala na porcie $Port." 'Green'; return }
        Start-Sleep -Milliseconds 500
    }

    Pisz "Baza nie wstala w 30 sekund. Zajrzyj do: $PlikBledow" 'Red'
    throw 'Nie udalo sie uruchomic bazy danych.'
}

function Zrzuc-Baze {
    <#
        Zrzut w formacie wlasnym pg_dump (-F c): kompresuje sie sam i daje
        sie czytac przez pg_restore --list bez odtwarzania czegokolwiek.
        Haslo i port zna ten skrypt, dlatego zrzut mieszka tutaj, a nie
        w aktualizatorze -- inaczej te same dane trzeba byloby powtorzyc.
    #>
    param([string]$Cel)

    Sprawdz-Binaria
    if (-not (Czy-Dziala)) { throw 'Baza nie dziala, nie ma czego zrzucic.' }

    if ([string]::IsNullOrWhiteSpace($Cel)) {
        $katalog = Katalog-Kopii
        New-Item -ItemType Directory -Force -Path $katalog | Out-Null
        $Cel = Join-Path $katalog ("najem-$(Get-Date -Format 'yyyy-MM-dd-HHmm').dump")
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Cel) | Out-Null

    $env:PGPASSWORD = $Haslo
    try {
        & (Join-Path $BinPg 'pg_dump.exe') -h 127.0.0.1 -p $Port -U $Rola -d $Baza `
            --format=custom --file="$Cel"
        if ($LASTEXITCODE -ne 0) { throw "pg_dump zakonczyl sie bledem $LASTEXITCODE" }
    }
    finally { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }

    $mb = [math]::Round((Get-Item -LiteralPath $Cel).Length / 1MB, 1)
    Pisz "Zrzut bazy: $Cel ($mb MB)" 'Green'
    return $Cel
}

function Stop-Serwer {
    Sprawdz-Binaria
    if (-not (Czy-Dziala)) { Pisz 'Baza nie dziala.' 'DarkGray'; return }
    & (Join-Path $BinPg 'pg_ctl.exe') -D "$KatalogDanych" -w -t 60 -m fast stop | Out-Null
    Pisz 'Baza zatrzymana.' 'Green'
}

switch ($Polecenie) {
    'setup' {
        Pobierz-Binaria
        Zaloz-Baze
        Ustaw-Konfiguracje
        Start-Serwer
        Zaloz-Role
        Pisz "`nGotowe. DATABASE_URL: postgresql+psycopg://${Rola}:${Haslo}@127.0.0.1:$Port/$Baza" 'Green'
    }
    'start'  { Start-Serwer }
    'stop'   { Stop-Serwer }
    'status' {
        if (Czy-Dziala) { Pisz "Baza dziala (localhost:$Port)." 'Green' }
        else { Pisz 'Baza nie dziala.' 'Yellow'; exit 1 }
    }
    'psql' {
        Sprawdz-Binaria
        $env:PGPASSWORD = $Haslo
        & (Join-Path $BinPg 'psql.exe') -h 127.0.0.1 -p $Port -U $Rola -d $Baza
    }
    'kopia' { Zrzuc-Baze -Cel $Plik | Out-Null }
    'reset' {
        Pisz 'To usunie WSZYSTKIE dane z lokalnej bazy.' 'Yellow'
        $odp = Read-Host 'Wpisz TAK, zeby potwierdzic'
        if ($odp -ne 'TAK') { Pisz 'Przerwane.' ; exit 1 }
        if (Czy-Dziala) { Stop-Serwer }
        Remove-Item -Recurse -Force $KatalogDanych -ErrorAction SilentlyContinue
        Zaloz-Baze; Ustaw-Konfiguracje; Start-Serwer; Zaloz-Role
        Pisz 'Baza postawiona od zera.' 'Green'
    }
}
