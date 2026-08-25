import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Waloryzacja from './Waloryzacja'

const ROK = new Date().getFullYear()

const PRZEBIEG = {
  rok: ROK,
  wskazniki: { gus_rok_do_roku: '3.70' },
  objete: [
    {
      okres_najmu_id: 1,
      lokal_id: 11,
      oznaczenie_lokalu: 'A/01',
      najemca: 'Piekarnia Złoty Kłos',
      kwota_stara: '9500.00',
      kwota_nowa: '9851.50',
      roznica: '351.50',
      waluta: 'PLN',
      rodzaj_kwoty: 'netto',
      wskaznik_procent: '3.70',
      obowiazuje_od: `${ROK}-01-01`,
      powod_wylaczenia: null,
    },
    {
      okres_najmu_id: 2,
      lokal_id: 12,
      oznaczenie_lokalu: 'A/02',
      najemca: 'Kancelaria Lex',
      kwota_stara: '4321.99',
      kwota_nowa: '4481.90',
      roznica: '159.91',
      waluta: 'PLN',
      rodzaj_kwoty: 'netto',
      wskaznik_procent: '3.70',
      obowiazuje_od: `${ROK}-01-01`,
      powod_wylaczenia: null,
    },
  ],
  wylaczone: [
    {
      okres_najmu_id: 3,
      lokal_id: 13,
      oznaczenie_lokalu: 'A/03',
      najemca: 'Studio Kreska',
      kwota_stara: null,
      kwota_nowa: null,
      roznica: null,
      waluta: null,
      rodzaj_kwoty: null,
      wskaznik_procent: null,
      obowiazuje_od: null,
      powod_wylaczenia: 'Umowa nie podlega waloryzacji.',
    },
  ],
  sumy: [
    { waluta: 'PLN', umow: 2, przed: '13821.99', po: '14333.40', roznica: '511.41' },
  ],
}

/** Sumy, jakie serwer odda dla danego wyboru umów. */
const SUMY_WYBORU: Record<string, unknown> = {
  '1,2': PRZEBIEG.sumy,
  '1': [{ waluta: 'PLN', umow: 1, przed: '9500.00', po: '9851.50', roznica: '351.50' }],
  '2': [{ waluta: 'PLN', umow: 1, przed: '4321.99', po: '4481.90', roznica: '159.91' }],
  '': [],
}

let zatwierdzone: number[] | null = null
let przebiegow = 0
let konflikt = false

function odpowiedz(dane: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(dane), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

beforeEach(() => {
  zatwierdzone = null
  przebiegow = 0
  konflikt = false
  vi.stubGlobal('fetch', (adres: string, opcje?: RequestInit) => {
    const tresc = opcje?.body ? (JSON.parse(String(opcje.body)) as Record<string, never>) : {}

    if (adres.includes('/waloryzacja/wskazniki')) return odpowiedz([])
    if (adres.includes('/waloryzacja/przebieg')) {
      przebiegow += 1
      // Po konflikcie serwer ma już inny stan: A/02 zniknęła z propozycji.
      if (konflikt && przebiegow > 1) {
        return odpowiedz({ ...PRZEBIEG, objete: [PRZEBIEG.objete[0]] })
      }
      return odpowiedz(PRZEBIEG)
    }
    if (adres.includes('/waloryzacja/podsumowanie')) {
      const okresy = (tresc.okresy_najmu ?? []) as number[]
      return odpowiedz(SUMY_WYBORU[[...okresy].sort().join(',')] ?? [])
    }
    if (adres.includes('/waloryzacja/zatwierdz')) {
      if (konflikt) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Odśwież listę propozycji.' }), {
            status: 409,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      zatwierdzone = (tresc.okresy_najmu ?? []) as number[]
      return odpowiedz({ rok: ROK, umow_zwaloryzowanych: zatwierdzone.length, zdarzen_o_wekslach: 1 })
    }
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
      <Waloryzacja />
    </QueryClientProvider>,
  )
}

describe('Ekran waloryzacji', () => {
  it('pokazuje propozycje z kwotami w polskim formacie', async () => {
    pokaz()

    const wiersz = (await screen.findByText('A/01')).closest('tr')!
    expect(within(wiersz).getByText('9 500,00 zł')).toBeInTheDocument()
    expect(within(wiersz).getByText(/9 851,50 zł/)).toBeInTheDocument()
    expect(within(wiersz).getByText('+351,50 zł')).toBeInTheDocument()
    expect(within(wiersz).getByText('01.01.' + ROK)).toBeInTheDocument()
  })

  it('pokazuje wyłączone umowy razem z powodem', async () => {
    pokaz()

    expect(await screen.findByText('A/03')).toBeInTheDocument()
    expect(screen.getByText('Umowa nie podlega waloryzacji.')).toBeInTheDocument()
  })

  it('domyślnie zaznacza wszystko', async () => {
    pokaz()

    await screen.findByText('A/01')
    expect(screen.getByRole('button', { name: /Zatwierdź 2 umowy/ })).toBeEnabled()
  })

  it('odznaczenie umowy zmienia sumę, bo pyta o nią serwer', async () => {
    const uzytkownik = userEvent.setup()
    pokaz()

    await screen.findByText('A/01')
    await waitFor(() => expect(screen.getByText(/Razem PLN \(2 umowy\)/)).toBeInTheDocument())

    await uzytkownik.click(screen.getByRole('checkbox', { name: 'Zatwierdź A/02' }))

    await waitFor(() => expect(screen.getByText(/Razem PLN \(1 umowę\)/)).toBeInTheDocument())

    // Suma liczy już tylko A/01, czyli 9 500,00 zł przed i 9 851,50 zł po.
    const suma = screen.getByText(/Razem PLN \(1 umowę\)/).closest('tr')!
    expect(within(suma).getByText('9 500,00 zł')).toBeInTheDocument()
    expect(within(suma).getByText('9 851,50 zł')).toBeInTheDocument()
    expect(within(suma).getByText('+351,50 zł')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Zatwierdź 1 umowę/ })).toBeInTheDocument()
  })

  it('zatwierdza tylko zaznaczone umowy', async () => {
    const uzytkownik = userEvent.setup()
    pokaz()

    await screen.findByText('A/01')
    await uzytkownik.click(screen.getByRole('checkbox', { name: 'Zatwierdź A/01' }))
    await uzytkownik.click(screen.getByRole('button', { name: /Zatwierdź 1 umowę/ }))

    await waitFor(() => expect(zatwierdzone).toEqual([2]))
  })

  it('po zatwierdzeniu mówi o zdarzeniach o zabezpieczeniach', async () => {
    const uzytkownik = userEvent.setup()
    pokaz()

    await screen.findByText('A/01')
    await uzytkownik.click(screen.getByRole('button', { name: /Zatwierdź 2 umowy/ }))

    expect(await screen.findByText(/Zwaloryzowano 2 umowy/)).toBeInTheDocument()
    expect(screen.getByText(/zabezpieczeniach do przeliczenia/)).toBeInTheDocument()
  })

  it('po konflikcie 409 sam pobiera listę na nowo', async () => {
    const uzytkownik = userEvent.setup()
    konflikt = true
    pokaz()

    await screen.findByText('A/02')

    await uzytkownik.click(screen.getByRole('button', { name: /Zatwierdź 2 umowy/ }))

    expect(await screen.findByText('Odśwież listę propozycji.')).toBeInTheDocument()
    // Serwer każe odświeżyć listę, więc ekran odświeża ją sam. Dowodem jest
    // treść, a nie liczba żądań: A/02 przestaje być widoczna.
    await waitFor(() => expect(screen.queryByText('A/02')).not.toBeInTheDocument())
    expect(screen.getByText('A/01')).toBeInTheDocument()
  })

  it('odznaczenie wszystkiego blokuje zatwierdzenie', async () => {
    const uzytkownik = userEvent.setup()
    pokaz()

    await screen.findByText('A/01')
    await uzytkownik.click(screen.getByRole('checkbox', { name: 'Zaznacz wszystkie' }))

    await waitFor(() =>
      expect(screen.getByText('Nic nie zaznaczono — nie ma czego zatwierdzić.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /Zatwierdź 0 umów/ })).toBeDisabled()
  })
})

describe('Ekran waloryzacji: deflacja', () => {
  const OBNIZKA = {
    ...PRZEBIEG,
    objete: [
      {
        ...PRZEBIEG.objete[0],
        kwota_stara: '10000.00',
        kwota_nowa: '9750.00',
        roznica: '-250.00',
        wskaznik_procent: '-2.50',
      },
    ],
    wylaczone: [],
    sumy: [
      { waluta: 'PLN', umow: 1, przed: '10000.00', po: '9750.00', roznica: '-250.00' },
    ],
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', (adres: string) => {
      if (adres.includes('/waloryzacja/wskazniki')) return odpowiedz([])
      if (adres.includes('/waloryzacja/przebieg')) return odpowiedz(OBNIZKA)
      if (adres.includes('/waloryzacja/podsumowanie')) return odpowiedz(OBNIZKA.sumy)
      throw new Error(`Nieoczekiwane żądanie: ${adres}`)
    })
  })

  it('pokazuje obniżkę jako obniżkę, a nie jako "+-250,00 zł"', async () => {
    pokaz()

    const wiersz = (await screen.findByText('A/01')).closest('tr')!
    const komorka = within(wiersz).getByText(/250,00 zł/)

    expect(komorka.textContent).not.toContain('+')
    expect(komorka.className).toContain('text-red-700')
  })

  it('sumę też pokazuje bez sztucznego plusa', async () => {
    pokaz()

    await screen.findByText('A/01')
    const suma = (await screen.findByText(/Razem PLN/)).closest('tr')!
    const komorka = within(suma).getByText(/250,00 zł/)

    expect(komorka.textContent).not.toContain('+')
    expect(komorka.className).toContain('text-red-700')
  })
})

describe('Ekran waloryzacji: pole roku', () => {
  it('skasowanie roku nie wysyła zapytania z rok=0', async () => {
    const uzytkownik = userEvent.setup()
    const adresy: string[] = []
    vi.stubGlobal('fetch', (adres: string) => {
      adresy.push(adres)
      if (adres.includes('/waloryzacja/wskazniki')) return odpowiedz([])
      if (adres.includes('/waloryzacja/przebieg')) return odpowiedz(PRZEBIEG)
      if (adres.includes('/waloryzacja/podsumowanie')) return odpowiedz(PRZEBIEG.sumy)
      throw new Error(`Nieoczekiwane żądanie: ${adres}`)
    })

    pokaz()
    await screen.findByText('A/01')

    await uzytkownik.clear(screen.getByLabelText('Rok'))

    expect(await screen.findByText('Podaj rok waloryzacji')).toBeInTheDocument()
    expect(adresy.filter((a) => a.includes('rok=0'))).toEqual([])
  })

  it('rok spoza zakresu też nie jest wysyłany', async () => {
    const uzytkownik = userEvent.setup()
    const adresy: string[] = []
    vi.stubGlobal('fetch', (adres: string) => {
      adresy.push(adres)
      if (adres.includes('/waloryzacja/wskazniki')) return odpowiedz([])
      if (adres.includes('/waloryzacja/przebieg')) return odpowiedz(PRZEBIEG)
      if (adres.includes('/waloryzacja/podsumowanie')) return odpowiedz(PRZEBIEG.sumy)
      throw new Error(`Nieoczekiwane żądanie: ${adres}`)
    })

    pokaz()
    await screen.findByText('A/01')

    const pole = screen.getByLabelText('Rok')
    await uzytkownik.clear(pole)
    await uzytkownik.type(pole, '202')

    // Po drodze przez "2", "20" i "202" nie leci ani jedno zapytanie.
    expect(await screen.findByText('Podaj rok waloryzacji')).toBeInTheDocument()
    expect(adresy.filter((a) => /rok=(2|20|202)(&|$)/.test(a))).toEqual([])
  })
})
