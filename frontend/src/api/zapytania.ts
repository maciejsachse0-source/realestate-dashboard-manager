/**
 * Zapytania TanStack Query. Jedno miejsce, w ktorym front wie, jak nazywaja sie
 * endpointy i jak wygladaja klucze cache'u.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { pobierz, wyslij } from './klient'
import type {
  Budynek,
  FiltryLokali,
  LokalNaLiscie,
  Profil,
  StanNaDzien,
  Strona,
  Zdarzenie,
} from './typy'

export const klucze = {
  profil: ['profil'] as const,
  budynki: ['budynki'] as const,
  lokale: (filtry: FiltryLokali) => ['lokale', filtry] as const,
  stan: (lokalId: number, naDzien?: string) => ['stan', lokalId, naDzien ?? 'dzis'] as const,
  zdarzenia: (filtry: Record<string, unknown>) => ['zdarzenia', filtry] as const,
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
