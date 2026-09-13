<#
.SYNOPSIS
    Kawalki wspolne dla zainstaluj.ps1, aktualizuj.ps1 i cofnij.ps1.

.DESCRIPTION
    Te trzy skrypty musza byc samodzielne wzgledem katalogu "program", bo
    aktualizacja zmienia jego nazwe w trakcie swojego dzialania. Dlatego nie
    dolaczaja narzedzia\sciezki.ps1 i licza sciezki od wlasnego polozenia.

    Nie znaczy to jednak, ze maja powtarzac wszystko miedzy soba. Czytanie
    WERSJA.txt bylo do niedawna w dwoch plikach, co do znaku, a komunikat
    bledu w trzech wariantach, ktore zdazyly sie rozjechac. To siedzi tutaj.

    UWAGA: ten plik lezy w instalator\ i -- tak samo jak reszta tego katalogu
    -- NIE aktualizuje sie sam. Jego poprawka wymaga recznej podmiany
    u uzytkownika, wiec ma byc krotki i rzadko ruszany (ADR 010).
#>

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }

function Krok($numer, $tekst, $zIlu = 6) {
    Write-Host "[$numer/$zIlu] $tekst" -ForegroundColor Cyan
}

function Czytaj-Wersje($katalog) {
    <#
        Wersja wydania z WERSJA.txt. Brak pliku to nie blad: tak wyglada
        program uruchamiany prosto z repozytorium autora.
    #>
    $plik = Join-Path $katalog 'WERSJA.txt'
    if (-not (Test-Path -LiteralPath $plik)) { return 'nieznana' }
    $wiersz = Select-String -LiteralPath $plik -Pattern '^wersja\s*=\s*(.+)$' | Select-Object -First 1
    if (-not $wiersz) { return 'nieznana' }
    return $wiersz.Matches[0].Groups[1].Value.Trim()
}

function Zakoncz-Bledem($tekst) {
    <#
        Konczy prace z komunikatem i czeka na Enter, zeby okno nie zniknelo
        razem z trescia bledu.

        $DopisekBledu ustawia wolajacy skrypt (plik jest dolaczany przez
        kropke, wiec jego zmienne sa tu widoczne). Aktualizator wpisuje tam
        "program zostal bez zmian" -- co jest prawda tylko dlatego, ze
        wszystkie jego wywolania tej funkcji sa PRZED podmiana katalogow.
        Gdyby kiedys doszlo wywolanie po podmianie, ten dopisek staje sie
        klamstwem i trzeba go wtedy podac inaczej.
    #>
    Pisz ''
    Pisz "  NIE UDALO SIE: $tekst" 'Red'
    Pisz ''
    if ($DopisekBledu) {
        Pisz "  $DopisekBledu" 'Yellow'
        Pisz ''
    }
    Read-Host '  Nacisnij Enter, zeby zamknac'
    exit 1
}
