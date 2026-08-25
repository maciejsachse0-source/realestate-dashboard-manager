import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { flexRender } from '@tanstack/react-table'
// Wejscie `legacy` to wspierany interfejs v8 dostarczany wewnatrz v9.
// Uzasadnienie i sciezka migracji: docs/decyzje/006-tanstack-table-legacy.md
import {
  getCoreRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from '@tanstack/react-table/legacy'

import { useBudynki, useLokale } from '@/api/zapytania'
import type { FiltryLokali, LokalNaLiscie } from '@/api/typy'
import { BRAK_DANYCH, formatujDate, formatujKwote, formatujPowierzchnie } from '@/funkcje/format'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { PasekKompletnosci } from '@/komponenty/PasekKompletnosci'
import { PanelFiltrow } from './PanelFiltrow'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

const NA_STRONIE = 50

/** Etykiety statusów. Enum z API jest techniczny, użytkownik czyta polski tekst. */
const ETYKIETY_STATUSU: Record<string, string> = {
  wolny: 'Wolny',
  wynajety: 'Wynajęty',
  w_trakcie_wydania: 'W trakcie wydania',
  przygotowanie: 'W przygotowaniu',
  aktywna: 'Aktywna',
  wypowiedziana: 'Wypowiedziana',
  zakonczona: 'Zakończona',
}

/**
 * Dashboard: lista lokali (koncepcja, sekcja 7.1).
 *
 * Bytem centralnym jest lokal, nie umowa (decyzja D1), więc wiersz to lokal,
 * a dane umowy są jego bieżącym stanem.
 */
export default function Dashboard() {
  const nawigacja = useNavigate()
  const [filtry, setFiltry] = useState<FiltryLokali>({ limit: NA_STRONIE, offset: 0 })
  const budynki = useBudynki()
  const lokale = useLokale(filtry)

  const nazwyBudynkow = useMemo(
    () => budynki.data?.pozycje.map((b) => ({ id: b.id, nazwa: b.nazwa })) ?? [],
    [budynki.data],
  )

  const kolumny = useMemo<LegacyColumnDef<LokalNaLiscie>[]>(
    () => [
      {
        accessorKey: 'oznaczenie',
        header: 'Lokal',
        cell: ({ row }) => (
          <div>
            <div className="font-medium">{row.original.oznaczenie}</div>
            <div className="text-xs text-muted-foreground">{row.original.budynek_nazwa}</div>
          </div>
        ),
      },
      {
        accessorKey: 'najemca_nazwa',
        header: 'Najemca',
        cell: ({ row }) =>
          row.original.najemca_nazwa ?? (
            <span className="text-muted-foreground">{BRAK_DANYCH}</span>
          ),
      },
      {
        accessorKey: 'status_umowy',
        header: 'Umowa',
        cell: ({ row }) => {
          const status = row.original.status_umowy
          if (!status) return <span className="text-muted-foreground">brak umowy</span>
          return (
            <Badge variant={status === 'aktywna' ? 'default' : 'secondary'}>
              {ETYKIETY_STATUSU[status] ?? status}
            </Badge>
          )
        },
      },
      {
        accessorKey: 'powierzchnia_ewidencyjna',
        header: () => <div className="text-right">Powierzchnia</div>,
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {row.original.powierzchnia_ewidencyjna
              ? formatujPowierzchnie(row.original.powierzchnia_ewidencyjna)
              : BRAK_DANYCH}
          </div>
        ),
      },
      {
        accessorKey: 'czynsz',
        header: () => <div className="text-right">Czynsz</div>,
        cell: ({ row }) => {
          const { czynsz, czynsz_waluta, czynsz_rodzaj } = row.original
          if (!czynsz) {
            return <div className="text-right text-muted-foreground">{BRAK_DANYCH}</div>
          }
          return (
            <div className="text-right tabular-nums">
              {formatujKwote(czynsz, czynsz_waluta ?? 'PLN')}
              <span className="ml-1 text-xs text-muted-foreground">{czynsz_rodzaj}</span>
            </div>
          )
        },
      },
      {
        accessorKey: 'data_zakonczenia',
        header: 'Koniec umowy',
        cell: ({ row }) => {
          const { data_zakonczenia, powod_braku_daty_zakonczenia } = row.original
          if (data_zakonczenia) return formatujDate(data_zakonczenia)
          if (!powod_braku_daty_zakonczenia) {
            return <span className="text-muted-foreground">{BRAK_DANYCH}</span>
          }
          // Decyzja D5: brak danych to informacja z powodem, nie pusta komórka.
          return (
            <span
              className="cursor-help text-amber-700 underline decoration-dotted underline-offset-4"
              title={powod_braku_daty_zakonczenia}
            >
              nieustalona
            </span>
          )
        },
      },
      {
        accessorKey: 'kompletnosc_procent',
        header: 'Kompletność',
        cell: ({ row }) => (
          <PasekKompletnosci
            procent={row.original.kompletnosc_procent}
            braki={row.original.brakujace_pola}
          />
        ),
      },
      {
        accessorKey: 'zdarzen_otwartych',
        header: () => <div className="text-right">Alerty</div>,
        cell: ({ row }) => {
          const ile = row.original.zdarzen_otwartych
          return (
            <div className="text-right">
              {ile > 0 ? (
                <Badge variant="destructive">{ile}</Badge>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>
          )
        },
      },
    ],
    [],
  )

  const tabela = useLegacyTable({
    data: lokale.data?.pozycje ?? [],
    columns: kolumny,
    getCoreRowModel: getCoreRowModel(),
  })

  const wszystkich = lokale.data?.wszystkich ?? 0
  const offset = filtry.offset ?? 0

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Lokale</h1>
        {lokale.data && (
          <p className="text-sm text-muted-foreground">
            {wszystkich === 0
              ? 'Brak wyników'
              : `${offset + 1}–${Math.min(offset + NA_STRONIE, wszystkich)} z ${wszystkich}`}
          </p>
        )}
      </div>

      <PanelFiltrow filtry={filtry} budynki={nazwyBudynkow} onZmiana={setFiltry} />

      {lokale.isPending && <Ladowanie />}

      {lokale.isError && (
        <Blad
          komunikat={
            lokale.error instanceof Error ? lokale.error.message : 'Nieznany błąd połączenia.'
          }
          ponow={() => void lokale.refetch()}
        />
      )}

      {lokale.data && wszystkich === 0 && (
        <Pusto
          tytul="Nie ma lokali pasujących do filtrów"
          opis={
            Object.keys(filtry).length > 2
              ? 'Wyczyść filtry albo zmień zakres wyszukiwania.'
              : 'Dodaj pierwszy budynek i lokal, żeby zacząć prowadzić rejestr.'
          }
        />
      )}

      {lokale.data && wszystkich > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border bg-background">
            <Table>
              <TableHeader>
                {tabela.getHeaderGroups().map((grupa) => (
                  <TableRow key={grupa.id}>
                    {grupa.headers.map((naglowek) => (
                      <TableHead key={naglowek.id}>
                        {flexRender(
                          naglowek.column.columnDef.header,
                          naglowek.getContext(),
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {tabela.getRowModel().rows.map((wiersz) => (
                  <TableRow
                    key={wiersz.id}
                    tabIndex={0}
                    role="link"
                    className="cursor-pointer focus-visible:outline-2 focus-visible:outline-ring"
                    onClick={() => nawigacja(`/lokale/${wiersz.original.lokal_id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        nawigacja(`/lokale/${wiersz.original.lokal_id}`)
                      }
                    }}
                  >
                    {wiersz.getVisibleCells().map((komorka) => (
                      <TableCell key={komorka.id}>
                        {flexRender(komorka.column.columnDef.cell, komorka.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {wszystkich > NA_STRONIE && (
            <div className="flex justify-center gap-2">
              <button
                type="button"
                className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={offset === 0}
                onClick={() => setFiltry({ ...filtry, offset: Math.max(0, offset - NA_STRONIE) })}
              >
                Poprzednie
              </button>
              <button
                type="button"
                className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={offset + NA_STRONIE >= wszystkich}
                onClick={() => setFiltry({ ...filtry, offset: offset + NA_STRONIE })}
              >
                Następne
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
