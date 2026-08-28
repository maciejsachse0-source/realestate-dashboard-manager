/**
 * Jedyne miejsce formatujace liczby, kwoty i daty w interfejsie.
 *
 * Plan, sekcja 1.2 punkt J: przecinek dziesietny, spacja jako separator tysiecy,
 * daty DD.MM.RRRR. Wymuszone przez wspolna funkcje, nie ad hoc w komponentach.
 *
 * Zasada twarda: front NIE liczy niczego na pieniadzach. Te funkcje tylko
 * wyswietlaja to, co przyszlo z API.
 */

const LOCALE = 'pl-PL'

/**
 * useGrouping: 'always' jest konieczne.
 * CLDR dla polskiego uzywa domyslnie trybu 'min2', wiec 1234,56 zl zostaloby
 * bez spacji, a dopiero 12 345,67 zl ja dostaje. Plan (sekcja 1.2 punkt J)
 * wymaga separatora tysiecy zawsze, takze przy czterech cyfrach.
 */
const GRUPOWANIE = { useGrouping: 'always' } as const

/** Kwota jako tekst, np. "1 234,56 zl". Wejscie to string z API (Decimal), nie number. */
export function formatujKwote(wartosc: string | number, waluta = 'PLN'): string {
  const liczba = typeof wartosc === 'string' ? Number(wartosc) : wartosc
  if (!Number.isFinite(liczba)) return '—'
  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: waluta,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...GRUPOWANIE,
  }).format(liczba)
}

/** Powierzchnia w metrach kwadratowych, np. "128,50 m²". */
export function formatujPowierzchnie(m2: string | number): string {
  const liczba = typeof m2 === 'string' ? Number(m2) : m2
  if (!Number.isFinite(liczba)) return '—'
  return `${new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...GRUPOWANIE,
  }).format(liczba)} m²`
}

/**
 * Data biznesowa w formacie DD.MM.RRRR.
 *
 * Wejscie to "RRRR-MM-DD" z API. Parsujemy recznie, bo new Date('2027-03-01')
 * to polnoc UTC, ktora w Europe/Warsaw potrafi cofnac sie o dzien.
 * To jest ten blad o jeden dzien z sekcji 1.1 punkt D planu.
 */
export function formatujDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const dopasowanie = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!dopasowanie) return '—'
  const [, rok, miesiac, dzien] = dopasowanie
  return `${dzien}.${miesiac}.${rok}`
}

/**
 * Kwota ze znakiem, np. "+351,50 zl" albo "-250,00 zl".
 *
 * Osobna funkcja, bo znak "+" doklejany w komponencie daje przy deflacji
 * "+-250,00 zl". Wskaznik ujemny jest dopuszczalny, wiec ten przypadek
 * nie jest teoretyczny.
 */
export function formatujRoznice(wartosc: string | number, waluta = 'PLN'): string {
  const liczba = typeof wartosc === 'string' ? Number(wartosc) : wartosc
  if (!Number.isFinite(liczba)) return BRAK_DANYCH
  const tekst = formatujKwote(liczba, waluta)
  return liczba > 0 ? `+${tekst}` : tekst
}

/** Procent, np. "3,70%". Wejscie to string z API (Decimal), nie number. */
export function formatujProcent(wartosc: string | number): string {
  const liczba = typeof wartosc === 'string' ? Number(wartosc) : wartosc
  if (!Number.isFinite(liczba)) return BRAK_DANYCH
  return `${new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...GRUPOWANIE,
  }).format(liczba)}%`
}

/** Brak danych to informacja, nie pusta komorka (koncepcja, decyzja D5). */
export const BRAK_DANYCH = '—'

/**
 * Ile zostalo do terminu, slowami: "za 12 dni", "dzis", "8 dni po terminie".
 *
 * Liczbe dni podaje API (`dni_do_terminu`) -- tutaj jest wylacznie ubranie jej
 * w slowa. Zero znaczy "dzis", a nie "brak danych", dlatego `null` i zero
 * musza dawac rozne wyniki.
 *
 * Polska liczba mnoga "dnia" jest tu prosta: wyjatkiem jest tylko jedynka.
 */
export function opisTerminu(dni: number | null | undefined): string {
  if (dni === null || dni === undefined || !Number.isFinite(dni)) return BRAK_DANYCH
  if (dni === 0) return 'dziś'
  if (dni === 1) return 'jutro'
  if (dni === -1) return 'wczoraj, po terminie'
  if (dni > 0) return `za ${dni} dni`
  return `${Math.abs(dni)} dni po terminie`
}

/**
 * Rozmiar pliku, np. "245 kB". Zaokraglamy w gore skali, bo przy liscie
 * dokumentow chodzi o rzad wielkosci, a nie o dokladna liczbe bajtow.
 */
export function formatujRozmiar(bajty: number | null | undefined): string {
  if (bajty === null || bajty === undefined || !Number.isFinite(bajty)) return BRAK_DANYCH
  if (bajty < 1024) return `${bajty} B`
  if (bajty < 1024 * 1024) return `${Math.round(bajty / 1024)} kB`
  return `${(bajty / 1024 / 1024).toFixed(1)} MB`
}
