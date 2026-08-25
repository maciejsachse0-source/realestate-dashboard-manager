import { useEffect, useState } from 'react'
import type { FiltryLokali } from '@/api/typy'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/** Ile milisekund czekamy, zanim wyszukiwarka uderzy w API. */
const OPOZNIENIE_SZUKANIA = 300

interface Props {
  filtry: FiltryLokali
  budynki: { id: number; nazwa: string }[]
  onZmiana: (filtry: FiltryLokali) => void
}

/**
 * Panel filtrow dashboardu (koncepcja, sekcja 7.1).
 *
 * Kazda zmiana filtru zeruje offset. Bez tego uzytkownik na trzeciej stronie
 * zawezalby wynik i ladowal na pustej liscie, mimo ze wyniki sa.
 */
export function PanelFiltrow({ filtry, budynki, onZmiana }: Props) {
  const [szukaj, setSzukaj] = useState(filtry.szukaj ?? '')

  useEffect(() => {
    const licznik = setTimeout(() => {
      if ((filtry.szukaj ?? '') !== szukaj) {
        onZmiana({ ...filtry, szukaj: szukaj || undefined, offset: 0 })
      }
    }, OPOZNIENIE_SZUKANIA)
    return () => clearTimeout(licznik)
  }, [szukaj, filtry, onZmiana])

  function ustaw(zmiana: Partial<FiltryLokali>) {
    onZmiana({ ...filtry, ...zmiana, offset: 0 })
  }

  const aktywne = Object.entries(filtry).filter(
    ([klucz, wartosc]) =>
      !['limit', 'offset', 'sortuj', 'malejaco'].includes(klucz) && wartosc !== undefined,
  ).length

  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="grid gap-4 md:grid-cols-4">
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="szukaj">Szukaj</Label>
          <Input
            id="szukaj"
            placeholder="Oznaczenie lokalu, budynek albo nazwa najemcy"
            value={szukaj}
            onChange={(e) => setSzukaj(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="budynek">Budynek</Label>
          <select
            id="budynek"
            className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
            value={filtry.budynek_id ?? ''}
            onChange={(e) =>
              ustaw({ budynek_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Wszystkie</option>
            {budynki.map((b) => (
              <option key={b.id} value={b.id}>
                {b.nazwa}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="status">Status umowy</Label>
          <select
            id="status"
            className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
            value={filtry.status_umowy ?? ''}
            onChange={(e) =>
              ustaw({
                status_umowy: (e.target.value || undefined) as FiltryLokali['status_umowy'],
              })
            }
          >
            <option value="">Wszystkie</option>
            <option value="aktywna">Aktywna</option>
            <option value="przygotowanie">W przygotowaniu</option>
            <option value="wypowiedziana">Wypowiedziana</option>
            <option value="zakonczona">Zakończona</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="koniec_od">Koniec umowy od</Label>
          <Input
            id="koniec_od"
            type="date"
            value={filtry.koniec_od ?? ''}
            onChange={(e) => ustaw({ koniec_od: e.target.value || undefined })}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="koniec_do">Koniec umowy do</Label>
          <Input
            id="koniec_do"
            type="date"
            value={filtry.koniec_do ?? ''}
            onChange={(e) => ustaw({ koniec_do: e.target.value || undefined })}
          />
        </div>

        <div className="flex items-end gap-4 md:col-span-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4"
              checked={filtry.waloryzacja === true}
              onChange={(e) => ustaw({ waloryzacja: e.target.checked ? true : undefined })}
            />
            Tylko z waloryzacją
          </label>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4"
              checked={filtry.niekompletne === true}
              onChange={(e) => ustaw({ niekompletne: e.target.checked ? true : undefined })}
            />
            Tylko niekompletne
          </label>

          {aktywne > 0 && (
            <button
              type="button"
              className="ml-auto text-sm underline underline-offset-4"
              onClick={() => {
                setSzukaj('')
                onZmiana({ limit: filtry.limit, offset: 0 })
              }}
            >
              Wyczyść filtry ({aktywne})
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
