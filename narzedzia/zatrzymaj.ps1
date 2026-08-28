<#
.SYNOPSIS
    Zatrzymuje program i baze danych.

.DESCRIPTION
    Zamkniecie okna krzyzykiem nie zawsze ubija proces aplikacji. Zostaje wtedy
    zajety port 8010, a kolejne uruchomienie odbija sie od niego i wyglada to
    tak, jakby skrot nie dzialal.

.PARAMETER TylkoAplikacja
    Zatrzymuje sam program, baze zostawia. Uzywa tego uruchom.ps1, ktory zaraz
    potem startuje aplikacje od nowa na tej samej bazie.
#>
param([switch]$TylkoAplikacja)

$ErrorActionPreference = 'Stop'
$Port = 8010

function Zatrzymaj-Aplikacje {
    $polaczenia = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($polaczenia.Count -eq 0) {
        Write-Host "  Program nie dzialal (port $Port byl wolny)." -ForegroundColor DarkGray
        return $true
    }

    foreach ($idProcesu in ($polaczenia.OwningProcess | Sort-Object -Unique)) {
        $proces = Get-Process -Id $idProcesu -ErrorAction SilentlyContinue
        if (-not $proces) { continue }

        # Port 8010 nalezy do tego programu, ale gdyby zajal go ktos inny,
        # ubicie cudzego procesu byloby gorsze niz komunikat o bledzie.
        if ($proces.ProcessName -notmatch '^(python|pythonw|uv|uvicorn)$') {
            Write-Host "  Port $Port zajmuje '$($proces.ProcessName)' (PID $idProcesu)." -ForegroundColor Red
            Write-Host '  To nie jest ten program. Nie zatrzymuje go.' -ForegroundColor Red
            return $false
        }

        Stop-Process -Id $idProcesu -Force -ErrorAction SilentlyContinue
    }

    # Zwolnienie portu nie jest natychmiastowe, wiec czekamy zamiast zgadywac.
    for ($proba = 0; $proba -lt 20; $proba++) {
        Start-Sleep -Milliseconds 500
        if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
            Write-Host '  Program zatrzymany.' -ForegroundColor Green
            return $true
        }
    }

    Write-Host "  Port $Port nadal jest zajety." -ForegroundColor Red
    return $false
}

$udaloSie = Zatrzymaj-Aplikacje

if (-not $TylkoAplikacja) {
    & powershell -ExecutionPolicy Bypass -NoProfile -File (Join-Path $PSScriptRoot 'lokalny-postgres.ps1') stop
}

if ($udaloSie) { exit 0 } else { exit 1 }
