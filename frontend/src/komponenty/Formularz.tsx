import { type ReactNode, useState } from 'react'
import { BladApi } from '@/api/klient'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Wspólna oprawa formularza w oknie modalnym.
 *
 * Trzy rzeczy, które robi za każdym razem tak samo:
 * pokazuje błąd z serwera po polsku, blokuje przycisk na czas zapisu
 * i zamyka się dopiero po udanym zapisie — nigdy przedtem.
 */
export function DialogFormularza({
  otwarty,
  onZamknij,
  tytul,
  opis,
  onZapisz,
  zapisywanie,
  etykietaZapisu = 'Zapisz',
  children,
}: {
  otwarty: boolean
  onZamknij: () => void
  tytul: string
  opis?: string
  onZapisz: () => Promise<unknown>
  zapisywanie: boolean
  etykietaZapisu?: string
  children: ReactNode
}) {
  const [blad, setBlad] = useState<string | null>(null)

  return (
    <Dialog
      open={otwarty}
      onOpenChange={(otwarte) => {
        if (!otwarte) {
          setBlad(null)
          onZamknij()
        }
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{tytul}</DialogTitle>
          {opis && <DialogDescription>{opis}</DialogDescription>}
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={async (zdarzenie) => {
            zdarzenie.preventDefault()
            setBlad(null)
            try {
              await onZapisz()
              onZamknij()
            } catch (e) {
              setBlad(e instanceof BladApi ? e.message : 'Nie udało się zapisać.')
            }
          }}
        >
          {children}

          {blad && (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
            >
              {blad}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onZamknij}>
              Anuluj
            </Button>
            <Button type="submit" disabled={zapisywanie}>
              {zapisywanie ? 'Zapisuję…' : etykietaZapisu}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** Pole tekstowe z etykietą i opcjonalną podpowiedzią. */
export function PoleTekstowe({
  nazwa,
  etykieta,
  wartosc,
  onZmiana,
  typ = 'text',
  wymagane = false,
  podpowiedz,
  ...reszta
}: {
  nazwa: string
  etykieta: string
  wartosc: string
  onZmiana: (wartosc: string) => void
  typ?: string
  wymagane?: boolean
  podpowiedz?: string
} & Omit<React.ComponentProps<typeof Input>, 'value' | 'onChange' | 'name' | 'type'>) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={nazwa}>
        {etykieta}
        {wymagane && <span className="ml-1 text-destructive">*</span>}
      </Label>
      <Input
        id={nazwa}
        name={nazwa}
        type={typ}
        value={wartosc}
        required={wymagane}
        onChange={(e) => onZmiana(e.target.value)}
        {...reszta}
      />
      {podpowiedz && <p className="text-xs text-muted-foreground">{podpowiedz}</p>}
    </div>
  )
}

/** Lista wyboru. Pusta wartość znaczy „nie wybrano", a nie „pierwsza opcja". */
export function PoleWyboru({
  nazwa,
  etykieta,
  wartosc,
  onZmiana,
  opcje,
  wymagane = false,
  pusteEtykieta = '— wybierz —',
  podpowiedz,
}: {
  nazwa: string
  etykieta: string
  wartosc: string
  onZmiana: (wartosc: string) => void
  opcje: { wartosc: string; etykieta: string }[]
  wymagane?: boolean
  pusteEtykieta?: string
  podpowiedz?: string
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={nazwa}>
        {etykieta}
        {wymagane && <span className="ml-1 text-destructive">*</span>}
      </Label>
      <select
        id={nazwa}
        name={nazwa}
        className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
        value={wartosc}
        required={wymagane}
        onChange={(e) => onZmiana(e.target.value)}
      >
        <option value="">{pusteEtykieta}</option>
        {opcje.map((o) => (
          <option key={o.wartosc} value={o.wartosc}>
            {o.etykieta}
          </option>
        ))}
      </select>
      {podpowiedz && <p className="text-xs text-muted-foreground">{podpowiedz}</p>}
    </div>
  )
}

export function PoleZaznaczenia({
  nazwa,
  etykieta,
  wartosc,
  onZmiana,
  podpowiedz,
}: {
  nazwa: string
  etykieta: string
  wartosc: boolean
  onZmiana: (wartosc: boolean) => void
  podpowiedz?: string
}) {
  return (
    <div className="space-y-1">
      <label className="flex items-center gap-2 text-sm">
        <input
          id={nazwa}
          name={nazwa}
          type="checkbox"
          className="size-4"
          checked={wartosc}
          onChange={(e) => onZmiana(e.target.checked)}
        />
        {etykieta}
      </label>
      {podpowiedz && <p className="text-xs text-muted-foreground">{podpowiedz}</p>}
    </div>
  )
}

/** Zamienia pusty tekst na null. API odróżnia „nie podano" od pustego napisu. */
export function pustyNaNull(wartosc: string): string | null {
  const przycięty = wartosc.trim()
  return przycięty === '' ? null : przycięty
}

/** Liczba albo null. Pusty tekst nie może stać się zerem (decyzja D5). */
export function liczbaLubNull(wartosc: string): number | null {
  const przycięty = wartosc.trim()
  if (przycięty === '') return null
  const liczba = Number(przycięty)
  return Number.isFinite(liczba) ? liczba : null
}
