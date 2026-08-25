/**
 * Typy odpowiedzi API.
 *
 * Pisane ręcznie do czasu, aż `openapi-typescript` zacznie działać z TypeScript 6
 * (ADR 001). Wtedy ten plik znika i typy są generowane z `/api/openapi.json`.
 *
 * Kwoty są tu `string`, nie `number`. To nie jest niedopatrzenie: JSON nie ma
 * typu dziesiętnego, a `number` po drodze gubi grosze. Front ich nie liczy.
 */

export type RolaUzytkownika = 'podglad' | 'operator' | 'zarzadca' | 'administrator'

export type StatusLokalu = 'wolny' | 'wynajety' | 'w_trakcie_wydania'

export type TypLokalu = 'handlowy' | 'biurowy' | 'magazyn' | 'miejsce_postojowe' | 'inny'

export type StatusUmowy = 'przygotowanie' | 'aktywna' | 'wypowiedziana' | 'zakonczona'

export type WagaZdarzenia = 'informacja' | 'ostrzezenie' | 'krytyczne'

export type StatusZdarzenia = 'otwarte' | 'obsluzone' | 'odroczone'

export type StatusWeryfikacji =
  | 'zaproponowana'
  | 'zatwierdzona'
  | 'poprawiona'
  | 'odrzucona'
  | 'niejednoznaczna'

export interface Profil {
  id: number
  login: string
  imie_nazwisko: string
  rola: RolaUzytkownika
  wymaga_zmiany_hasla: boolean
  ostatnie_logowanie: string | null
}

export interface Strona<T> {
  pozycje: T[]
  wszystkich: number
  limit: number
  offset: number
}

export interface Budynek {
  id: number
  nazwa: string
  adres: string | null
  aktywny: boolean
  uwagi: string | null
  wersja: number
}

export interface LokalNaLiscie {
  lokal_id: number
  budynek_id: number
  budynek_nazwa: string
  oznaczenie: string
  typ: TypLokalu
  status_lokalu: StatusLokalu
  powierzchnia_ewidencyjna: string | null

  okres_najmu_id: number | null
  najemca_id: number | null
  najemca_nazwa: string | null
  status_umowy: StatusUmowy | null
  data_przekazania: string | null
  data_zakonczenia: string | null
  /** Powód, dla którego daty nie da się ustalić. Decyzja D5: brak to informacja. */
  powod_braku_daty_zakonczenia: string | null

  czynsz: string | null
  czynsz_waluta: string | null
  czynsz_rodzaj: string | null
  waloryzacja_podlega: boolean | null

  kompletnosc_procent: number | null
  brakujace_pola: string[]
  zdarzen_otwartych: number
}

export interface WartoscStanu {
  klucz: string
  typ: string
  wartosc: string
  waluta: string | null
  rodzaj_kwoty: string | null
  stawka_vat: string | null
  obowiazuje_od: string
  obowiazuje_do: string | null
  status_weryfikacji: StatusWeryfikacji
  dokument_zrodlowy_id: number | null
  zrodlo_strona: number | null
  zrodlo_paragraf: string | null
}

export interface StanNaDzien {
  lokal_id: number
  okres_najmu_id: number | null
  na_dzien: string
  parametry: Record<string, WartoscStanu>
  brakujace_pola: string[]
  kompletnosc_procent: number
  data_zakonczenia: string | null
  powod_braku_daty_zakonczenia: string | null
}

export interface Zdarzenie {
  id: number
  typ: string
  encja_typ: string
  encja_id: number
  lokal_id: number | null
  data_zdarzenia: string
  waga: WagaZdarzenia
  status: StatusZdarzenia
  tresc: string
  przypisany_uzytkownik_id: number | null
  odroczone_do: string | null
  obsluzone_dnia: string | null
  notatka: string | null
  wersja: number
}

/** Filtry listy lokali. Odpowiadają parametrom zapytania endpointu. */
export interface FiltryLokali {
  budynek_id?: number
  status_lokalu?: StatusLokalu
  typ?: TypLokalu
  status_umowy?: StatusUmowy
  koniec_od?: string
  koniec_do?: string
  waloryzacja?: boolean
  niekompletne?: boolean
  szukaj?: string
  sortuj?: string
  malejaco?: boolean
  limit?: number
  offset?: number
}
