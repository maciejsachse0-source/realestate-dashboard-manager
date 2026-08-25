import { useQuery } from '@tanstack/react-query'
import { pobierz, type Zdrowie } from './api/klient'

/**
 * Etap E0: ekran diagnostyczny, nie interfejs uzytkownika.
 * Potwierdza, ze przegladarka, serwer WWW, API i baza sa polaczone.
 * Prawdziwe ekrany przychodza od etapu E5.
 */
export default function App() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['zdrowie'],
    queryFn: () => pobierz<Zdrowie>('/health'),
    refetchInterval: 10_000,
  })

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">System Zarządzania Umowami Najmu</h1>
      <p className="mt-1 text-sm text-gray-500">Etap E0: fundament. Ekrany budujemy od E5.</p>

      <section className="mt-8 rounded-lg border p-5">
        <h2 className="text-sm font-medium uppercase tracking-wide text-gray-500">Stan systemu</h2>

        {isPending && <p className="mt-3">Sprawdzam…</p>}

        {isError && (
          <p className="mt-3 text-red-600">
            Brak połączenia z serwerem aplikacji. Sprawdź, czy program jest uruchomiony.
          </p>
        )}

        {data && (
          <dl className="mt-3 grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
            <dt className="text-gray-500">Aplikacja</dt>
            <dd>{data.status === 'ok' ? 'działa' : 'działa z ograniczeniami'}</dd>

            <dt className="text-gray-500">Środowisko</dt>
            <dd>{data.srodowisko}</dd>

            <dt className="text-gray-500">Baza danych</dt>
            <dd>
              {data.baza.polaczona ? (
                (data.baza.wersja ?? 'połączona')
              ) : (
                <span className="text-red-600">niedostępna: {data.baza.blad}</span>
              )}
            </dd>
          </dl>
        )}
      </section>
    </main>
  )
}
