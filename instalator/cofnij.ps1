<#
.SYNOPSIS
    Wraca do wersji programu sprzed ostatniej aktualizacji.

.DESCRIPTION
    Zamienia miejscami "program" i "program-poprzednia". Trwa sekunde, bo
    to tylko zmiana nazw katalogow.

    UWAGA, ktora trzeba powiedziec wprost: cofa sie KOD, nie baza danych.
    Struktura bazy zostaje taka, jaka zrobila z niej aktualizacja. W tym
    projekcie migracje sa dokladajace (nic nie usuwamy fizycznie), wiec
    starsza wersja programu prawie zawsze sobie z tym poradzi. Prawie.

    Gdy po cofnieciu program zachowuje sie dziwnie, wlasciwym ruchem jest
    odtworzenie bazy ze zrzutu z dane\kopie -- i to juz robi autor, nie
    ten skrypt. Odtworzenie kasuje wszystko, co wprowadzono po zrzucie,
    wiec nie jest decyzja, ktora skrypt ma prawo podjac sam.
#>

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'wspolne.ps1')

$Korzen = Split-Path -Parent $PSScriptRoot
$KatalogProgramu = Join-Path $Korzen 'program'
$KatalogPoprzedni = Join-Path $Korzen 'program-poprzednia'
$KatalogTymczasowy = Join-Path $Korzen 'program-zamiana'
$SkryptStopu = Join-Path $KatalogProgramu 'narzedzia\zatrzymaj.ps1'
$HistoriaWersji = Join-Path $Korzen 'dane\historia-wersji.txt'

$Host.UI.RawUI.WindowTitle = 'Cofniecie aktualizacji'

Pisz ''
Pisz '  Cofniecie aktualizacji' 'White'
Pisz '  ----------------------' 'DarkGray'
Pisz ''

if (-not (Test-Path -LiteralPath $KatalogPoprzedni)) {
    Pisz '  Nie ma do czego wracac -- poprzedniej wersji nie ma na dysku.' 'Yellow'
    Pisz ''
    Read-Host '  Nacisnij Enter, zeby zamknac'
    exit 1
}

$teraz = Czytaj-Wersje $KatalogProgramu
$wroci = Czytaj-Wersje $KatalogPoprzedni

Pisz "      teraz masz wersje : $teraz" 'DarkGray'
Pisz "      wroci wersja      : $wroci" 'White'
Pisz ''
Pisz '      Dane i dokumenty zostaja nietkniete. Cofa sie sam program.' 'DarkGray'
Pisz ''
if ((Read-Host '  Wpisz TAK, zeby cofnac') -ne 'TAK') {
    Pisz '  Przerwane. Nic nie zostalo zmienione.' 'DarkGray'
    exit 0
}

try {
    Pisz ''
    Pisz '  Zatrzymuje program...' 'DarkGray'
    if (Test-Path -LiteralPath $SkryptStopu) {
        & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptStopu
    }

    # Zamiana przez trzeci katalog, bo Rename-Item nie umie zamienic dwoch
    # nazw naraz, a polowiczna zamiana zostawilaby instalacje bez "program".
    if (Test-Path -LiteralPath $KatalogTymczasowy) {
        Remove-Item -LiteralPath $KatalogTymczasowy -Recurse -Force
    }
    Rename-Item -LiteralPath $KatalogProgramu -NewName 'program-zamiana'
    Rename-Item -LiteralPath $KatalogPoprzedni -NewName 'program'
    Rename-Item -LiteralPath $KatalogTymczasowy -NewName 'program-poprzednia'

    Add-Content -LiteralPath $HistoriaWersji -Encoding UTF8 -Value `
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  COFNIETO $teraz -> $wroci"

    Pisz ''
    Pisz "  Gotowe. Program ma z powrotem wersje $wroci." 'Green'
    Pisz ''
    Pisz '  Uruchom go jak zwykle, skrotem z pulpitu.' 'DarkGray'
    Pisz '  Gdyby zachowywal sie dziwnie -- zadzwon, baza zostala nowsza.' 'DarkGray'
}
catch {
    Pisz ''
    Pisz "  BLAD: $($_.Exception.Message)" 'Red'
    Pisz '  Sprawdz, czy program jest zamkniety, i sprobuj jeszcze raz.' 'Yellow'
}

Pisz ''
Read-Host '  Nacisnij Enter, zeby zamknac'
