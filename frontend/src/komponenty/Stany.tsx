import { Skeleton } from '@/components/ui/skeleton'

/**
 * Cztery stany widoku danych: ładowanie, pusty, błąd, dane.
 *
 * Reguła z `.claude/rules/frontend.md`: każdy z nich jest zaprojektowany.
 * Stan pusty musi mówić, co zrobić dalej — inaczej użytkownik nie wie,
 * czy filtr jest za wąski, czy w systemie po prostu nic nie ma.
 */

export function Ladowanie({ wierszy = 8 }: { wierszy?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Wczytywanie danych">
      {Array.from({ length: wierszy }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function Pusto({
  tytul,
  opis,
  akcja,
}: {
  tytul: string
  opis: string
  akcja?: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed p-12 text-center">
      <p className="font-medium">{tytul}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{opis}</p>
      {akcja && <div className="mt-4">{akcja}</div>}
    </div>
  )
}

export function Blad({ komunikat, ponow }: { komunikat: string; ponow?: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center"
    >
      <p className="font-medium text-destructive">Nie udało się wczytać danych</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{komunikat}</p>
      {ponow && (
        <button
          type="button"
          onClick={ponow}
          className="mt-4 text-sm font-medium underline underline-offset-4"
        >
          Spróbuj ponownie
        </button>
      )}
    </div>
  )
}
