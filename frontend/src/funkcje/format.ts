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

/** Brak danych to informacja, nie pusta komorka (koncepcja, decyzja D5). */
export const BRAK_DANYCH = '—'
