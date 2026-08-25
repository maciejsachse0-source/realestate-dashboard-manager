import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useStanLokalu, useZdarzenia } from '@/api/zapytania'
import type { WartoscStanu } from '@/api/typy'
import { BRAK_DANYCH, formatujDate, formatujKwote } from '@/funkcje/format'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { PasekKompletnosci } from '@/komponenty/PasekKompletnosci'
import { czytelnaNazwaPola } from '@/funkcje/nazwy'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/** Nazwy parametrów po polsku. Klucz techniczny nie jest dla użytkownika. */
const NAZWY_PARAMETROW: Record<string, string> = {
  czynsz_podstawowy: 'Czynsz podstawowy',
  stawka_m2: 'Stawka za m²',
  powierzchnia: 'Powierzchnia z umowy',
  data_zakonczenia: 'Data zakończenia',
  oplata_eksploatacyjna: 'Opłata eksploatacyjna',
}

/**
 * Profil lokalu (koncepcja, sekcja 7.2).
 *
 * Zasada twarda: każda wartość pochodząca z dokumentu jest klikalna i prowadzi
 * do źródła. Wartości niezatwierdzone są wyróżnione wizualnie (decyzja D4).
 *
 * Pole „stan na dzień" pozwala cofnąć się w czasie. To jest widoczna twarz
 * decyzji D2: historia zostaje nienaruszona, a aneks tylko dokłada wersję.
 */
export default function ProfilLokalu() {
  const { lokalId } = useParams<{ lokalId: string }>()
  const [naDzien, setNaDzien] = useState('')
  const identyfikator = Number(lokalId)

  const stan = useStanLokalu(identyfikator, naDzien || undefined)
  const zdarzenia = useZdarzenia({ lokal_id: identyfikator, limit: 50 })

  if (Number.isNaN(identyfikator)) {
    return <Blad komunikat="Nieprawidłowy numer lokalu w adresie." />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-muted-foreground underline underline-offset-4">
            ← Wróć do listy
          </Link>
          <h1 className="mt-1 text-lg font-semibold">Profil lokalu</h1>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="na_dzien">Stan na dzień</Label>
          <Input
            id="na_dzien"
            type="date"
            className="w-44"
            value={naDzien}
            onChange={(e) => setNaDzien(e.target.value)}
          />
        </div>
      </div>

      {stan.isPending && <Ladowanie wierszy={4} />}

      {stan.isError && (
        <Blad
          komunikat={stan.error instanceof Error ? stan.error.message : 'Nieznany błąd.'}
          ponow={() => void stan.refetch()}
        />
      )}

      {stan.data && (
        <>
          <section className="rounded-lg border bg-background p-4">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <p className="text-xs text-muted-foreground">Kompletność profilu</p>
                <div className="mt-1">
                  <PasekKompletnosci
                    procent={stan.data.kompletnosc_procent}
                    braki={stan.data.brakujace_pola}
                  />
                </div>
              </div>

              <div>
                <p className="text-xs text-muted-foreground">Koniec umowy</p>
                <p className="mt-1 text-sm">
                  {stan.data.data_zakonczenia ? (
                    formatujDate(stan.data.data_zakonczenia)
                  ) : (
                    <span className="text-amber-700">nieustalona</span>
                  )}
                </p>
              </div>
            </div>

            {stan.data.powod_braku_daty_zakonczenia && (
              <p className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
                {stan.data.powod_braku_daty_zakonczenia}
              </p>
            )}

            {stan.data.brakujace_pola.length > 0 && (
              <p className="mt-3 text-sm text-muted-foreground">
                Do uzupełnienia:{' '}
                {stan.data.brakujace_pola.map(czytelnaNazwaPola).join(', ')}
              </p>
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium">Warunki obowiązujące</h2>
            {Object.keys(stan.data.parametry).length === 0 ? (
              <Pusto
                tytul="Brak zatwierdzonych warunków"
                opis="Wartości niezatwierdzone nie wchodzą do stanu. Zatwierdź je na ekranie weryfikacji."
              />
            ) : (
              <div className="divide-y rounded-lg border bg-background">
                {Object.entries(stan.data.parametry).map(([klucz, wartosc]) => (
                  <Parametr key={klucz} klucz={klucz} wartosc={wartosc} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium">Zdarzenia</h2>
            {zdarzenia.data && zdarzenia.data.pozycje.length === 0 ? (
              <Pusto tytul="Brak zdarzeń" opis="Ten lokal nie ma otwartych terminów." />
            ) : (
              <ul className="divide-y rounded-lg border bg-background">
                {zdarzenia.data?.pozycje.map((z) => (
                  <li key={z.id} className="flex items-center gap-3 p-3 text-sm">
                    <Badge variant={z.waga === 'krytyczne' ? 'destructive' : 'secondary'}>
                      {z.waga}
                    </Badge>
                    <span className="flex-1">{z.tresc}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatujDate(z.data_zdarzenia)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}

function Parametr({ klucz, wartosc }: { klucz: string; wartosc: WartoscStanu }) {
  const niezatwierdzona = wartosc.status_weryfikacji !== 'zatwierdzona'
  const zrodlo = [
    wartosc.zrodlo_strona ? `str. ${wartosc.zrodlo_strona}` : null,
    wartosc.zrodlo_paragraf,
  ]
    .filter(Boolean)
    .join(', ')

  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 p-3">
      <span className="w-56 text-sm text-muted-foreground">
        {NAZWY_PARAMETROW[klucz] ?? czytelnaNazwaPola(klucz)}
      </span>

      <span className="text-sm font-medium tabular-nums">
        {wartosc.typ === 'kwota'
          ? formatujKwote(wartosc.wartosc, wartosc.waluta ?? 'PLN')
          : wartosc.wartosc || BRAK_DANYCH}
        {wartosc.rodzaj_kwoty && (
          <span className="ml-1 text-xs font-normal text-muted-foreground">
            {wartosc.rodzaj_kwoty}
          </span>
        )}
      </span>

      {niezatwierdzona && (
        <Badge variant="outline" className="border-amber-400 text-amber-700">
          {wartosc.status_weryfikacji}
        </Badge>
      )}

      <span className="ml-auto text-xs text-muted-foreground">
        od {formatujDate(wartosc.obowiazuje_od)}
        {wartosc.dokument_zrodlowy_id && (
          // Dokumenty wchodzą w etapie E7. Do tego czasu pokazujemy sam ślad,
          // bo sama informacja „skąd ta liczba" jest już wartościowa.
          <span className="ml-2">· dokument #{wartosc.dokument_zrodlowy_id}</span>
        )}
        {zrodlo && <span className="ml-1">({zrodlo})</span>}
      </span>
    </div>
  )
}
