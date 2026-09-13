<#
.SYNOPSIS
    Kopia zapasowa: zrzut bazy plus dokumenty, poza ten komputer.

.DESCRIPTION
    Bez tego skryptu awaria dysku kasuje wszystko naraz. Dokumenty wskazane
    na dysku nie sa kopiowane do programu, tylko linkowane (ADR 008), wiec
    sama kopia bazy jest bezuzyteczna: zostalyby sciezki do plikow, ktorych
    juz nie ma. Dlatego kopiujemy jedno i drugie.

    Kopiowane sa trzy rzeczy:
      1. zrzut bazy (pg_dump -F c)
      2. katalog dokumentow wgranych przez program
      3. katalog z dokumentami na dysku (ten z ekranu "Dokumenty z dysku")

    Katalog docelowy bierzemy z KATALOG_KOPII w .env. Pusty znaczy, ze nikt
    go nie ustawil -- konczymy wtedy bledem, a nie cisza. Kopia, o ktorej
    nikt nie wie, ze sie nie robi, jest gorsza niz jej brak.

.PARAMETER Cel
    Katalog docelowy. Bez tego bierzemy KATALOG_KOPII z .env.
#>
param([string]$Cel)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$SkryptBazy = Join-Path $PSScriptRoot 'lokalny-postgres.ps1'
$IleZrzutowTrzymamy = 7

function Zapisz-Stan {
    <#
        Zapisuje wynik ostatniej proby LOKALNIE, w katalogu danych. Celowo nie
        w katalogu kopii: gdy pendrive'a nie ma w porcie, to wlasnie tam nie da
        sie nic zapisac, a to jest ten moment, o ktorym trzeba powiedziec.

        Czyta to uruchom.ps1 i krzyczy przy starcie programu, gdy kopii dawno
        nie bylo. Zadanie z Harmonogramu chodzi w ukrytym oknie -- bez tego
        pliku nikt nigdy nie zauwazy, ze kopie przestaly sie robic.
    #>
    param([Parameter(Mandatory)] [bool]$Udana, [string]$Komunikat = '')

    $plik = Join-Path (Katalog-Danych) 'stan-kopii.txt'
    $tresc = @"
data     = $(Get-Date -Format 'yyyy-MM-dd HH:mm')
wynik    = $(if ($Udana) { 'OK' } else { 'BLAD' })
komunikat= $Komunikat
"@
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $plik) | Out-Null
    Set-Content -LiteralPath $plik -Value $tresc -Encoding UTF8
}

function Katalog-Skanu-Z-Bazy {
    <#
        Katalog z dokumentami uzytkownika mieszka w bazie, nie w .env --
        ustawia go czlowiek w programie i baza wygrywa z plikiem.
        Gdy bazy nie da sie zapytac, wracamy do wartosci z .env.
    #>
    param($Konfiguracja)
    $psql = Join-Path (Katalog-Silnika) 'pgsql\bin\psql.exe'
    if (Test-Path -LiteralPath $psql) {
        $env:PGPASSWORD = 'najem'
        try {
            $wartosc = & $psql -h 127.0.0.1 -p 5434 -U najem -d najem -tAc `
                "SELECT wartosc FROM ustawienie_systemu WHERE klucz = 'katalog_skanu' AND usunieto_dnia IS NULL"
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($wartosc)) {
                return $wartosc.Trim()
            }
        }
        catch { }
        finally { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }
    }
    return $Konfiguracja['KATALOG_SKANU']
}

function Skopiuj-Drzewo {
    param([string]$Zrodlo, [string]$Cel, [string]$Opis)

    if ([string]::IsNullOrWhiteSpace($Zrodlo) -or -not (Test-Path -LiteralPath $Zrodlo)) {
        Pisz "  - $Opis : pomijam, nie ma takiego katalogu" 'DarkGray'
        return
    }
    & robocopy $Zrodlo $Cel /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    # robocopy zwraca mape bitowa, nie kod bledu: 0-7 to sukces (0 = bez zmian,
    # 1 = skopiowano pliki, 2 = dodatkowe pliki w celu, ...). Dopiero 8 w gore
    # to prawdziwy problem. Bez tego sprawdzenia PowerShell uznalby udana
    # kopie za blad przy pierwszym skopiowanym pliku.
    if ($LASTEXITCODE -ge 8) { throw "Kopiowanie '$Opis' nie powiodlo sie (robocopy $LASTEXITCODE)." }
    Pisz "  - $Opis : skopiowane" 'Green'
}

Pisz ''
Pisz "  Kopia zapasowa $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 'White'
Pisz ''

$konfiguracja = Czytaj-Env
if ([string]::IsNullOrWhiteSpace($Cel)) { $Cel = $konfiguracja['KATALOG_KOPII'] }

if ([string]::IsNullOrWhiteSpace($Cel)) {
    Pisz '  KOPIA ZAPASOWA NIE JEST USTAWIONA.' 'Red'
    Pisz ''
    Pisz '  W pliku .env nie ma KATALOG_KOPII, wiec nie ma dokad kopiowac.' 'DarkGray'
    Pisz '  Dopoki to sie nie zmieni, awaria dysku kasuje baze i dokumenty naraz.' 'DarkGray'
    Pisz ''
    Zapisz-Stan -Udana $false -Komunikat 'KATALOG_KOPII nie jest ustawiony w .env'
    exit 1
}

try {
New-Item -ItemType Directory -Force -Path $Cel | Out-Null

# --------------------------------------------------------------- baza
# Baza moze byc zatrzymana (kopia chodzi z harmonogramu, program nie musi
# dzialac). Startujemy ja wtedy na czas zrzutu i zostawiamy tak, jak byla.
$bazaChodzila = $true
& powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy status
if ($LASTEXITCODE -ne 0) {
    $bazaChodzila = $false
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy start
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie uruchomic bazy danych do zrzutu.' }
}

try {
    $katalogZrzutow = Katalog-Kopii
    New-Item -ItemType Directory -Force -Path $katalogZrzutow | Out-Null
    & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy kopia
    if ($LASTEXITCODE -ne 0) { throw 'pg_dump nie powiodl sie.' }

    Get-ChildItem -Path $katalogZrzutow -Filter 'najem-*.dump' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $IleZrzutowTrzymamy |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $katalogSkanu = Katalog-Skanu-Z-Bazy $konfiguracja
}
finally {
    if (-not $bazaChodzila) {
        & powershell -ExecutionPolicy Bypass -NoProfile -File $SkryptBazy stop
    }
}

# ------------------------------------------------------------ na zewnatrz
Pisz ''
Pisz "  Kopiuje do: $Cel" 'DarkGray'
Skopiuj-Drzewo $katalogZrzutow (Join-Path $Cel 'baza') 'zrzuty bazy'
Skopiuj-Drzewo $konfiguracja['KATALOG_DOKUMENTOW'] (Join-Path $Cel 'dokumenty-programu') 'dokumenty wgrane w programie'
Skopiuj-Drzewo $katalogSkanu (Join-Path $Cel 'dokumenty-na-dysku') 'dokumenty z dysku'

Set-Content -LiteralPath (Join-Path $Cel 'ostatnia-kopia.txt') -Encoding UTF8 `
    -Value "Ostatnia udana kopia: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"

    Zapisz-Stan -Udana $true
    Pisz ''
    Pisz '  Gotowe.' 'Green'
    Pisz ''
}
catch {
    # Najczestszy powod: pendrive wyjety z portu albo zmieniona litera dysku.
    Zapisz-Stan -Udana $false -Komunikat $_.Exception.Message
    Pisz ''
    Pisz '  KOPIA ZAPASOWA SIE NIE UDALA.' 'Red'
    Pisz "  $($_.Exception.Message)" 'DarkGray'
    Pisz ''
    Pisz "  Sprawdz, czy dysk kopii jest podlaczony: $Cel" 'Yellow'
    Pisz ''
    exit 1
}
