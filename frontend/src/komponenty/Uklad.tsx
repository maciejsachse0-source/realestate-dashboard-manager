import { Link, NavLink, Outlet } from "react-router-dom";
import { useZdarzenia } from "@/api/zapytania";

/**
 * Rama aplikacji: nagłówek, nawigacja i licznik alertów.
 *
 * Licznik jest klikalny i prowadzi do kokpitu terminów (koncepcja, sekcja 7.1).
 */
export default function Uklad() {
  const zdarzenia = useZdarzenia({ limit: 1, status_zdarzenia: "otwarte" });

  const otwartych = zdarzenia.data?.wszystkich ?? 0;

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
            <Pozycja do="/waloryzacja">Waloryzacja</Pozycja>
            <Pozycja do="/dokumenty-z-dysku">Dokumenty z dysku</Pozycja>
            <Pozycja do="/import">Import</Pozycja>
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
        </div>
      </header>

      <main className="mx-auto max-w-[1800px] p-4">
        <Outlet />
      </main>
    </div>
  );
}

function Pozycja({
  do: adres,
  children,
}: {
  do: string;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={adres}
      end={adres === "/"}
      className={({ isActive }) =>
        [
          "rounded-md px-3 py-1.5 transition-colors",
          isActive
            ? "bg-muted font-medium"
            : "text-muted-foreground hover:text-foreground",
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}
