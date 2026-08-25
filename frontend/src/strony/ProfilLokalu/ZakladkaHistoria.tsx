import { useMemo, useState } from 'react'
import type { Parametr, StatusWeryfikacji } from '@/api/typy'
import { BladApi } from '@/api/klient'
import { useDecyzjaOParametrze, useHistoriaParametrow } from '@/api/zapytania'
import { formatujDate, formatujKwote } from '@/funkcje/format'
import { czytelnaNazwaPola } from '@/funkcje/nazwy'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { Button } from '@/components/ui/button'
import { FormularzParametru } from './Formularze'
import { Karta, OdznakaWeryfikacji } from './Wspolne'

const NAZWY_PARAMETROW: Record<string, string> = {
  czynsz_podstawowy: 'Czynsz podstawowy',
  stawka_m2: 'Stawka za m²',
  powierzchnia: 'Powierzchnia z umowy',
  data_zakonczenia: 'Data zakończenia',
  oplata_eksploatacyjna: 'Opłata eksploatacyjna',
}

/** Statusy, które wchodzą do stanu efektywnego (decyzja D4). */
const OBOWIAZUJACE: StatusWeryfikacji[] = ['zatwierdzona', 'poprawiona']

function wartoscTekstem(p: Parametr): string {
  switch (p.typ_wartosci) {
    case 'kwota':
      return p.wartosc_kwota ? formatujKwote(p.wartosc_kwota, p.wartosc_waluta ?? 'PLN') : '—'
    case 'liczba':
      return p.wartosc_liczba ?? '—'
    case 'data':
      return formatujDate(p.wartosc_data)
    case 'flaga':
      return p.wartosc_flaga ? 'tak' : 'nie'
    case 'tekst':
      return p.wartosc_tekst ?? '—'
  }
}

/**
 * Oś czasu zmian parametrów (koncepcja, sekcja 7.2).
 *
 * Pokazuje **wszystkie** wersje, także niezatwierdzone. To jest celowe:
 * ukrycie propozycji czekających na decyzję ukryłoby pracę do zrobienia,
 * a ta zakładka jest jedynym miejscem, w którym widać, że coś czeka.
 *
 * Stąd też przyciski zatwierdzania: decyzja D4 mówi, że każdą liczbę
 * zatwierdza człowiek, więc musi mieć gdzie to zrobić.
 */
export function ZakladkaHistoria({ okresId }: { okresId: number | null }) {
  const historia = useHistoriaParametrow(okresId)
  const decyzja = useDecyzjaOParametrze()
  const [blad, setBlad] = useState<string | null>(null)
  const [otwarty, setOtwarty] = useState(false)

  const pogrupowane = useMemo(() => {
    const mapa = new Map<string, Parametr[]>()
    for (const p of historia.data ?? []) {
      const lista = mapa.get(p.klucz) ?? []
      lista.push(p)
      mapa.set(p.klucz, lista)
    }
    // Najnowsze na górze każdej grupy: pytanie „co obowiązuje" pada częściej
    // niż „co obowiązywało trzy lata temu".
    for (const lista of mapa.values()) {
      lista.sort((a, b) => b.obowiazuje_od.localeCompare(a.obowiazuje_od) || b.id - a.id)
    }
    return [...mapa.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [historia.data])

  if (okresId === null) {
    return <Pusto tytul="Brak umowy" opis="Bez umowy nie ma parametrów ani ich historii." />
  }
  if (historia.isPending) return <Ladowanie wierszy={4} />
  if (historia.isError) {
    return (
      <Blad
        komunikat={historia.error instanceof Error ? historia.error.message : 'Nieznany błąd.'}
        ponow={() => void historia.refetch()}
      />
    )
  }
  if (pogrupowane.length === 0) {
    return (
      <>
        <Pusto
          tytul="Brak wprowadzonych warunków"
          opis="Warunki umowy wprowadza się ręcznie albo wczytuje z dokumentu. Ekstrakcja wchodzi w późniejszym etapie."
          akcja={<Button onClick={() => setOtwarty(true)}>Dodaj warunek</Button>}
        />
        <FormularzParametru
          otwarty={otwarty}
          onZamknij={() => setOtwarty(false)}
          okresId={okresId}
        />
      </>
    )
  }

  const czekajace = (historia.data ?? []).filter(
    (p) => p.status_weryfikacji === 'zaproponowana',
  ).length

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setOtwarty(true)}>Dodaj warunek</Button>
      </div>

      {blad && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {blad}
        </p>
      )}

      {czekajace > 0 && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {czekajace === 1
            ? 'Jedna wartość czeka na decyzję.'
            : `${czekajace} wartości czeka na decyzję.`}{' '}
          Dopóki nie zostaną zatwierdzone, nie wchodzą do stanu ani do alertów.
        </p>
      )}

      {pogrupowane.map(([klucz, wersje]) => (
        <Karta key={klucz} tytul={NAZWY_PARAMETROW[klucz] ?? czytelnaNazwaPola(klucz)}>
          <ol className="divide-y">
            {wersje.map((p, indeks) => {
              const obowiazuje = OBOWIAZUJACE.includes(p.status_weryfikacji)
              const najnowszaObowiazujaca =
                obowiazuje && wersje.slice(0, indeks).every((w) => !OBOWIAZUJACE.includes(w.status_weryfikacji))

              return (
                <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5">
                  <span className="w-32 shrink-0 text-sm text-muted-foreground">
                    od {formatujDate(p.obowiazuje_od)}
                  </span>

                  <span className="text-sm font-medium tabular-nums">
                    {wartoscTekstem(p)}
                    {p.wartosc_rodzaj_kwoty && (
                      <span className="ml-1 text-xs font-normal text-muted-foreground">
                        {p.wartosc_rodzaj_kwoty}
                      </span>
                    )}
                  </span>

                  <OdznakaWeryfikacji status={p.status_weryfikacji} />

                  {najnowszaObowiazujaca && (
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800">
                      obowiązuje
                    </span>
                  )}

                  <span className="ml-auto text-xs text-muted-foreground">
                    {p.dokument_zrodlowy_id
                      ? `dokument #${p.dokument_zrodlowy_id}`
                      : 'wprowadzone ręcznie'}
                    {p.zrodlo_paragraf && ` · ${p.zrodlo_paragraf}`}
                    {p.zrodlo_strona && `, str. ${p.zrodlo_strona}`}
                  </span>

                  {p.status_weryfikacji === 'zaproponowana' && (
                    <span className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={decyzja.isPending}
                        onClick={() => {
                          setBlad(null)
                          decyzja.mutate(
                            { id: p.id, status: 'zatwierdzona' },
                            {
                              onError: (e) =>
                                setBlad(
                                  e instanceof BladApi ? e.message : 'Nie udało się zapisać.',
                                ),
                            },
                          )
                        }}
                      >
                        Zatwierdź
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={decyzja.isPending}
                        onClick={() => {
                          setBlad(null)
                          decyzja.mutate({ id: p.id, status: 'odrzucona' })
                        }}
                      >
                        Odrzuć
                      </Button>
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
        </Karta>
      ))}

      <FormularzParametru
        otwarty={otwarty}
        onZamknij={() => setOtwarty(false)}
        okresId={okresId}
      />
    </div>
  )
}
