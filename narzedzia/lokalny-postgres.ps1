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
    reset   USUWA wszystkie dane i stawia baze od zera
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'start', 'stop', 'status', 'psql', 'reset')]
    [string]$Polecenie = 'status'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$WersjaPg   = '16.11-1'
$KatalogRepo = Split-Path -Parent $PSScriptRoot
$KatalogNarzedzi = Join-Path $KatalogRepo 'tools'
$KatalogPg  = Join-Path $KatalogNarzedzi 'pgsql'
$BinPg      = Join-Path $KatalogPg 'bin'
$KatalogDanych = Join-Path $KatalogRepo 'pgdata'
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

    $plikHasla = Join-Path $env:TEMP "najem-pg-haslo-$PID.txt"
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

function Start-Serwer {
    Sprawdz-Binaria
    if (Czy-Dziala) { Pisz "Baza juz dziala na porcie $Port." 'DarkGray'; return }

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
