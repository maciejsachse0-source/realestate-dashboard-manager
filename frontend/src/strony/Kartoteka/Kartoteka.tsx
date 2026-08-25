import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { Budynek, Najemca } from '@/api/typy'
import {
  useBudynki,
  useDodajBudynek,
  useDodajLokal,
  useDodajNajemce,
  useLokale,
  useNajemcy,
  useProfil,
} from '@/api/zapytania'
import { formatujPowierzchnie } from '@/funkcje/format'
import {
  DialogFormularza,
  PoleTekstowe,
  PoleWyboru,
  PoleZaznaczenia,
  liczbaLubNull,
  pustyNaNull,
} from '@/komponenty/Formularz'
import { Blad, Ladowanie, Pusto } from '@/komponenty/Stany'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const TYPY_LOKALU = [
  { wartosc: 'handlowy', etykieta: 'Handlowy' },
  { wartosc: 'biurowy', etykieta: 'Biurowy' },
  { wartosc: 'magazyn', etykieta: 'Magazyn' },
  { wartosc: 'miejsce_postojowe', etykieta: 'Miejsce postojowe' },
  { wartosc: 'inny', etykieta: 'Inny' },
]

/**
 * Kartoteka: budynki, lokale i najemcy.
 *
 * Bez tego ekranu program jest tylko do oglądania. Kolejność zakładek nie jest
 * przypadkowa — bez budynku nie ma lokalu, bez lokalu i najemcy nie ma umowy.
 */
export default function Kartoteka() {
  const [parametry, setParametry] = useSearchParams()
  const profil = useProfil()
  const rola = profil.data?.rola

  const mozeZarzadzac = rola === 'zarzadca' || rola === 'administrator'
  const mozeBudynki = rola === 'administrator'

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Kartoteka</h1>

      <Tabs
        value={parametry.get('zakladka') ?? 'lokale'}
        onValueChange={(w) => setParametry({ zakladka: w }, { replace: true })}
      >
        <TabsList>
          <TabsTrigger value="lokale">Lokale</TabsTrigger>
          <TabsTrigger value="najemcy">Najemcy</TabsTrigger>
          <TabsTrigger value="budynki">Budynki</TabsTrigger>
        </TabsList>

        <div className="mt-4">
          <TabsContent value="lokale">
            <ListaLokali mozeDodawac={mozeZarzadzac} />
          </TabsContent>
          <TabsContent value="najemcy">
            <ListaNajemcow mozeDodawac={mozeZarzadzac} />
          </TabsContent>
          <TabsContent value="budynki">
            <ListaBudynkow mozeDodawac={mozeBudynki} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}

// ----------------------------------------------------------------- budynki

function ListaBudynkow({ mozeDodawac }: { mozeDodawac: boolean }) {
  const budynki = useBudynki()
  const [otwarty, setOtwarty] = useState(false)

  if (budynki.isPending) return <Ladowanie wierszy={3} />
  if (budynki.isError) {
    return (
      <Blad
        komunikat={budynki.error instanceof Error ? budynki.error.message : 'Nieznany błąd.'}
        ponow={() => void budynki.refetch()}
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {mozeDodawac ? (
          <Button onClick={() => setOtwarty(true)}>Dodaj budynek</Button>
        ) : (
          <p className="text-sm text-muted-foreground">
            Kartoteka budynków należy do administratora.
          </p>
        )}
      </div>

      {budynki.data.pozycje.length === 0 ? (
        <Pusto
          tytul="Nie ma jeszcze żadnego budynku"
          opis="Budynek jest pierwszą rzeczą do wprowadzenia. Bez niego nie da się dodać lokalu."
          akcja={mozeDodawac ? <Button onClick={() => setOtwarty(true)}>Dodaj budynek</Button> : undefined}
        />
      ) : (
        <ul className="divide-y rounded-lg border bg-background">
          {budynki.data.pozycje.map((b) => (
            <li key={b.id} className="flex items-center gap-4 px-3 py-2.5 text-sm">
              <span className="font-medium">{b.nazwa}</span>
              <span className="text-muted-foreground">{b.adres ?? '—'}</span>
              {!b.aktywny && <span className="text-xs text-muted-foreground">(nieaktywny)</span>}
            </li>
          ))}
        </ul>
      )}

      <FormularzBudynku otwarty={otwarty} onZamknij={() => setOtwarty(false)} />
    </div>
  )
}

function FormularzBudynku({ otwarty, onZamknij }: { otwarty: boolean; onZamknij: () => void }) {
  const dodaj = useDodajBudynek()
  const [nazwa, setNazwa] = useState('')
  const [adres, setAdres] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setNazwa('')
        setAdres('')
        onZamknij()
      }}
      tytul="Nowy budynek"
      onZapisz={() =>
        dodaj.mutateAsync({ nazwa: nazwa.trim(), adres: pustyNaNull(adres), aktywny: true })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleTekstowe
        nazwa="nazwa"
        etykieta="Nazwa"
        wartosc={nazwa}
        onZmiana={setNazwa}
        wymagane
        podpowiedz="Krótka, taka jakiej używacie na co dzień, na przykład 18A."
      />
      <PoleTekstowe nazwa="adres" etykieta="Adres" wartosc={adres} onZmiana={setAdres} />
    </DialogFormularza>
  )
}

// ------------------------------------------------------------------ lokale

function ListaLokali({ mozeDodawac }: { mozeDodawac: boolean }) {
  const lokale = useLokale({ limit: 500 })
  const budynki = useBudynki()
  const [otwarty, setOtwarty] = useState(false)

  if (lokale.isPending) return <Ladowanie wierszy={4} />
  if (lokale.isError) {
    return (
      <Blad
        komunikat={lokale.error instanceof Error ? lokale.error.message : 'Nieznany błąd.'}
        ponow={() => void lokale.refetch()}
      />
    )
  }

  const brakBudynkow = (budynki.data?.pozycje.length ?? 0) === 0

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {mozeDodawac && (
          <Button onClick={() => setOtwarty(true)} disabled={brakBudynkow}>
            Dodaj lokal
          </Button>
        )}
      </div>

      {brakBudynkow && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Najpierw dodaj budynek — lokal musi do czegoś należeć.
        </p>
      )}

      {lokale.data.pozycje.length === 0 ? (
        <Pusto
          tytul="Nie ma jeszcze żadnego lokalu"
          opis="Lokal jest bytem centralnym systemu. Umowy i najemcy się zmieniają, lokal trwa."
        />
      ) : (
        <ul className="divide-y rounded-lg border bg-background">
          {lokale.data.pozycje.map((l) => (
            <li key={l.lokal_id} className="flex flex-wrap items-center gap-4 px-3 py-2.5 text-sm">
              <span className="w-28 font-medium">{l.oznaczenie}</span>
              <span className="w-20 text-muted-foreground">{l.budynek_nazwa}</span>
              <span className="w-28 text-muted-foreground">{l.typ}</span>
              <span className="w-28 text-right tabular-nums text-muted-foreground">
                {l.powierzchnia_ewidencyjna
                  ? formatujPowierzchnie(l.powierzchnia_ewidencyjna)
                  : '—'}
              </span>
              <span className="text-muted-foreground">{l.najemca_nazwa ?? 'bez najemcy'}</span>
            </li>
          ))}
        </ul>
      )}

      <FormularzLokalu
        otwarty={otwarty}
        onZamknij={() => setOtwarty(false)}
        budynki={budynki.data?.pozycje ?? []}
      />
    </div>
  )
}

function FormularzLokalu({
  otwarty,
  onZamknij,
  budynki,
}: {
  otwarty: boolean
  onZamknij: () => void
  budynki: Budynek[]
}) {
  const dodaj = useDodajLokal()
  const [budynekId, setBudynekId] = useState('')
  const [oznaczenie, setOznaczenie] = useState('')
  const [typ, setTyp] = useState('')
  const [kondygnacja, setKondygnacja] = useState('')
  const [powierzchnia, setPowierzchnia] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setOznaczenie('')
        setKondygnacja('')
        setPowierzchnia('')
        onZamknij()
      }}
      tytul="Nowy lokal"
      onZapisz={() =>
        dodaj.mutateAsync({
          budynek_id: Number(budynekId),
          oznaczenie: oznaczenie.trim(),
          typ,
          status: 'wolny',
          kondygnacja: pustyNaNull(kondygnacja),
          powierzchnia_ewidencyjna: liczbaLubNull(powierzchnia),
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleWyboru
        nazwa="budynek"
        etykieta="Budynek"
        wartosc={budynekId}
        onZmiana={setBudynekId}
        wymagane
        opcje={budynki.map((b) => ({ wartosc: String(b.id), etykieta: b.nazwa }))}
      />
      <PoleTekstowe
        nazwa="oznaczenie"
        etykieta="Oznaczenie"
        wartosc={oznaczenie}
        onZmiana={setOznaczenie}
        wymagane
        podpowiedz="Tak, jak lokal jest nazywany w umowach, na przykład 18A/12."
      />
      <PoleWyboru nazwa="typ" etykieta="Typ" wartosc={typ} onZmiana={setTyp} wymagane opcje={TYPY_LOKALU} />
      <PoleTekstowe
        nazwa="kondygnacja"
        etykieta="Kondygnacja"
        wartosc={kondygnacja}
        onZmiana={setKondygnacja}
      />
      <PoleTekstowe
        nazwa="powierzchnia"
        etykieta="Powierzchnia z ewidencji (m²)"
        typ="number"
        step="0.01"
        min="0"
        wartosc={powierzchnia}
        onZmiana={setPowierzchnia}
        podpowiedz="Powierzchnia z umowy bywa inna. Tę drugą wprowadza się jako warunek umowy."
      />
    </DialogFormularza>
  )
}

// ----------------------------------------------------------------- najemcy

function ListaNajemcow({ mozeDodawac }: { mozeDodawac: boolean }) {
  const najemcy = useNajemcy()
  const [otwarty, setOtwarty] = useState(false)

  if (najemcy.isPending) return <Ladowanie wierszy={3} />
  if (najemcy.isError) {
    return (
      <Blad
        komunikat={najemcy.error instanceof Error ? najemcy.error.message : 'Nieznany błąd.'}
        ponow={() => void najemcy.refetch()}
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {mozeDodawac && <Button onClick={() => setOtwarty(true)}>Dodaj najemcę</Button>}
      </div>

      {najemcy.data.pozycje.length === 0 ? (
        <Pusto
          tytul="Nie ma jeszcze żadnego najemcy"
          opis="Dane najemcy wprowadza człowiek i nigdy nie przechodzą przez ekstrakcję z dokumentu."
        />
      ) : (
        <ul className="divide-y rounded-lg border bg-background">
          {najemcy.data.pozycje.map((n: Najemca) => (
            <li key={n.id} className="flex flex-wrap items-center gap-4 px-3 py-2.5 text-sm">
              <span className="min-w-64 font-medium">{n.nazwa_pelna}</span>
              <span className="text-muted-foreground">{n.nip ? `NIP ${n.nip}` : '—'}</span>
              <span className="text-muted-foreground">{n.email ?? ''}</span>
            </li>
          ))}
        </ul>
      )}

      <FormularzNajemcy otwarty={otwarty} onZamknij={() => setOtwarty(false)} />
    </div>
  )
}

function FormularzNajemcy({ otwarty, onZamknij }: { otwarty: boolean; onZamknij: () => void }) {
  const dodaj = useDodajNajemce()
  const [nazwa, setNazwa] = useState('')
  const [nip, setNip] = useState('')
  const [osobaFizyczna, setOsobaFizyczna] = useState(false)
  const [adres, setAdres] = useState('')
  const [email, setEmail] = useState('')
  const [telefon, setTelefon] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setNazwa('')
        setNip('')
        setAdres('')
        setEmail('')
        setTelefon('')
        onZamknij()
      }}
      tytul="Nowy najemca"
      opis="Dane poufne. Wprowadza je człowiek, nigdy ekstrakcja z dokumentu."
      onZapisz={() =>
        dodaj.mutateAsync({
          nazwa_pelna: nazwa.trim(),
          nip: pustyNaNull(nip),
          osoba_fizyczna: osobaFizyczna,
          adres_siedziby: pustyNaNull(adres),
          email: pustyNaNull(email),
          telefon: pustyNaNull(telefon),
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleTekstowe
        nazwa="nazwa_pelna"
        etykieta="Nazwa lub imię i nazwisko"
        wartosc={nazwa}
        onZmiana={setNazwa}
        wymagane
      />
      <PoleZaznaczenia
        nazwa="osoba_fizyczna"
        etykieta="To osoba fizyczna"
        wartosc={osobaFizyczna}
        onZmiana={setOsobaFizyczna}
        podpowiedz="Wpływa na zakres obowiązków wynikających z RODO."
      />
      <PoleTekstowe nazwa="nip" etykieta="NIP" wartosc={nip} onZmiana={setNip} />
      <PoleTekstowe
        nazwa="adres_siedziby"
        etykieta="Adres siedziby"
        wartosc={adres}
        onZmiana={setAdres}
      />
      <PoleTekstowe nazwa="email" etykieta="E-mail" typ="email" wartosc={email} onZmiana={setEmail} />
      <PoleTekstowe nazwa="telefon" etykieta="Telefon" wartosc={telefon} onZmiana={setTelefon} />
    </DialogFormularza>
  )
}
