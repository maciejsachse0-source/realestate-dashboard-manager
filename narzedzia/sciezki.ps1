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
#>

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
        350 MB binariow, ktore i tak sie nie zmieniaja.
    #>
    if (Katalog-Instalacji) { return (Join-Path (Katalog-Instalacji) 'silnik-bazy') }
    return (Join-Path (Katalog-Programu) 'tools')
}

function Plik-Env {
    <# Konfiguracja. Nalezy do danych, nie do programu: aktualizacja jej nie rusza. #>
    if (Katalog-Instalacji) { return (Join-Path (Katalog-Danych) '.env') }
    return (Join-Path (Katalog-Programu) '.env')
}

function Katalog-Logow { return (Join-Path (Katalog-Danych) 'logi') }

function Katalog-Kopii { return (Join-Path (Katalog-Danych) 'kopie') }
