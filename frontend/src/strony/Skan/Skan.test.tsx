import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Skan from './Skan'

const LOKALE = {
  pozycje: [
    {
      lokal_id: 11,
      budynek_id: 1,
      budynek_nazwa: 'Rycerska',
      oznaczenie: '12',
      typ: 'handlowy',
      status_lokalu: 'wynajety',
      powierzchnia_ewidencyjna: '124.50',
      okres_najmu_id: 501,
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
    },
  ],
  wszystkich: 1,
  limit: 500,
  offset: 0,
}

/** Drzewo z dysku: jeden budynek, jeden folder, trzy pliki w trzech stanach. */
const SKAN = {
  katalog: 'C:/Users/Dorota/Documents/Budynki',
  dostepny: true,
  komunikat: null,
  nowych: 2,
  obcietych: 0,
  budynki: [
    {
      nazwa_folderu: 'Rycerska',
      budynek_id: 1,
      budynek_nazwa: 'Rycerska',
      foldery: [
        {
          nazwa: 'Lokal nr 12_Piekarnia',
          sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia',
          powiazanie_id: null,
          okres_najmu_id: null,
          opis_umowy: null,
          nowych: 2,
          pliki: [
            {
              nazwa: 'Umowa najmu.pdf',
              sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia/Umowa najmu.pdf',
              rozmiar_bajty: 245_000,
              status: 'nowy',
              typ_proponowany: 'umowa',
              numer_proponowany: null,
              dokument_id: null,
              pominiecie_id: null,
            },
            {
              nazwa: 'skan0012.pdf',
              sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia/skan0012.pdf',
              rozmiar_bajty: 12_000,
              status: 'nowy',
              typ_proponowany: null,
              numer_proponowany: null,
              dokument_id: null,
              pominiecie_id: null,
            },
            {
              nazwa: 'Aneks nr 1.pdf',
              sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia/Aneks nr 1.pdf',
              rozmiar_bajty: 30_000,
              status: 'w_systemie',
              typ_proponowany: 'aneks',
              numer_proponowany: '1',
              dokument_id: 88,
              pominiecie_id: null,
            },
          ],
        },
      ],
    },
  ],
}

let zaimportowane: Record<string, unknown> | null = null
let powiazane: Record<string, unknown> | null = null
let pominiete: Record<string, unknown> | null = null

function odpowiedz(dane: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(dane), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

beforeEach(() => {
  zaimportowane = null
  powiazane = null
  pominiete = null
  vi.stubGlobal('fetch', (adres: string, opcje?: RequestInit) => {
    const tresc = opcje?.body ? (JSON.parse(String(opcje.body)) as Record<string, unknown>) : {}

    if (adres.includes('/skan/importuj')) {
      zaimportowane = tresc
      return odpowiedz({ id: 99 }, 201)
    }
    if (adres.includes('/skan/powiazania')) {
      powiazane = tresc
      return odpowiedz({ id: 5 }, 201)
    }
    if (adres.includes('/skan/pominiecia')) {
      pominiete = tresc
      return odpowiedz({ id: 6 }, 201)
    }
    if (adres.includes('/skan/sprawdz')) {
      return odpowiedz({ katalog: SKAN.katalog, sprawdzonych: 1, zerwane: [] })
    }
    if (adres.includes('/skan')) return odpowiedz(SKAN)
    if (adres.includes('/lokale')) return odpowiedz(LOKALE)
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
      <Skan />
    </QueryClientProvider>,
  )
}

describe('Ekran dokumentów z dysku', () => {
  it('pokazuje znalezione pliki i podpowiada rodzaj z nazwy', async () => {
    pokaz()

    const wiersz = (await screen.findByText('Umowa najmu.pdf')).closest('li')!
    const rodzaj = within(wiersz).getByLabelText(/Rodzaj dokumentu/)
    expect(rodzaj).toHaveValue('umowa')
  })

  it('nie zgaduje rodzaju, gdy nazwa pliku nic nie mówi', async () => {
    pokaz()

    const wiersz = (await screen.findByText('skan0012.pdf')).closest('li')!
    expect(within(wiersz).getByLabelText(/Rodzaj dokumentu/)).toHaveValue('')
    expect(within(wiersz).getByText(/Wybierz rodzaj sam/)).toBeInTheDocument()
  })

  it('nie pozwala dodać dokumentu, dopóki folder nie jest powiązany z umową', async () => {
    pokaz()

    const wiersz = (await screen.findByText('Umowa najmu.pdf')).closest('li')!
    expect(within(wiersz).getByRole('button', { name: 'Dodaj' })).toBeDisabled()
    expect(within(wiersz).getByText(/Najpierw powiąż ten folder z umową/)).toBeInTheDocument()
  })

  it('paruje folder z umową wybraną przez człowieka', async () => {
    pokaz()
    const uzytkownik = userEvent.setup()

    const wybor = await screen.findByLabelText(/Umowa dla folderu/)
    // Lista umow przychodzi osobnym zapytaniem, wiec czekamy na nia,
    // zanim cokolwiek wybierzemy.
    await screen.findByRole('option', { name: /Piekarnia/ })
    await uzytkownik.selectOptions(wybor, '501')
    await uzytkownik.click(screen.getByRole('button', { name: 'Powiąż' }))

    expect(powiazane).toEqual({
      sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia',
      okres_najmu_id: 501,
    })
  })

  it('plik już wczytany pokazuje się jako obecny w systemie, bez formularza', async () => {
    pokaz()

    const wiersz = (await screen.findByText('Aneks nr 1.pdf')).closest('li')!
    expect(within(wiersz).getByText('w systemie')).toBeInTheDocument()
    expect(within(wiersz).queryByRole('button', { name: 'Dodaj' })).not.toBeInTheDocument()
  })

  it('pomija plik, o który człowiek nie prosił', async () => {
    pokaz()
    const uzytkownik = userEvent.setup()

    const wiersz = (await screen.findByText('skan0012.pdf')).closest('li')!
    await uzytkownik.click(within(wiersz).getByRole('button', { name: 'Pomiń' }))

    expect(pominiete).toEqual({
      sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia/skan0012.pdf',
    })
  })

  it('pusta data zostaje pusta, a nie podstawia dzisiejszej', async () => {
    // Decyzja D5: brak danych to informacja. Do E9 system nie czyta treści
    // dokumentów, więc nie ma skąd wziąć daty.
    const zSparowanymFolderem = {
      ...SKAN,
      budynki: [
        {
          ...SKAN.budynki[0],
          foldery: [
            {
              ...SKAN.budynki[0].foldery[0],
              powiazanie_id: 5,
              okres_najmu_id: 501,
              opis_umowy: '12 - Piekarnia Złoty Kłos',
            },
          ],
        },
      ],
    }
    vi.stubGlobal('fetch', (adres: string, opcje?: RequestInit) => {
      const tresc = opcje?.body ? (JSON.parse(String(opcje.body)) as Record<string, unknown>) : {}
      if (adres.includes('/skan/importuj')) {
        zaimportowane = tresc
        return odpowiedz({ id: 99 }, 201)
      }
      if (adres.includes('/skan')) return odpowiedz(zSparowanymFolderem)
      if (adres.includes('/lokale')) return odpowiedz(LOKALE)
      throw new Error(`Nieoczekiwane żądanie: ${adres}`)
    })

    pokaz()
    const uzytkownik = userEvent.setup()

    const wiersz = (await screen.findByText('Umowa najmu.pdf')).closest('li')!
    await uzytkownik.click(within(wiersz).getByRole('button', { name: 'Dodaj' }))

    expect(zaimportowane).toMatchObject({
      sciezka_wzgledna: 'Rycerska/Umowy najmu/Lokal nr 12_Piekarnia/Umowa najmu.pdf',
      typ: 'umowa',
      okres_najmu_id: 501,
      data_dokumentu: null,
    })
  })

  it('mówi, co ustawić, gdy katalog nie jest wskazany', async () => {
    vi.stubGlobal('fetch', (adres: string) => {
      if (adres.includes('/skan'))
        return odpowiedz({
          katalog: null,
          dostepny: false,
          komunikat: 'Nie wskazano katalogu z dokumentami. Ustaw KATALOG_SKANU w pliku .env.',
          nowych: 0,
          obcietych: 0,
          budynki: [],
        })
      if (adres.includes('/lokale')) return odpowiedz(LOKALE)
      throw new Error(`Nieoczekiwane żądanie: ${adres}`)
    })

    pokaz()

    expect(await screen.findByText(/KATALOG_SKANU/)).toBeInTheDocument()
  })
})
