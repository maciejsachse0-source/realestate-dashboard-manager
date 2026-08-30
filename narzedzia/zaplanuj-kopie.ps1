<#
.SYNOPSIS
    Rejestruje codzienna kopie zapasowa w Harmonogramie zadan Windows.

.DESCRIPTION
    Zadanie chodzi na koncie zalogowanego uzytkownika i nie wymaga uprawnien
    administratora. Odpala sie w poludnie, bo o tej porze komputer w biurze
    na pewno jest wlaczony -- kopia o trzeciej w nocy nie wykonalaby sie ani
    razu. Gdy komputer byl wylaczony o umowionej godzinie, zadanie dogania
    sie przy najblizszym wlaczeniu (StartWhenAvailable).

    Uruchomienie ponowne nadpisuje istniejace zadanie, wiec skrypt jest
    idempotentny.

.PARAMETER Godzina
    Pora uruchomienia, domyslnie 12:30.
#>
param([string]$Godzina = '12:30')

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'sciezki.ps1')

$NazwaZadania = 'System Najmu - kopia zapasowa'
$SkryptKopii = Join-Path $PSScriptRoot 'kopia-zapasowa.ps1'
$Instalacja = Katalog-Instalacji

function Pisz($tekst, $kolor = 'Gray') { Write-Host $tekst -ForegroundColor $kolor }

if (-not $Instalacja) {
    Pisz '      Pomijam zadanie kopii: to nie jest instalacja, tylko repozytorium.' 'DarkGray'
    exit 0
}

# Zadanie musi znac katalog instalacji, bo bez NAJEM_KATALOG_INSTALACJI
# sciezki.ps1 wskazalyby na uklad deweloperski. Przekazujemy go wprost
# w poleceniu, zamiast liczyc na zmienna srodowiskowa uzytkownika, ktorej
# Harmonogram nie musi widziec.
$polecenie = "`$env:NAJEM_KATALOG_INSTALACJI='$Instalacja'; & '$SkryptKopii'"

try {
    $akcja = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -Command `"$polecenie`""
    $wyzwalacz = New-ScheduledTaskTrigger -Daily -At $Godzina
    $ustawienia = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    Register-ScheduledTask -TaskName $NazwaZadania -Action $akcja -Trigger $wyzwalacz `
        -Settings $ustawienia -Description 'Zrzut bazy i kopia dokumentow poza ten komputer.' `
        -Force | Out-Null

    Pisz "      Kopia zapasowa: codziennie o $Godzina" 'DarkGray'
}
catch {
    # Brak zadania to nie powod, zeby przerwac instalacje -- program bedzie
    # dzialal. Ale musi to zostac powiedziane glosno, bo to jedyna ochrona
    # przed awaria dysku.
    Pisz '' 'Red'
    Pisz '      NIE UDALO SIE ZAPLANOWAC KOPII ZAPASOWEJ.' 'Red'
    Pisz "      $($_.Exception.Message)" 'DarkGray'
    Pisz '      Program bedzie dzialal, ale kopie trzeba robic recznie:' 'Yellow'
    Pisz "      $SkryptKopii" 'DarkGray'
    Pisz ''
}
