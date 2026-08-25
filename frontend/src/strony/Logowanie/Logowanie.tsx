import { useState } from 'react'
import { useLogowanie, useZmianaHasla } from '@/api/zapytania'
import { BladApi } from '@/api/klient'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Ekran logowania.
 *
 * Po pierwszym logowaniu na koncie założonym przez system pokazuje od razu
 * formularz zmiany hasła. Hasło początkowe jest widoczne w oknie startowym
 * programu, więc musi przestać obowiązywać przy pierwszej okazji.
 */
export default function Logowanie() {
  const [login, setLogin] = useState('')
  const [haslo, setHaslo] = useState('')
  const logowanie = useLogowanie()

  const wymagaZmiany = logowanie.data?.wymaga_zmiany_hasla === true

  if (wymagaZmiany) {
    return <ZmianaHaslaPoczatkowa hasloBiezace={haslo} />
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-muted/30 p-4">
      <form
        className="w-full max-w-sm space-y-5 rounded-xl border bg-card p-8 shadow-sm"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault()
          logowanie.mutate({ login, haslo })
        }}
      >
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">System Zarządzania Umowami Najmu</h1>
          <p className="text-sm text-muted-foreground">Zaloguj się, aby kontynuować.</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="login">Login</Label>
          <Input
            id="login"
            autoFocus
            autoComplete="username"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="haslo">Hasło</Label>
          <Input
            id="haslo"
            type="password"
            autoComplete="current-password"
            value={haslo}
            onChange={(e) => setHaslo(e.target.value)}
            required
          />
        </div>

        {logowanie.isError && (
          <p role="alert" className="text-sm text-destructive">
            {logowanie.error instanceof BladApi
              ? logowanie.error.message
              : 'Nie udało się połączyć z programem. Sprawdź, czy jest uruchomiony.'}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={logowanie.isPending}>
          {logowanie.isPending ? 'Loguję…' : 'Zaloguj'}
        </Button>
      </form>
    </main>
  )
}

function ZmianaHaslaPoczatkowa({ hasloBiezace }: { hasloBiezace: string }) {
  const [nowe, setNowe] = useState('')
  const [powtorzenie, setPowtorzenie] = useState('')
  const zmiana = useZmianaHasla()

  const niezgodne = powtorzenie.length > 0 && nowe !== powtorzenie

  return (
    <main className="flex min-h-dvh items-center justify-center bg-muted/30 p-4">
      <form
        className="w-full max-w-sm space-y-5 rounded-xl border bg-card p-8 shadow-sm"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault()
          if (niezgodne) return
          zmiana.mutate(
            { haslo_biezace: hasloBiezace, haslo_nowe: nowe },
            {
              onSuccess: () => {
                // Zmiana hasła unieważnia sesję po stronie serwera, więc
                // wracamy do logowania z nowym hasłem. To jest zamierzone.
                window.location.reload()
              },
            },
          )
        }}
      >
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Ustaw własne hasło</h1>
          <p className="text-sm text-muted-foreground">
            Hasło początkowe było widoczne w oknie programu, więc trzeba je zmienić.
            Minimum 12 znaków.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="nowe">Nowe hasło</Label>
          <Input
            id="nowe"
            type="password"
            autoFocus
            autoComplete="new-password"
            value={nowe}
            onChange={(e) => setNowe(e.target.value)}
            required
            minLength={12}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="powtorzenie">Powtórz nowe hasło</Label>
          <Input
            id="powtorzenie"
            type="password"
            autoComplete="new-password"
            value={powtorzenie}
            onChange={(e) => setPowtorzenie(e.target.value)}
            required
          />
        </div>

        {niezgodne && (
          <p role="alert" className="text-sm text-destructive">
            Hasła nie są takie same.
          </p>
        )}
        {zmiana.isError && (
          <p role="alert" className="text-sm text-destructive">
            {zmiana.error instanceof BladApi ? zmiana.error.message : 'Nie udało się zmienić hasła.'}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={zmiana.isPending || niezgodne}>
          {zmiana.isPending ? 'Zapisuję…' : 'Zapisz i zaloguj ponownie'}
        </Button>
      </form>
    </main>
  )
}
