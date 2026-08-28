import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Kartoteka from './Kartoteka'

const PROFIL = {
  id: 1,
  login: 'jan',
  imie_nazwisko: 'Jan Sachse',
  rola: 'administrator',
  wymaga_zmiany_hasla: false,
}

const BUDYNKI = {
  pozycje: [
    { id: 1, nazwa: 'Rycerska', adres: 'ul. Rycerska 18A', aktywny: true, uwagi: null, wersja: 1 },
    { id: 2, nazwa: 'Nowatorów', adres: null, aktywny: false, uwagi: null, wersja: 1 },
  ],
  wszystkich: 2,
  limit: 500,
  offset: 0,
}

function lokal(id: number, budynekId: number, oznaczenie: string) {
  return {
    lokal_id: id,
    budynek_id: budynekId,
    budynek_nazwa: budynekId === 1 ? 'Rycerska' : 'Nowatorów',
    oznaczenie,
    typ: 'handlowy',
    status_lokalu: 'wynajety',
    powierzchnia_ewidencyjna: '124.50',
    okres_najmu_id: 500 + id,
    najemca_id: 7,
    najemca_nazwa: 'Piekarnia Złoty Kłos',
    status_umowy: 'aktywna',
    data_przekazania: '2026-02-01',
    data_zakonczenia: '2028-01-31',
    powod_braku_daty_zakonczenia: null,
    czynsz: '9500.00',
    czynsz_waluta: 'PLN',
    czynsz_rodzaj: 'netto',
    waloryzacja_podlega: true,
    kompletnosc_procent: 80,
    brakujace_pola: [],
    zdarzen_otwartych: 0,
  }
}

// Budynek 2 celowo bez lokali: ma być widoczny mimo pustej grupy.
const LOKALE = {
  pozycje: [lokal(11, 1, '2'), lokal(12, 1, '10')],
  wszystkich: 2,
  limit: 500,
  offset: 0,
}

const NAJEMCY = { pozycje: [], wszystkich: 0, limit: 500, offset: 0 }

function odpowiedz(dane: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(dane), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

beforeEach(() => {
  vi.stubGlobal('fetch', (adres: string) => {
    if (adres.includes('/auth/ja')) return odpowiedz(PROFIL)
    if (adres.includes('/budynki')) return odpowiedz(BUDYNKI)
    if (adres.includes('/lokale')) return odpowiedz(LOKALE)
    if (adres.includes('/najemcy')) return odpowiedz(NAJEMCY)
    throw new Error(`Nieoczekiwane żądanie: ${adres}`)
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function pokaz() {
  const klient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={klient}>
      <MemoryRouter>
        <Kartoteka />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Kartoteka: jedna tabela pogrupowana budynkami', () => {
  it('budynek jest nagłówkiem sekcji, a nie osobną zakładką', async () => {
    pokaz()
    const naglowek = (await screen.findByText('Rycerska')).closest('tr')!
    expect(within(naglowek).getByText('ul. Rycerska 18A')).toBeInTheDocument()
    expect(within(naglowek).getByText('lokali: 2')).toBeInTheDocument()
  })

  it('nagłówek budynku odcina się od wierszy lokali', async () => {
    pokaz()
    // Bez wyróżnienia długa lista zlewa się w jedno i nie widać, gdzie
    // kończy się jeden budynek, a zaczyna następny.
    const komorka = (await screen.findByText('Rycerska')).closest('td')!
    const wiersz = komorka.closest('tr')!

    expect(wiersz.className).toMatch(/bg-/)
    expect(wiersz.className).toMatch(/border-y-2/)
    expect(screen.getByText('Rycerska').className).toMatch(/uppercase/)
  })

  it('budynek bez lokali też jest widoczny', async () => {
    pokaz()
    // Inaczej wygląda na nieistniejący i nikt nie doda do niego lokalu.
    const naglowek = (await screen.findByText('Nowatorów')).closest('tr')!
    expect(within(naglowek).getByText('bez lokali')).toBeInTheDocument()
    expect(within(naglowek).getByText('nieaktywny')).toBeInTheDocument()
  })

  it('lokale sortuje po ludzku: 2 przed 10', async () => {
    pokaz()
    await screen.findByText('Rycerska')
    const oznaczenia = screen
      .getAllByRole('cell')
      .map((k) => k.textContent)
      .filter((t) => t === '2' || t === '10')
    expect(oznaczenia).toEqual(['2', '10'])
  })
})
