import { Fragment, useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { Budynek, LokalNaLiscie, Najemca } from "@/api/typy";
import {
  useBudynki,
  useDodajBudynek,
  useDodajLokal,
  useDodajNajemce,
  useLokale,
  useNajemcy,
} from "@/api/zapytania";
import { formatujPowierzchnie } from "@/funkcje/format";
import {
  DialogFormularza,
  PoleTekstowe,
  PoleWyboru,
  PoleZaznaczenia,
  liczbaLubNull,
  pustyNaNull,
} from "@/komponenty/Formularz";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ETYKIETY_TYPU: Record<string, string> = {
  handlowy: "Handlowy",
  biurowy: "Biurowy",
  magazyn: "Magazyn",
  miejsce_postojowe: "Miejsce postojowe",
  inny: "Inny",
};

const ETYKIETY_STATUSU: Record<string, string> = {
  wolny: "Wolny",
  wynajety: "Wynajęty",
  w_trakcie_wydania: "W trakcie wydania",
};

/** Sortowanie po polsku, z liczbami w kolejnosci naturalnej: 2 przed 10. */
function porownaj(a: string, b: string): number {
  return a.localeCompare(b, "pl", { numeric: true, sensitivity: "base" });
}

/** Ta sama lista, co w tabeli. Dwie kopie rozjechalyby sie po pierwszej zmianie. */
const TYPY_LOKALU = Object.entries(ETYKIETY_TYPU).map(
  ([wartosc, etykieta]) => ({
    wartosc,
    etykieta,
  }),
);

/**
 * Kartoteka: budynki, lokale i najemcy.
 *
 * Bez tego ekranu program jest tylko do oglądania. Kolejność zakładek nie jest
 * przypadkowa — bez budynku nie ma lokalu, bez lokalu i najemcy nie ma umowy.
 */
export default function Kartoteka() {
  const [parametry, setParametry] = useSearchParams();
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Kartoteka</h1>

      <Tabs
        value={parametry.get("zakladka") ?? "lokale"}
        onValueChange={(w) => setParametry({ zakladka: w }, { replace: true })}
      >
        <TabsList>
          <TabsTrigger value="lokale">Lokale</TabsTrigger>
          <TabsTrigger value="najemcy">Najemcy</TabsTrigger>
        </TabsList>

        <div className="mt-4">
          <TabsContent value="lokale">
            <ListaLokali />
          </TabsContent>
          <TabsContent value="najemcy">
            <ListaNajemcow />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

// -------------------------------------------------- budynki wraz z lokalami

/**
 * Jedna tabela, pogrupowana budynkami.
 *
 * Wczesniej budynki mialy wlasna zakladke i zeby zobaczyc rzecz oczywista —
 * co jest w ktorym budynku — trzeba bylo skakac miedzy widokami. Budynek jest
 * naglowkiem, nie osobna lista.
 */
function ListaLokali() {
  const lokale = useLokale({ limit: 500 });
  const budynki = useBudynki();
  const [otwartyLokal, setOtwartyLokal] = useState(false);
  const [otwartyBudynek, setOtwartyBudynek] = useState(false);

  if (lokale.isPending || budynki.isPending) return <Ladowanie wierszy={4} />;
  if (lokale.isError) {
    return (
      <Blad
        komunikat={
          lokale.error instanceof Error
            ? lokale.error.message
            : "Nieznany błąd."
        }
        ponow={() => void lokale.refetch()}
      />
    );
  }
  if (budynki.isError) {
    return (
      <Blad
        komunikat={
          budynki.error instanceof Error
            ? budynki.error.message
            : "Nieznany błąd."
        }
        ponow={() => void budynki.refetch()}
      />
    );
  }

  const listaBudynkow = [...budynki.data.pozycje].sort((a, b) =>
    porownaj(a.nazwa, b.nazwa),
  );
  const brakBudynkow = listaBudynkow.length === 0;

  // Budynek bez lokali tez musi byc widoczny, inaczej wyglada na nieistniejacy.
  const wedlugBudynku = new Map<number, LokalNaLiscie[]>(
    listaBudynkow.map((b) => [b.id, []]),
  );
  for (const l of lokale.data.pozycje) {
    wedlugBudynku.get(l.budynek_id)?.push(l);
  }
  for (const grupa of wedlugBudynku.values()) {
    grupa.sort((a, b) => porownaj(a.oznaczenie, b.oznaczenie));
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => setOtwartyBudynek(true)}>
          Dodaj budynek
        </Button>
        <Button onClick={() => setOtwartyLokal(true)} disabled={brakBudynkow}>
          Dodaj lokal
        </Button>
      </div>

      {brakBudynkow ? (
        <Pusto
          tytul="Nie ma jeszcze żadnego budynku"
          opis="Budynek jest pierwszą rzeczą do wprowadzenia. Bez niego nie da się dodać lokalu."
          akcja={
            <Button onClick={() => setOtwartyBudynek(true)}>
              Dodaj budynek
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-background">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-40">Lokal</TableHead>
                <TableHead className="w-36">Typ</TableHead>
                <TableHead className="w-36 text-right">Powierzchnia</TableHead>
                <TableHead>Najemca</TableHead>
                <TableHead className="w-40">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {listaBudynkow.map((b) => {
                const grupa = wedlugBudynku.get(b.id) ?? [];
                return (
                  <Fragment key={b.id}>
                    {/*
                      Nagłówek budynku musi być widoczny na pierwszy rzut oka,
                      bo to on dzieli tę tabelę na sekcje. Stąd ciemne tło,
                      pionowy pasek z lewej i wersaliki: przy przewijaniu długiej
                      listy oko ma zaczepienie, którego zwykły pogrubiony wiersz
                      nie dawał.
                    */}
                    <TableRow className="border-y-2 border-border bg-foreground/[0.06] hover:bg-foreground/[0.06]">
                      <TableCell colSpan={5} className="py-3">
                        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-l-4 border-foreground/40 pl-3">
                          <span className="text-sm font-bold tracking-wider uppercase">
                            {b.nazwa}
                          </span>
                          {b.adres && (
                            <span className="text-xs text-muted-foreground">
                              {b.adres}
                            </span>
                          )}
                          <span className="ml-auto rounded-full bg-background px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
                            {grupa.length === 0
                              ? "bez lokali"
                              : `lokali: ${grupa.length}`}
                          </span>
                          {!b.aktywny && (
                            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                              nieaktywny
                            </span>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {grupa.map((l) => (
                      <TableRow key={l.lokal_id}>
                        <TableCell className="font-medium">
                          {l.oznaczenie}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {ETYKIETY_TYPU[l.typ] ?? l.typ}
                        </TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {l.powierzchnia_ewidencyjna
                            ? formatujPowierzchnie(l.powierzchnia_ewidencyjna)
                            : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {l.najemca_nazwa ?? "bez najemcy"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {ETYKIETY_STATUSU[l.status_lokalu] ?? l.status_lokalu}
                        </TableCell>
                      </TableRow>
                    ))}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <FormularzBudynku
        otwarty={otwartyBudynek}
        onZamknij={() => setOtwartyBudynek(false)}
      />
      <FormularzLokalu
        otwarty={otwartyLokal}
        onZamknij={() => setOtwartyLokal(false)}
        budynki={listaBudynkow}
      />
    </div>
  );
}

function FormularzBudynku({
  otwarty,
  onZamknij,
}: {
  otwarty: boolean;
  onZamknij: () => void;
}) {
  const dodaj = useDodajBudynek();
  const [nazwa, setNazwa] = useState("");
  const [nazwaFolderu, setNazwaFolderu] = useState("");
  const [adres, setAdres] = useState("");

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setNazwa("");
        setNazwaFolderu("");
        setAdres("");
        onZamknij();
      }}
      tytul="Nowy budynek"
      onZapisz={() =>
        dodaj.mutateAsync({
          nazwa: nazwa.trim(),
          // Puste znaczy „folder nazywa się tak samo jak budynek".
          nazwa_folderu: pustyNaNull(nazwaFolderu),
          adres: pustyNaNull(adres),
          aktywny: true,
        })
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
      {/*
        Bez tego pola nazwa budynku musiałaby być kopią nazwy katalogu na dysku
        — czyli o wyglądzie kartoteki decydowałby układ folderów. Puste znaczy
        „folder nazywa się tak samo", a to najczęstszy przypadek.
      */}
      <PoleTekstowe
        nazwa="nazwa_folderu"
        etykieta="Folder na dysku"
        wartosc={nazwaFolderu}
        onZmiana={setNazwaFolderu}
        podpowiedz="Wypełnij tylko wtedy, gdy katalog nazywa się inaczej niż budynek."
      />
      <PoleTekstowe
        nazwa="adres"
        etykieta="Adres"
        wartosc={adres}
        onZmiana={setAdres}
      />
    </DialogFormularza>
  );
}

function FormularzLokalu({
  otwarty,
  onZamknij,
  budynki,
}: {
  otwarty: boolean;
  onZamknij: () => void;
  budynki: Budynek[];
}) {
  const dodaj = useDodajLokal();
  const [budynekId, setBudynekId] = useState("");
  const [oznaczenie, setOznaczenie] = useState("");
  const [typ, setTyp] = useState("");
  const [powierzchnia, setPowierzchnia] = useState("");

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setOznaczenie("");
        setPowierzchnia("");
        onZamknij();
      }}
      tytul="Nowy lokal"
      onZapisz={() =>
        dodaj.mutateAsync({
          budynek_id: Number(budynekId),
          oznaczenie: oznaczenie.trim(),
          typ,
          status: "wolny",
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
        opcje={budynki.map((b) => ({
          wartosc: String(b.id),
          etykieta: b.nazwa,
        }))}
      />
      <PoleTekstowe
        nazwa="oznaczenie"
        etykieta="Oznaczenie"
        wartosc={oznaczenie}
        onZmiana={setOznaczenie}
        wymagane
        podpowiedz="Tak, jak lokal jest nazywany w umowach, na przykład 18A/12."
      />
      <PoleWyboru
        nazwa="typ"
        etykieta="Typ"
        wartosc={typ}
        onZmiana={setTyp}
        wymagane
        opcje={TYPY_LOKALU}
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
  );
}

// ----------------------------------------------------------------- najemcy

function ListaNajemcow() {
  const najemcy = useNajemcy();
  const [otwarty, setOtwarty] = useState(false);

  if (najemcy.isPending) return <Ladowanie wierszy={3} />;
  if (najemcy.isError) {
    return (
      <Blad
        komunikat={
          najemcy.error instanceof Error
            ? najemcy.error.message
            : "Nieznany błąd."
        }
        ponow={() => void najemcy.refetch()}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setOtwarty(true)}>Dodaj najemcę</Button>
      </div>

      {najemcy.data.pozycje.length === 0 ? (
        <Pusto
          tytul="Nie ma jeszcze żadnego najemcy"
          opis="Dane najemcy wprowadza człowiek i nigdy nie przechodzą przez ekstrakcję z dokumentu."
        />
      ) : (
        <ul className="divide-y rounded-lg border bg-background">
          {najemcy.data.pozycje.map((n: Najemca) => (
            <li
              key={n.id}
              className="flex flex-wrap items-center gap-4 px-3 py-2.5 text-sm"
            >
              <span className="min-w-64 font-medium">{n.nazwa_pelna}</span>
              <span className="text-muted-foreground">
                {n.nip ? `NIP ${n.nip}` : "—"}
              </span>
              <span className="text-muted-foreground">{n.email ?? ""}</span>
            </li>
          ))}
        </ul>
      )}

      <FormularzNajemcy otwarty={otwarty} onZamknij={() => setOtwarty(false)} />
    </div>
  );
}

function FormularzNajemcy({
  otwarty,
  onZamknij,
}: {
  otwarty: boolean;
  onZamknij: () => void;
}) {
  const dodaj = useDodajNajemce();
  const [nazwa, setNazwa] = useState("");
  const [nip, setNip] = useState("");
  const [osobaFizyczna, setOsobaFizyczna] = useState(false);
  const [adres, setAdres] = useState("");
  const [email, setEmail] = useState("");
  const [telefon, setTelefon] = useState("");

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={() => {
        setNazwa("");
        setNip("");
        setAdres("");
        setEmail("");
        setTelefon("");
        onZamknij();
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
      <PoleTekstowe
        nazwa="nip"
        etykieta="NIP"
        wartosc={nip}
        onZmiana={setNip}
      />
      <PoleTekstowe
        nazwa="adres_siedziby"
        etykieta="Adres siedziby"
        wartosc={adres}
        onZmiana={setAdres}
      />
      <PoleTekstowe
        nazwa="email"
        etykieta="E-mail"
        typ="email"
        wartosc={email}
        onZmiana={setEmail}
      />
      <PoleTekstowe
        nazwa="telefon"
        etykieta="Telefon"
        wartosc={telefon}
        onZmiana={setTelefon}
      />
    </DialogFormularza>
  );
}
