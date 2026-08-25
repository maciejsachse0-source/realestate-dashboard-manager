import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useObsluzZdarzenie, useZdarzenia } from '@/api/zapytania'
import type { WagaZdarzenia, Zdarzenie } from '@/api/typy'
import { formatujDate } from '@/funkcje/format'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const OPIS_WAGI: Record<WagaZdarzenia, string> = {
  krytyczne: 'Krytyczne',
  ostrzezenie: 'Ostrzeżenie',
  informacja: 'Informacja',
}

const KOLEJNOSC: WagaZdarzenia[] = ['krytyczne', 'ostrzezenie', 'informacja']

/**
 * Kokpit terminow (koncepcja, sekcja 7.3).
 *
 * Zdarzenia pogrupowane wedlug pilnosci. To jest wlasciwy produkt tego systemu:
 * tabela lokali jest widokiem, a alerty sa tym, po co ktos tu wchodzi rano.
 */
export default function KokpitTerminow() {
  const nawigacja = useNavigate()
  const [tylkoOtwarte, setTylkoOtwarte] = useState(true)
  const zdarzenia = useZdarzenia({
    limit: 200,
    status_zdarzenia: tylkoOtwarte ? 'otwarte' : undefined,
  })
  const obsluz = useObsluzZdarzenie()

  const pozycje = zdarzenia.data?.pozycje ?? []
  const pogrupowane = KOLEJNOSC.map((waga) => ({
    waga,
    lista: pozycje.filter((z) => z.waga === waga),
  })).filter((g) => g.lista.length > 0)

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Terminy</h1>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4"
            checked={tylkoOtwarte}
            onChange={(e) => setTylkoOtwarte(e.target.checked)}
          />
          Tylko nieobsłużone
        </label>
      </div>

      {zdarzenia.isPending && <Ladowanie wierszy={5} />}

      {zdarzenia.isError && (
        <Blad
          komunikat={
            zdarzenia.error instanceof Error ? zdarzenia.error.message : 'Nieznany błąd.'
          }
          ponow={() => void zdarzenia.refetch()}
        />
      )}

      {zdarzenia.data && pozycje.length === 0 && (
        <Pusto
          tytul={tylkoOtwarte ? 'Nic nie wymaga uwagi' : 'Brak zdarzeń'}
          opis={
            tylkoOtwarte
              ? 'Wszystkie terminy są obsłużone. Generator sprawdza je codziennie o 6:00.'
              : 'System nie wygenerował jeszcze żadnych zdarzeń. Sprawdź, czy są wprowadzone umowy.'
          }
        />
      )}

      {pogrupowane.map(({ waga, lista }) => (
        <section key={waga} className="space-y-2">
          <h2 className="flex items-center gap-2 text-sm font-medium">
            <Badge variant={waga === 'krytyczne' ? 'destructive' : 'secondary'}>
              {OPIS_WAGI[waga]}
            </Badge>
            <span className="text-muted-foreground">{lista.length}</span>
          </h2>

          <ul className="divide-y rounded-lg border bg-background">
            {lista.map((zdarzenie) => (
              <Wiersz
                key={zdarzenie.id}
                zdarzenie={zdarzenie}
                naLokal={() =>
                  zdarzenie.lokal_id && nawigacja(`/lokale/${zdarzenie.lokal_id}`)
                }
                naObsluzone={() => obsluz.mutate({ id: zdarzenie.id })}
                zajety={obsluz.isPending}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function Wiersz({
  zdarzenie,
  naLokal,
  naObsluzone,
  zajety,
}: {
  zdarzenie: Zdarzenie
  naLokal: () => void
  naObsluzone: () => void
  zajety: boolean
}) {
  return (
    <li className="flex items-center gap-4 p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm">{zdarzenie.tresc}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {formatujDate(zdarzenie.data_zdarzenia)}
          {zdarzenie.status !== 'otwarte' && ` · ${zdarzenie.status}`}
        </p>
      </div>

      {zdarzenie.lokal_id && (
        <Button variant="ghost" size="sm" onClick={naLokal}>
          Pokaż lokal
        </Button>
      )}
      {zdarzenie.status === 'otwarte' && (
        <Button variant="outline" size="sm" onClick={naObsluzone} disabled={zajety}>
          Obsłużone
        </Button>
      )}
    </li>
  )
}
