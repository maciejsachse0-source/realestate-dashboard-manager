import { useState } from 'react'
import type { StanNaDzien } from '@/api/typy'
import { useSkladniki } from '@/api/zapytania'
import { formatujDate, formatujKwote } from '@/funkcje/format'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { Button } from '@/components/ui/button'
import { FormularzSkladnika } from './Formularze'
import { Karta } from './Wspolne'

/**
 * Składniki opłat i terminy płatności (reguła R3).
 *
 * Każdy składnik ma własny dzień płatności, bo w praktyce prawie nigdy
 * nie są takie same: czynsz do 10-go, eksploatacja do 14-go albo 28-go.
 *
 * Obok dnia umownego pokazujemy faktyczny dzień roboczy. Termin wypadający
 * w niedzielę to nie jest termin.
 */
export function ZakladkaFinanse({
  okresId,
  stan,
}: {
  okresId: number | null
  stan: StanNaDzien | null
}) {
  const skladniki = useSkladniki(okresId)
  const [otwarty, setOtwarty] = useState(false)

  if (okresId === null) {
    return <Pusto tytul="Brak umowy" opis="Bez umowy nie ma składników opłat." />
  }
  if (skladniki.isPending) return <Ladowanie wierszy={3} />
  if (skladniki.isError) {
    return (
      <Blad
        komunikat={
          skladniki.error instanceof Error ? skladniki.error.message : 'Nieznany błąd.'
        }
        ponow={() => void skladniki.refetch()}
      />
    )
  }
  if (skladniki.data.length === 0) {
    return (
      <>
        <Pusto
          tytul="Brak składników opłat"
          opis="Dopóki nie ma żadnego składnika, system nie wie, co i kiedy jest płatne."
          akcja={<Button onClick={() => setOtwarty(true)}>Dodaj składnik</Button>}
        />
        <FormularzSkladnika
          otwarty={otwarty}
          onZamknij={() => setOtwarty(false)}
          okresId={okresId}
        />
      </>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setOtwarty(true)}>Dodaj składnik</Button>
      </div>
      <Karta>
      <table className="w-full text-sm">
        <thead className="border-b text-left text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Składnik</th>
            <th className="px-3 py-2 text-right font-medium">Kwota</th>
            <th className="px-3 py-2 font-medium">Termin umowny</th>
            <th className="px-3 py-2 font-medium">Faktyczny dzień roboczy</th>
            <th className="px-3 py-2 font-medium">Waloryzowany</th>
          </tr>
        </thead>
        <tbody>
          {skladniki.data.map((s) => {
            const wartosc = stan?.parametry[s.klucz_parametru]
            return (
              <tr key={s.id} className="border-b last:border-b-0">
                <td className="px-3 py-2.5">
                  {s.nazwa}
                  {s.sposob_wyliczenia && (
                    <div className="text-xs text-muted-foreground">{s.sposob_wyliczenia}</div>
                  )}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {wartosc?.typ === 'kwota' ? (
                    <>
                      {formatujKwote(wartosc.wartosc, wartosc.waluta ?? 'PLN')}
                      <span className="ml-1 text-xs text-muted-foreground">
                        {wartosc.rodzaj_kwoty}
                      </span>
                    </>
                  ) : (
                    <span className="text-muted-foreground" title="Kwota nie jest zatwierdzona">
                      nieustalona
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {s.dzien_platnosci_miesiaca ? `do ${s.dzien_platnosci_miesiaca}-go` : '—'}
                </td>
                <td className="px-3 py-2.5">
                  {s.dzien_platnosci_roboczy ? formatujDate(s.dzien_platnosci_roboczy) : '—'}
                </td>
                <td className="px-3 py-2.5">{s.czy_waloryzowany ? 'tak' : 'nie'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </Karta>
      <FormularzSkladnika
        otwarty={otwarty}
        onZamknij={() => setOtwarty(false)}
        okresId={okresId}
      />
    </div>
  )
}
