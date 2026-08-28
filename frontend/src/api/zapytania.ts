/**
 * Zapytania TanStack Query. Jedno miejsce, w ktorym front wie, jak nazywaja sie
 * endpointy i jak wygladaja klucze cache'u.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { pobierz, usun, wyslij, zapisz } from './klient'
import type {
  Budynek,
  FiltryLokali,
  Lokal,
  LokalNaLiscie,
  Najemca,
  OkresNajmu,
  Parametr,
  Profil,
  PrzegladLinkow,
  Przeglad,
  Skladnik,
  StanNaDzien,
  StatusWeryfikacji,
  Strona,
  UzytkownikNaLiscie,
  WynikSkanu,
  Zabezpieczenie,
  Zdarzenie,
} from './typy'

export const klucze = {
  profil: ['profil'] as const,
  budynki: ['budynki'] as const,
  lokale: (filtry: FiltryLokali) => ['lokale', filtry] as const,
  stan: (lokalId: number, naDzien?: string) => ['stan', lokalId, naDzien ?? 'dzis'] as const,
  zdarzenia: (filtry: Record<string, unknown>) => ['zdarzenia', filtry] as const,
  skan: ['skan'] as const,
}

export function useProfil() {
  return useQuery({
    queryKey: klucze.profil,
    queryFn: () => pobierz<Profil>('/auth/ja'),
    // Brak sesji to normalny stan przy pierwszym wejsciu, a nie awaria,
    // wiec nie ponawiamy zapytania.
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLogowanie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: { login: string; haslo: string }) =>
      wyslij<Profil>('/auth/logowanie', dane),
    onSuccess: (profil) => {
      kolejka.setQueryData(klucze.profil, profil)
    },
  })
}

export function useWylogowanie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: () => wyslij<void>('/auth/wylogowanie'),
    onSuccess: () => {
      kolejka.clear()
    },
  })
}

export function useZmianaHasla() {
  return useMutation({
    mutationFn: (dane: { haslo_biezace: string; haslo_nowe: string }) =>
      wyslij<void>('/auth/haslo', dane),
  })
}

export function useBudynki() {
  return useQuery({
    queryKey: klucze.budynki,
    queryFn: () => pobierz<Strona<Budynek>>('/budynki', { limit: 500 }),
    staleTime: 10 * 60 * 1000,
  })
}

export function useLokale(filtry: FiltryLokali) {
  return useQuery({
    queryKey: klucze.lokale(filtry),
    queryFn: () => pobierz<Strona<LokalNaLiscie>>('/lokale', filtry as Record<string, unknown>),
    // Poprzednia strona zostaje widoczna przy zmianie filtrow, zeby tabela
    // nie migala pustka przy kazdym nacisnieciu klawisza w wyszukiwarce.
    placeholderData: (poprzednie) => poprzednie,
  })
}

export function useStanLokalu(lokalId: number, naDzien?: string) {
  return useQuery({
    queryKey: klucze.stan(lokalId, naDzien),
    queryFn: () => pobierz<StanNaDzien>(`/lokale/${lokalId}/stan`, { na_dzien: naDzien }),
  })
}

export function useZdarzenia(filtry: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: klucze.zdarzenia(filtry),
    queryFn: () => pobierz<Strona<Zdarzenie>>('/zdarzenia', filtry),
  })
}

export function useObsluzZdarzenie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notatka }: { id: number; notatka?: string }) =>
      wyslij<Zdarzenie>(`/zdarzenia/${id}/obsluzone`, { notatka: notatka ?? null }),
    onSuccess: () => {
      void kolejka.invalidateQueries({ queryKey: ['zdarzenia'] })
      void kolejka.invalidateQueries({ queryKey: ['lokale'] })
    },
  })
}

// ------------------------------------------------------- profil lokalu

export function useLokal(lokalId: number) {
  return useQuery({
    queryKey: ['lokal', lokalId],
    queryFn: () => pobierz<Lokal>(`/lokale/${lokalId}`),
  })
}

export function useOkresNajmu(okresId: number | null | undefined) {
  return useQuery({
    queryKey: ['okres', okresId],
    queryFn: () => pobierz<OkresNajmu>(`/okresy-najmu/${okresId}`),
    enabled: okresId != null,
  })
}

export function useNajemca(najemcaId: number | null | undefined) {
  return useQuery({
    queryKey: ['najemca', najemcaId],
    queryFn: () => pobierz<Najemca>(`/najemcy/${najemcaId}`),
    enabled: najemcaId != null,
  })
}

/** Cała oś czasu parametrów, także wartości niezatwierdzone (zakładka Historia). */
export function useHistoriaParametrow(okresId: number | null | undefined) {
  return useQuery({
    queryKey: ['parametry', okresId],
    queryFn: () => pobierz<Parametr[]>(`/okresy-najmu/${okresId}/parametry`),
    enabled: okresId != null,
  })
}

export function useSkladniki(okresId: number | null | undefined) {
  return useQuery({
    queryKey: ['skladniki', okresId],
    queryFn: () => pobierz<Skladnik[]>(`/okresy-najmu/${okresId}/skladniki`),
    enabled: okresId != null,
  })
}

export function useZabezpieczenia(okresId: number | null | undefined) {
  return useQuery({
    queryKey: ['zabezpieczenia', okresId],
    queryFn: () => pobierz<Zabezpieczenie[]>(`/okresy-najmu/${okresId}/zabezpieczenia`),
    enabled: okresId != null,
  })
}

export function usePrzeglady(lokalId: number) {
  return useQuery({
    queryKey: ['przeglady', lokalId],
    queryFn: () => pobierz<Przeglad[]>(`/lokale/${lokalId}/przeglady`),
  })
}

export function useUzytkownicy() {
  return useQuery({
    queryKey: ['uzytkownicy'],
    queryFn: () => pobierz<UzytkownikNaLiscie[]>('/uzytkownicy'),
    staleTime: 10 * 60 * 1000,
  })
}

// ------------------------------------------------------------- zmiany

/** Unieważnia wszystko, co dotyczy jednego lokalu. Po zmianie danych umowy
 *  zmienia się i stan efektywny, i kompletność, i lista na dashboardzie. */
function odswiezLokal(kolejka: ReturnType<typeof useQueryClient>) {
  for (const klucz of ['stan', 'lokale', 'parametry', 'skladniki', 'zabezpieczenia', 'przeglady', 'okres']) {
    void kolejka.invalidateQueries({ queryKey: [klucz] })
  }
}

export function useDecyzjaOParametrze() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, uwagi }: { id: number; status: StatusWeryfikacji; uwagi?: string }) =>
      wyslij<Parametr>(`/parametry/${id}/decyzja`, { status, uwagi: uwagi ?? null }),
    onSuccess: () => odswiezLokal(kolejka),
  })
}

export function useDodajParametr() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ okresId, dane }: { okresId: number; dane: Record<string, unknown> }) =>
      wyslij<Parametr>(`/okresy-najmu/${okresId}/parametry`, dane),
    onSuccess: () => odswiezLokal(kolejka),
  })
}

export function useZmienZabezpieczenie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dane }: { id: number; dane: Record<string, unknown> }) =>
      zapisz<Zabezpieczenie>(`/zabezpieczenia/${id}`, dane),
    onSuccess: () => odswiezLokal(kolejka),
  })
}

export function useProtokolPrzegladu() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: string }) =>
      wyslij<Przeglad>(`/przeglady/${id}/protokol?data_protokolu=${data}`),
    onSuccess: () => odswiezLokal(kolejka),
  })
}

// --------------------------------------------------------- kokpit terminow

export function useOdroczZdarzenie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, do_dnia, notatka }: { id: number; do_dnia: string; notatka?: string }) =>
      wyslij(`/zdarzenia/${id}/odroczenie`, {
        odroczone_do: do_dnia,
        notatka: notatka ?? null,
      }),
    onSuccess: () => {
      void kolejka.invalidateQueries({ queryKey: ['zdarzenia'] })
      void kolejka.invalidateQueries({ queryKey: ['lokale'] })
    },
  })
}

export function usePrzypiszZdarzenie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, uzytkownikId }: { id: number; uzytkownikId: number | null }) =>
      wyslij(`/zdarzenia/${id}/przypisanie`, { uzytkownik_id: uzytkownikId }),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['zdarzenia'] }),
  })
}

// ------------------------------------------------------ tworzenie i edycja

export function useDodajBudynek() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<Budynek>('/budynki', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['budynki'] }),
  })
}

export function useDodajLokal() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<Lokal>('/lokale', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['lokale'] }),
  })
}

export function useZmienLokal() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dane }: { id: number; dane: Record<string, unknown> }) =>
      zapisz<Lokal>(`/lokale/${id}`, dane),
    onSuccess: (_, { id }) => {
      void kolejka.invalidateQueries({ queryKey: ['lokale'] })
      void kolejka.invalidateQueries({ queryKey: ['lokal', id] })
    },
  })
}

export function useDodajNajemce() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<Najemca>('/najemcy', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['najemcy'] }),
  })
}

export function useNajemcy(szukaj?: string) {
  return useQuery({
    queryKey: ['najemcy', szukaj ?? ''],
    queryFn: () => pobierz<Strona<Najemca>>('/najemcy', { limit: 500, szukaj }),
  })
}

export function useDodajOkresNajmu() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<OkresNajmu>('/okresy-najmu', dane),
    onSuccess: () => {
      void kolejka.invalidateQueries({ queryKey: ['stan'] })
      void kolejka.invalidateQueries({ queryKey: ['lokale'] })
    },
  })
}

export function useDodajSkladnik() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ okresId, dane }: { okresId: number; dane: Record<string, unknown> }) =>
      wyslij<Skladnik>(`/okresy-najmu/${okresId}/skladniki`, dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['skladniki'] }),
  })
}

export function useDodajZabezpieczenie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: ({ okresId, dane }: { okresId: number; dane: Record<string, unknown> }) =>
      wyslij<Zabezpieczenie>(`/okresy-najmu/${okresId}/zabezpieczenia`, dane),
    onSuccess: () => {
      void kolejka.invalidateQueries({ queryKey: ['zabezpieczenia'] })
      void kolejka.invalidateQueries({ queryKey: ['stan'] })
      void kolejka.invalidateQueries({ queryKey: ['lokale'] })
    },
  })
}

export function useDodajPrzeglad() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<Przeglad>('/przeglady', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: ['przeglady'] }),
  })
}

// --------------------------------------------------- dokumenty z dysku (skan)

/**
 * Skan przechodzi po drzewie katalogow i liczy skroty nowych plikow, wiec
 * jest drozszy niz zwykle zapytanie. Nie odswiezamy go samoczynnie -- czlowiek
 * naciska "Skanuj ponownie", kiedy cos zmienil w folderach.
 */
export function useSkan() {
  return useQuery({
    queryKey: klucze.skan,
    queryFn: () => pobierz<WynikSkanu>('/skan'),
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
  })
}

export function usePowiazFolder() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: { sciezka_wzgledna: string; okres_najmu_id: number }) =>
      wyslij<{ id: number }>('/skan/powiazania', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: klucze.skan }),
  })
}

export function useOdepnijFolder() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => usun(`/skan/powiazania/${id}`),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: klucze.skan }),
  })
}

export function useZaimportujZDysku() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: Record<string, unknown>) => wyslij<{ id: number }>('/skan/importuj', dane),
    onSuccess: () => {
      void kolejka.invalidateQueries({ queryKey: klucze.skan })
      void kolejka.invalidateQueries({ queryKey: ['dokumenty'] })
    },
  })
}

export function usePominPlik() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (dane: { sciezka_wzgledna: string }) =>
      wyslij<{ id: number }>('/skan/pominiecia', dane),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: klucze.skan }),
  })
}

export function useCofnijPominiecie() {
  const kolejka = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => usun(`/skan/pominiecia/${id}`),
    onSuccess: () => void kolejka.invalidateQueries({ queryKey: klucze.skan }),
  })
}

/** Przeglad odnosnikow: czy zlinkowane pliki nadal leza tam, gdzie lezaly. */
export function usePrzegladLinkow(wlaczony: boolean) {
  return useQuery({
    queryKey: ['przeglad-linkow'],
    queryFn: () => pobierz<PrzegladLinkow>('/skan/sprawdz'),
    enabled: wlaczony,
    staleTime: Infinity,
  })
}
