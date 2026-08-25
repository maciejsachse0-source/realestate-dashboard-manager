/**
 * Czytelne nazwy kluczy technicznych.
 *
 * Klucz `czynsz_podstawowy` jest dla bazy i API. Uzytkownik czyta "czynsz".
 */

const NAZWY_POL: Record<string, string> = {
  najemca: 'najemca',
  powierzchnia: 'powierzchnia',
  data_przekazania: 'data przekazania',
  data_zakonczenia: 'data zakończenia',
  czynsz_podstawowy: 'czynsz',
  terminy_platnosci: 'terminy płatności',
  status_kaucji: 'kaucja',
  status_polisy: 'polisa',
}

export function czytelnaNazwaPola(klucz: string): string {
  return NAZWY_POL[klucz] ?? klucz.replace(/_/g, ' ')
}
