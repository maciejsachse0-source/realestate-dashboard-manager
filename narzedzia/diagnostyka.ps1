<#
.SYNOPSIS
    Sklada plik z informacjami o stanie programu, do wyslania autorowi.

.DESCRIPTION
    Powstal, bo opis "nie dziala" nie wystarcza do naprawy, a zdalny pulpit
    wymaga umawiania sie na godzine. Uzytkownik klika Diagnostyka.cmd,
    dostaje jeden plik zip na pulpicie i wysyla go mailem.

    CO WCHODZI DO PLIKU:
      - wersja programu i historia aktualizacji
      - numer migracji bazy (alembic current)
      - liczba wierszy w kazdej tabeli, bez zadnej ich zawartosci
      - nazwy ustawien z .env wraz z informacja "ustawione / puste",
        ale BEZ WARTOSCI -- sciezki potrafia zdradzac nazwy klientow
      - logi techniczne programu i bazy z ostatnich dni

    CZEGO NIE MA: nazw najemcow, kwot, tresci dokumentow, sciezek do nich.

    Logi to jedyne miejsce, gdzie teoretycznie moze przeciec cos z danych --
    np. w tresci komunikatu o bledzie. Dlatego plik zostaje na pulpicie
    i to czlowiek decyduje, czy go wyslac, zamiast zeby program wysylal
    cokolwiek sam.
#>

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$KatalogProgramu = Katalog-Programu
$KatalogDanych = Katalog-Danych

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }

Pisz ''
Pisz '  Diagnostyka Systemu Najmu' 'White'
Pisz '  -------------------------' 'DarkGray'
Pisz ''

$roboczy = Join-Path $KatalogDanych "_diagnostyka-$PID"
New-Item -ItemType Directory -Force -Path $roboczy | Out-Null

try {
    # ------------------------------------------------------------- podsumowanie
    $raport = New-Object System.Collections.Generic.List[string]
    $raport.Add("Diagnostyka Systemu Najmu")
    $raport.Add("zebrano  : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $raport.Add("windows  : $([Environment]::OSVersion.VersionString)")
    $raport.Add("instalacja: $(if (Katalog-Instalacji) { Katalog-Instalacji } else { 'repozytorium (tryb deweloperski)' })")
    $raport.Add('')

    $plikWersji = Join-Path $KatalogProgramu 'WERSJA.txt'
    $raport.Add('--- WERSJA ---')
    if (Test-Path -LiteralPath $plikWersji) {
        $raport.AddRange([string[]](Get-Content -LiteralPath $plikWersji))
    }
    else { $raport.Add('brak pliku WERSJA.txt (program uruchamiany z repozytorium)') }
    $raport.Add('')

    # --------------------------------------------------------- ustawienia
    # Same nazwy i to, czy cos jest ustawione. Bez wartosci: sciezka
    # "C:\Umowy\Kowalski sp. z o.o." powiedzialaby wiecej, niz powinna.
    $raport.Add('--- USTAWIENIA (bez wartosci) ---')
    $plikEnv = Plik-Env
    if (Test-Path -LiteralPath $plikEnv) {
        foreach ($linia in (Get-Content -LiteralPath $plikEnv -Encoding UTF8)) {
            if ($linia -match '^\s*([A-Z_]+)\s*=\s*(.*)$') {
                $stan = if ([string]::IsNullOrWhiteSpace($Matches[2])) { 'puste' } else { 'ustawione' }
                $raport.Add("$($Matches[1]) = $stan")
            }
        }
    }
    else { $raport.Add("brak pliku: $plikEnv") }
    $raport.Add('')

    # ------------------------------------------------------------- baza
    $raport.Add('--- BAZA DANYCH ---')
    $psql = Join-Path (Katalog-Silnika) 'pgsql\bin\psql.exe'
    $bazaChodzi = $false
    & powershell -ExecutionPolicy Bypass -NoProfile -File (Join-Path $PSScriptRoot 'lokalny-postgres.ps1') status | Out-Null
    if ($LASTEXITCODE -eq 0) { $bazaChodzi = $true }
    $raport.Add("serwer: $(if ($bazaChodzi) { 'dziala' } else { 'nie dziala' })")

    if ($bazaChodzi -and (Test-Path -LiteralPath $psql)) {
        $env:PGPASSWORD = 'najem'
        try {
            $migracja = & $psql -h 127.0.0.1 -p 5434 -U najem -d najem -tAc 'SELECT version_num FROM alembic_version'
            $raport.Add("migracja: $($migracja -join ', ')")
            $raport.Add('')
            $raport.Add('liczba wierszy w tabelach:')
            # Same liczby. Zadnej zawartosci.
            $zapytanie = @'
SELECT relname || ' = ' || n_live_tup
FROM pg_stat_user_tables ORDER BY relname
'@
            $liczby = & $psql -h 127.0.0.1 -p 5434 -U najem -d najem -tAc $zapytanie
            $raport.AddRange([string[]]($liczby | Where-Object { $_ }))
        }
        catch { $raport.Add("nie udalo sie odpytac bazy: $($_.Exception.Message)") }
        finally { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }
    }
    $raport.Add('')

    # ------------------------------------------------------------ historia
    $raport.Add('--- HISTORIA WERSJI ---')
    $historia = Join-Path $KatalogDanych 'historia-wersji.txt'
    if (Test-Path -LiteralPath $historia) {
        $raport.AddRange([string[]](Get-Content -LiteralPath $historia -Encoding UTF8 -Tail 20))
    }
    else { $raport.Add('brak') }
    $raport.Add('')

    $raport.Add('--- KOPIE ZAPASOWE ---')
    $kopie = Katalog-Kopii
    if (Test-Path -LiteralPath $kopie) {
        $ostatnie = Get-ChildItem -Path $kopie -Filter '*.dump' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 5
        if ($ostatnie) {
            foreach ($k in $ostatnie) {
                $raport.Add("$($k.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))  $([math]::Round($k.Length/1MB,1)) MB")
            }
        }
        else { $raport.Add('BRAK ZRZUTOW BAZY -- kopia zapasowa moze sie nie wykonywac') }
    }
    else { $raport.Add('BRAK KATALOGU KOPII') }

    Set-Content -LiteralPath (Join-Path $roboczy 'podsumowanie.txt') -Value $raport -Encoding UTF8

    # --------------------------------------------------------------- logi
    $katalogLogow = Katalog-Logow
    if (Test-Path -LiteralPath $katalogLogow) {
        $celLogow = Join-Path $roboczy 'logi'
        New-Item -ItemType Directory -Force -Path $celLogow | Out-Null
        Get-ChildItem -Path $katalogLogow -File | Sort-Object LastWriteTime -Descending |
            Select-Object -First 5 |
            Copy-Item -Destination $celLogow -Force
    }
    foreach ($logBazy in @('serwer-bledy.log', 'serwer.log')) {
        $sciezka = Join-Path (Katalog-Bazy) $logBazy
        if (Test-Path -LiteralPath $sciezka) {
            Get-Content -LiteralPath $sciezka -Tail 300 |
                Set-Content -LiteralPath (Join-Path $roboczy "baza-$logBazy") -Encoding UTF8
        }
    }

    # ---------------------------------------------------------------- zip
    $plikZip = Join-Path ([Environment]::GetFolderPath('Desktop')) `
        "diagnostyka-najem-$(Get-Date -Format 'yyyy-MM-dd-HHmm').zip"
    if (Test-Path -LiteralPath $plikZip) { Remove-Item -LiteralPath $plikZip -Force }
    Compress-Archive -Path (Join-Path $roboczy '*') -DestinationPath $plikZip

    Pisz '  Gotowe. Na pulpicie jest plik:' 'Green'
    Pisz ''
    Pisz "      $(Split-Path -Leaf $plikZip)" 'White'
    Pisz ''
    Pisz '  Wyslij go mailem do autora programu.' 'DarkGray'
    Pisz '  Nie ma w nim nazw najemcow, kwot ani tresci dokumentow --' 'DarkGray'
    Pisz '  same informacje techniczne. Mozna go otworzyc i sprawdzic.' 'DarkGray'
    Pisz ''
}
finally {
    Remove-Item -LiteralPath $roboczy -Recurse -Force -ErrorAction SilentlyContinue
}

Read-Host '  Nacisnij Enter, zeby zamknac'
