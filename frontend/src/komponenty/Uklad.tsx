import { Link, NavLink, Outlet } from 'react-router-dom'
import { useProfil, useWylogowanie, useZdarzenia } from '@/api/zapytania'
import { Button } from '@/components/ui/button'

/**
 * Rama aplikacji: nagłówek, nawigacja i licznik alertów.
 *
 * Licznik jest klikalny i prowadzi do kokpitu terminów (koncepcja, sekcja 7.1).
 */
export default function Uklad() {
  const profil = useProfil()
  const wylogowanie = useWylogowanie()
  const zdarzenia = useZdarzenia({ limit: 1, status_zdarzenia: 'otwarte' })

  const otwartych = zdarzenia.data?.wszystkich ?? 0

  return (
    <div className="min-h-dvh bg-muted/20">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-14 max-w-[1800px] items-center gap-6 px-4">
          <Link to="/" className="font-semibold whitespace-nowrap">
            Umowy najmu
          </Link>

          <nav className="flex items-center gap-1 text-sm">
            <Pozycja do="/">Lokale</Pozycja>
            <Pozycja do="/kartoteka">Kartoteka</Pozycja>
            <Pozycja do="/terminy">
              Terminy
              {otwartych > 0 && (
                <span
                  className="ml-2 rounded-full bg-destructive px-1.5 py-0.5 text-xs font-medium text-white"
                  aria-label={`${otwartych} otwartych zdarzeń`}
                >
                  {otwartych}
                </span>
              )}
            </Pozycja>
          </nav>

          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">
              {profil.data?.imie_nazwisko}
              <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
                {profil.data?.rola}
              </span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                wylogowanie.mutate(undefined, {
                  onSuccess: () => window.location.assign('/'),
                })
              }}
            >
              Wyloguj
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1800px] p-4">
        <Outlet />
      </main>
    </div>
  )
}

function Pozycja({ do: adres, children }: { do: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={adres}
      end={adres === '/'}
      className={({ isActive }) =>
        [
          'rounded-md px-3 py-1.5 transition-colors',
          isActive ? 'bg-muted font-medium' : 'text-muted-foreground hover:text-foreground',
        ].join(' ')
      }
    >
      {children}
    </NavLink>
  )
}
