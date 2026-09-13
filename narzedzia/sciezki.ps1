<#
.SYNOPSIS
    Mowi reszcie skryptow, gdzie leza dane, binaria bazy i plik .env.

.DESCRIPTION
    Program dziala w dwoch ukladach katalogow i to jest jedyne miejsce,
    ktore o tym wie.

    UKLAD DEWELOPERSKI (komputer autora, kopia repozytorium):
        <repo>\pgdata          baza
        <repo>\tools\pgsql     binaria PostgreSQL
        <repo>\dane            dokumenty, kopie, logi
        <repo>\.env            konfiguracja

    UKLAD INSTALACJI (komputer uzytkownika):
        C:\SystemNajmu\program            <- TYLKO TUTAJ siega aktualizacja
        C:\SystemNajmu\dane\pgdata
        C:\SystemNajmu\dane\.env
        C:\SystemNajmu\silnik-bazy\pgsql

    Ten podzial istnieje po to, zeby podmiana katalogu z programem nie mogla
    dotknac bazy ani dokumentow. Dopoki pgdata lezalo wewnatrz katalogu
    programu, kazda aktualizacja byla o jeden nieostrozny ruch od skasowania
    wszystkiego, co uzytkownik kiedykolwiek wprowadzil.

    Przelacznikiem jest zmienna srodowiskowa NAJEM_KATALOG_INSTALACJI,
    ustawiana przez "Uruchom system najmu.cmd" w korzeniu instalacji.
    Nieustawiona znaczy "uklad deweloperski", wiec praca na repozytorium
    wyglada dokladnie tak samo jak przed ta zmiana.

    Plik jest dolaczany przez ". (Join-Path $PSScriptRoot 'sciezki.ps1')",
    wiec celowo niczego nie wykonuje i nie ustawia zadnych preferencji --
    dzialalyby w zasiegu wolajacego.

    Nazwa mowi o sciezkach, bo to glowna robota tego pliku. Mieszkaja tu
    tez Czytaj-Env i Pisz: kazdy skrypt z narzedzia\ i tak dolacza ten plik,
    wiec trzymanie ich osobno konczylo sie kilkoma kopiami tego samego.
    Skrypty w instalator\ maja wlasny wspolne.ps1 i tego pliku nie dolaczaja
    ani nie moga -- powod przy Katalog-Programu.
#>

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }

function Katalog-Instalacji {
    <# Korzen instalacji u uzytkownika albo $null w ukladzie deweloperskim. #>
    if ([string]::IsNullOrWhiteSpace($env:NAJEM_KATALOG_INSTALACJI)) { return $null }
    return $env:NAJEM_KATALOG_INSTALACJI.TrimEnd('\')
}

function Katalog-Programu {
    <#
        Katalog z kodem. W obu ukladach jest to katalog nadrzedny wobec
        "narzedzia", wiec nie wymaga zadnego rozgalezienia: raz korzen
        repozytorium, raz <instalacja>\program.

        Dlatego wlasnie skrypty z instalator\ NIE korzystaja z tego pliku
        i licza sciezki same, od swojego wlasnego polozenia. Aktualizacja
        zmienia nazwe katalogu "program" w trakcie swojego dzialania, wiec
        skrypt, ktory siedzi w srodku, wyciagalby sobie grunt spod nog.
        To jedyne dozwolone powtorzenie wiedzy o ukladzie katalogow.
    #>
    return (Split-Path -Parent $PSScriptRoot)
}

function Katalog-Danych {
    $instalacja = Katalog-Instalacji
    if ($instalacja) { return (Join-Path $instalacja 'dane') }
    return (Join-Path (Katalog-Programu) 'dane')
}

function Katalog-Bazy {
    <# Katalog danych PostgreSQL (pgdata). #>
    if (Katalog-Instalacji) { return (Join-Path (Katalog-Danych) 'pgdata') }
    return (Join-Path (Katalog-Programu) 'pgdata')
}

function Katalog-Silnika {
    <#
        Katalog, do ktorego rozpakowuja sie binaria PostgreSQL. Zip zawiera
        w srodku folder "pgsql", stad tools\pgsql i silnik-bazy\pgsql.
        W instalacji lezy poza "program", zeby aktualizacja nie kasowala
        ~800 MB binariow, ktore i tak sie nie zmieniaja.
    #>
    if (Katalog-Instalacji) { return (Join-Path (Katalog-Instalacji) 'silnik-bazy') }
    return (Join-Path (Katalog-Programu) 'tools')
}

function Plik-Env {
    <# Konfiguracja. Nalezy do danych, nie do programu: aktualizacja jej nie rusza. #>
    if (Katalog-Instalacji) { return (Join-Path (Katalog-Danych) '.env') }
    return (Join-Path (Katalog-Programu) '.env')
}

function Katalog-Srodowiska {
    <#
        Srodowisko Pythona u uzytkownika albo $null w ukladzie deweloperskim.

        Domyslne miejsce uv to <projekt>\.venv, czyli program\backend\.venv --
        czyli w srodku katalogu, ktory aktualizacja podmienia w calosci.
        Instalator zaklada je wiec obok danych i **uruchom.ps1 musi celowac
        w to samo miejsce**, inaczej pierwszy start po instalacji buduje drugie
        srodowisko od zera: kilka minut i internet, ktorego program mial nie
        potrzebowac do pracy. Potem powtarza to po kazdej aktualizacji.

        $null u autora jest zamierzone: bez NAJEM_KATALOG_INSTALACJI nie
        ustawiamy UV_PROJECT_ENVIRONMENT w ogole i uv uzywa backend\.venv,
        czyli tego samego, co zawsze.

        Instalator liczy te sciezke sam (Join-Path $Korzen 'srodowisko'),
        bo nie wolno mu siegac do program\. Obie definicje musza zostac zgodne.
    #>
    $instalacja = Katalog-Instalacji
    if ($instalacja) { return (Join-Path $instalacja 'srodowisko') }
    return $null
}

function Czytaj-Env {
    <#
        Odczytuje .env do tablicy skrotow. Plik jest prosty: klucz=wartosc,
        bez cudzyslowow i bez sekcji, wiec tyle wystarczy.

        Stoi tutaj, a nie w kazdym skrypcie z osobna, bo wczesniej ten sam
        wzorzec byl w dwoch miejscach (kopia zapasowa i diagnostyka).
        Dwie kopie jednego wyrazenia regularnego to dwie okazje, zeby
        poprawic tylko jedna z nich.
    #>
    $wynik = @{}
    $plik = Plik-Env
    if (-not (Test-Path -LiteralPath $plik)) { return $wynik }
    foreach ($linia in (Get-Content -LiteralPath $plik -Encoding UTF8)) {
        if ($linia -match '^\s*([A-Z_]+)\s*=\s*(.*)$') {
            $wynik[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $wynik
}

function Katalog-Logow { return (Join-Path (Katalog-Danych) 'logi') }

function Katalog-Kopii { return (Join-Path (Katalog-Danych) 'kopie') }
