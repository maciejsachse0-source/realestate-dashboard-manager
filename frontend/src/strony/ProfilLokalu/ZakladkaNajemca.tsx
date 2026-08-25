import type { Najemca } from '@/api/typy'
import { Ladowanie, Pusto } from '@/komponenty/Stany'
import { Karta, Pole } from './Wspolne'

/**
 * Dane najemcy: tor B z decyzji D3.
 *
 * Te dane nigdy nie przechodzą przez ekstrakcję z dokumentu. Wprowadza je
 * człowiek i tylko człowiek. Stąd osobna zakładka, a nie wymieszanie
 * z warunkami umowy.
 */
export function ZakladkaNajemca({
  najemca,
  wczytywanie,
}: {
  najemca: Najemca | null
  wczytywanie: boolean
}) {
  if (wczytywanie) return <Ladowanie wierszy={4} />

  if (najemca === null) {
    return (
      <Pusto
        tytul="Brak najemcy"
        opis="Lokal nie ma bieżącej umowy, więc nie ma też przypisanego najemcy."
      />
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Karta tytul="Podmiot">
        <Pole etykieta="Nazwa">{najemca.nazwa_pelna}</Pole>
        <Pole etykieta="Rodzaj">
          {najemca.osoba_fizyczna ? 'osoba fizyczna' : 'podmiot gospodarczy'}
        </Pole>
        <Pole etykieta="NIP">{najemca.nip}</Pole>
        <Pole etykieta="REGON">{najemca.regon}</Pole>
        <Pole etykieta="KRS">{najemca.krs}</Pole>
      </Karta>

      <Karta tytul="Kontakt">
        <Pole etykieta="Adres siedziby">{najemca.adres_siedziby}</Pole>
        <Pole etykieta="Adres do korespondencji">{najemca.adres_korespondencyjny}</Pole>
        <Pole etykieta="E-mail">{najemca.email}</Pole>
        <Pole etykieta="Telefon">{najemca.telefon}</Pole>
      </Karta>

      {najemca.notatki && (
        <Karta tytul="Notatki">
          <p className="whitespace-pre-wrap px-3 py-2.5 text-sm">{najemca.notatki}</p>
        </Karta>
      )}
    </div>
  )
}
