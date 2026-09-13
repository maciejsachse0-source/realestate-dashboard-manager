/**
 * Typy odpowiedzi API.
 *
 * Pisane ręcznie do czasu, aż `openapi-typescript` zacznie działać z TypeScript 6
 * (ADR 001). Wtedy ten plik znika i typy są generowane z `/api/openapi.json`.
 *
 * Kwoty są tu `string`, nie `number`. To nie jest niedopatrzenie: JSON nie ma
 * typu dziesiętnego, a `number` po drodze gubi grosze. Front ich nie liczy.
 */

export type StatusLokalu = "wolny" | "wynajety" | "w_trakcie_wydania";

export type TypLokalu =
  "handlowy" | "biurowy" | "magazyn" | "miejsce_postojowe" | "inny";

export type StatusUmowy =
  "przygotowanie" | "aktywna" | "wypowiedziana" | "zakonczona";

export type WagaZdarzenia = "informacja" | "ostrzezenie" | "krytyczne";

export type StatusZdarzenia = "otwarte" | "obsluzone" | "odroczone";

export type StatusWeryfikacji =
  | "zaproponowana"
  | "zatwierdzona"
  | "poprawiona"
  | "odrzucona"
  | "niejednoznaczna";

export interface Strona<T> {
  pozycje: T[];
  wszystkich: number;
  limit: number;
  offset: number;
}

export interface Budynek {
  id: number;
  nazwa: string;
  /** Nazwa katalogu na dysku, gdy różni się od nazwy budynku. */
  nazwa_folderu: string | null;
  adres: string | null;
  aktywny: boolean;
  uwagi: string | null;
  wersja: number;
}

export interface LokalNaLiscie {
  lokal_id: number;
  budynek_id: number;
  budynek_nazwa: string;
  oznaczenie: string;
  typ: TypLokalu;
  status_lokalu: StatusLokalu;
  powierzchnia_ewidencyjna: string | null;

  okres_najmu_id: number | null;
  najemca_id: number | null;
  najemca_nazwa: string | null;
  status_umowy: StatusUmowy | null;
  data_przekazania: string | null;
  data_zakonczenia: string | null;
  /** Powód, dla którego daty nie da się ustalić. Decyzja D5: brak to informacja. */
  powod_braku_daty_zakonczenia: string | null;

  czynsz: string | null;
  czynsz_waluta: string | null;
  czynsz_rodzaj: string | null;
  waloryzacja_podlega: boolean | null;

  kompletnosc_procent: number | null;
  brakujace_pola: string[];
  zdarzen_otwartych: number;
}

export interface WartoscStanu {
  klucz: string;
  typ: string;
  wartosc: string;
  waluta: string | null;
  rodzaj_kwoty: string | null;
  stawka_vat: string | null;
  obowiazuje_od: string;
  obowiazuje_do: string | null;
  status_weryfikacji: StatusWeryfikacji;
  dokument_zrodlowy_id: number | null;
  zrodlo_strona: number | null;
  zrodlo_paragraf: string | null;
}

export interface StanNaDzien {
  lokal_id: number;
  okres_najmu_id: number | null;
  na_dzien: string;
  parametry: Record<string, WartoscStanu>;
  brakujace_pola: string[];
  kompletnosc_procent: number;
  data_zakonczenia: string | null;
  powod_braku_daty_zakonczenia: string | null;
}

export interface Zdarzenie {
  id: number;
  typ: string;
  encja_typ: string;
  encja_id: number;
  lokal_id: number | null;
  data_zdarzenia: string;
  /** Dni do terminu; ujemnie, gdy termin minął. Liczy API, front tylko pokazuje. */
  dni_do_terminu: number | null;
  waga: WagaZdarzenia;
  status: StatusZdarzenia;
  tresc: string;
  odroczone_do: string | null;
  obsluzone_dnia: string | null;
  notatka: string | null;
  wersja: number;
}

/** Filtry listy lokali. Odpowiadają parametrom zapytania endpointu. */
export interface FiltryLokali {
  budynek_id?: number;
  status_lokalu?: StatusLokalu;
  typ?: TypLokalu;
  status_umowy?: StatusUmowy;
  koniec_od?: string;
  koniec_do?: string;
  waloryzacja?: boolean;
  niekompletne?: boolean;
  szukaj?: string;
  sortuj?: string;
  malejaco?: boolean;
  limit?: number;
  offset?: number;
}

export type RodzajZabezpieczenia =
  "kaucja" | "weksel" | "gwarancja_bankowa" | "polisa";

export type StatusZabezpieczenia =
  "wymagane" | "dostarczone" | "zwrocone" | "zatrzymane" | "brak";

export type StatusPrzegladu =
  "aktualny" | "zbliza_sie" | "przeterminowany" | "nieustalony";

export type TypWartosci = "kwota" | "liczba" | "data" | "flaga" | "tekst";

export type RodzajKwoty = "netto" | "brutto";

export type BazaOkresuNajmu = "data_zawarcia" | "data_przekazania";

export interface Lokal {
  id: number;
  budynek_id: number;
  oznaczenie: string;
  typ: TypLokalu;
  status: StatusLokalu;
  kondygnacja: string | null;
  powierzchnia_ewidencyjna: string | null;
  uwagi: string | null;
  wersja: number;
}

export interface Najemca {
  id: number;
  nazwa_pelna: string;
  nip: string | null;
  regon: string | null;
  krs: string | null;
  adres_siedziby: string | null;
  adres_korespondencyjny: string | null;
  email: string | null;
  telefon: string | null;
  osoba_fizyczna: boolean;
  notatki: string | null;
  wersja: number;
}

export interface OkresNajmu {
  id: number;
  lokal_id: number;
  najemca_id: number;
  data_zawarcia: string | null;
  data_przekazania: string | null;
  bazuje_na_dacie: BazaOkresuNajmu;
  okres_zawarcia_miesiace: number | null;
  okres_wypowiedzenia_miesiace: number | null;
  data_zakonczenia_planowana: string | null;
  data_zakonczenia_faktyczna: string | null;
  status: StatusUmowy;
  waloryzacja_podlega: boolean;
  waloryzacja_miesiac: number | null;
  waloryzacja_rodzaj_wskaznika: string | null;
  waloryzacja_stala_stawka: string | null;
  waloryzacja_pierwsza_data: string | null;
  uwagi: string | null;
  wersja: number;
}

/** Jedna wersja parametru w osi czasu. Także niezatwierdzona (decyzja D4). */
export interface Parametr {
  id: number;
  okres_najmu_id: number;
  klucz: string;
  typ_wartosci: TypWartosci;
  wartosc_kwota: string | null;
  wartosc_waluta: string | null;
  wartosc_rodzaj_kwoty: RodzajKwoty | null;
  wartosc_stawka_vat: string | null;
  wartosc_liczba: string | null;
  wartosc_data: string | null;
  wartosc_flaga: boolean | null;
  wartosc_tekst: string | null;
  obowiazuje_od: string;
  obowiazuje_do: string | null;
  dokument_zrodlowy_id: number | null;
  zrodlo_strona: number | null;
  zrodlo_paragraf: string | null;
  status_weryfikacji: StatusWeryfikacji;
  zatwierdzono_dnia: string | null;
  uwagi: string | null;
  wersja: number;
}

export interface Skladnik {
  id: number;
  okres_najmu_id: number;
  nazwa: string;
  klucz_parametru: string;
  sposob_wyliczenia: string | null;
  dzien_platnosci_miesiaca: number | null;
  /** Termin przesunięty na dzień roboczy (reguła R3). */
  dzien_platnosci_roboczy: string | null;
  okres_rozliczeniowy: string;
  czy_waloryzowany: boolean;
  uwagi: string | null;
  wersja: number;
}

export interface Zabezpieczenie {
  id: number;
  okres_najmu_id: number;
  rodzaj: RodzajZabezpieczenia;
  status: StatusZabezpieczenia;
  wymagana_wartosc: string | null;
  wymagana_waluta: string | null;
  wymagana_rodzaj_kwoty: RodzajKwoty | null;
  wymagana_stawka_vat: string | null;
  sposob_wyliczenia: string | null;
  data_wymagalnosci: string | null;
  data_dostarczenia: string | null;
  data_waznosci: string | null;
  data_zwrotu: string | null;
  miejsce_przechowywania: string | null;
  dokument_id: number | null;
  uwagi: string | null;
  wersja: number;
}

export interface Przeglad {
  id: number;
  lokal_id: number;
  okres_najmu_id: number | null;
  element: string;
  kto_obciazany: "najemca" | "wynajmujacy";
  czestotliwosc_miesiace: number | null;
  ostatni_przeglad_data: string | null;
  nastepny_przeglad_data: string | null;
  status: StatusPrzegladu;
  protokol_dokument_id: number | null;
  uwagi: string | null;
  wersja: number;
}

/** Filtry kokpitu terminów (koncepcja, sekcja 7.3). */
export interface FiltryZdarzen {
  status_zdarzenia?: StatusZdarzenia | "";
  waga?: WagaZdarzenia;
  typ?: string;
  lokal_id?: number;
  budynek_id?: number;
  do_dnia?: string;
  limit?: number;
  offset?: number;
}

// --------------------------------------------------- dokumenty z dysku (skan)

/** Typ dokumentu proponowany z nazwy pliku. `null` znaczy „nazwa nic nie mówi". */
export type TypDokumentu =
  | "umowa"
  | "aneks"
  | "protokol_przekazania"
  | "protokol_zdawczy"
  | "polisa"
  | "protokol_przegladu"
  | "wypowiedzenie"
  | "inne";

export interface PlikZeSkanu {
  nazwa: string;
  sciezka_wzgledna: string;
  rozmiar_bajty: number;
  /** nowy | w_systemie | pominiety */
  status: string;
  typ_proponowany: TypDokumentu | null;
  numer_proponowany: string | null;
  dokument_id: number | null;
  pominiecie_id: number | null;
}

export interface FolderZeSkanu {
  nazwa: string;
  sciezka_wzgledna: string;
  powiazanie_id: number | null;
  okres_najmu_id: number | null;
  opis_umowy: string | null;
  nowych: number;
  pliki: PlikZeSkanu[];
}

export interface BudynekZeSkanu {
  nazwa_folderu: string;
  budynek_id: number | null;
  budynek_nazwa: string | null;
  foldery: FolderZeSkanu[];
}

export interface WynikSkanu {
  katalog: string | null;
  dostepny: boolean;
  komunikat: string | null;
  nowych: number;
  obcietych: number;
  /** Ile katalogów i plików system odmówił udostępnić. */
  niedostepnych: number;
  budynki: BudynekZeSkanu[];
}

export interface KatalogSkanu {
  sciezka: string | null;
  /** baza | plik | brak — skąd pochodzi wartość. */
  zrodlo: string;
  istnieje: boolean;
}

export interface ZerwanyLink {
  dokument_id: number;
  nazwa: string | null;
  sciezka_wzgledna: string;
  okres_najmu_id: number | null;
  powod: string;
}

export interface PrzegladLinkow {
  katalog: string | null;
  sprawdzonych: number;
  zerwane: ZerwanyLink[];
}
