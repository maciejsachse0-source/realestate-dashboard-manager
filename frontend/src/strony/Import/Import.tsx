import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Blad, Pusto } from "@/komponenty/Stany";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

/** Pola systemu, na które można zmapować kolumnę arkusza. */
const POLA: { wartosc: string; etykieta: string }[] = [
  { wartosc: "", etykieta: "— pomiń tę kolumnę —" },
  { wartosc: "budynek", etykieta: "Budynek (wymagane)" },
  { wartosc: "lokal", etykieta: "Oznaczenie lokalu (wymagane)" },
  { wartosc: "najemca", etykieta: "Najemca (wymagane)" },
  { wartosc: "typ_lokalu", etykieta: "Typ lokalu" },
  { wartosc: "powierzchnia", etykieta: "Powierzchnia" },
  { wartosc: "nip", etykieta: "NIP" },
  { wartosc: "data_zawarcia", etykieta: "Data zawarcia" },
  { wartosc: "data_przekazania", etykieta: "Data przekazania" },
  { wartosc: "okres_miesiace", etykieta: "Okres najmu (miesiące)" },
  { wartosc: "czynsz", etykieta: "Czynsz" },
  { wartosc: "czynsz_rodzaj", etykieta: "Czynsz netto/brutto" },
  { wartosc: "stawka_vat", etykieta: "Stawka VAT" },
  { wartosc: "dzien_platnosci", etykieta: "Dzień płatności" },
];

/** Podpowiedzi mapowania po nazwie kolumny. Zgadujemy, człowiek poprawia. */
const PODPOWIEDZI: { wzorzec: RegExp; pole: string }[] = [
  { wzorzec: /budyn/i, pole: "budynek" },
  { wzorzec: /lokal|nr lok|numer lok/i, pole: "lokal" },
  { wzorzec: /najemc|firma|klient/i, pole: "najemca" },
  { wzorzec: /\btyp\b|rodzaj lok/i, pole: "typ_lokalu" },
  { wzorzec: /powierzch|metra|m2|m²/i, pole: "powierzchnia" },
  { wzorzec: /nip/i, pole: "nip" },
  { wzorzec: /zawar|podpis/i, pole: "data_zawarcia" },
  { wzorzec: /przekaz|protok/i, pole: "data_przekazania" },
  { wzorzec: /okres|czas trwan|miesi/i, pole: "okres_miesiace" },
  { wzorzec: /vat|stawka pod/i, pole: "stawka_vat" },
  { wzorzec: /netto|brutto/i, pole: "czynsz_rodzaj" },
  { wzorzec: /czynsz|kwota|oplat|opłat/i, pole: "czynsz" },
  { wzorzec: /płatn|platn|termin/i, pole: "dzien_platnosci" },
];

function zgadnijPole(naglowek: string): string {
  // Kolejność ma znaczenie: „czynsz netto" ma trafić w rodzaj kwoty, nie w kwotę,
  // więc wzorzec rodzaju stoi przed wzorcem czynszu.
  for (const { wzorzec, pole } of PODPOWIEDZI) {
    if (wzorzec.test(naglowek)) return pole;
  }
  return "";
}

interface BladWiersza {
  wiersz: number;
  pole: string | null;
  komunikat: string;
  opis: string;
}

interface Podglad {
  naglowki: string[];
  arkusze: string[];
  wierszy_w_pliku: number;
  wierszy_poprawnych: number;
  bledy: BladWiersza[];
  podglad: Record<string, string>[];
  pola_dostepne: string[];
}

interface WynikImportu {
  budynkow_dodanych: number;
  lokali_dodanych: number;
  najemcow_dodanych: number;
  umow_dodanych: number;
  warunkow_dodanych: number;
  skladnikow_dodanych: number;
  wierszy_pominietych: number;
  pominiecia: string[];
}

/**
 * Kreator importu startowego (koncepcja, sekcja 7.4; plan, sekcja E7).
 *
 * Trzy kroki i to jest celowe: wgraj plik, zmapuj kolumny, obejrzyj i zapisz.
 * Nikt nie zapisuje danych, których wcześniej nie zobaczył.
 *
 * Import jest transakcyjny: albo cały plik, albo nic. Arkusz z jednym błędem
 * w trzydziestym wierszu nie zapisze dwudziestu dziewięciu poprawnych.
 */
export default function Import() {
  const kolejka = useQueryClient();
  const [plik, setPlik] = useState<File | null>(null);
  const [mapowanie, setMapowanie] = useState<Record<string, string>>({});
  const [podglad, setPodglad] = useState<Podglad | null>(null);
  const [wynik, setWynik] = useState<WynikImportu | null>(null);
  const [blad, setBlad] = useState<string | null>(null);
  const [bledyImportu, setBledyImportu] = useState<string[]>([]);
  const [pracuje, setPracuje] = useState(false);

  /**
   * Ta strona celowo nie korzysta ze wspólnego klienta z `api/klient.ts`:
   * wysyłka pliku wymaga `FormData`, a klient ustawia `Content-Type` na JSON,
   * co zepsułoby granicę multipart.
   */
  async function wyslij(
    sciezka: string,
    mapa: Record<string, string>,
  ): Promise<Response> {
    const dane = new FormData();
    dane.append("plik", plik as File);
    dane.append("mapowanie", JSON.stringify(mapa));
    return fetch(`/api/v1/import/${sciezka}`, {
      method: "POST",
      body: dane,
      credentials: "same-origin",
    });
  }

  async function wczytajPodglad(mapa: Record<string, string> = mapowanie) {
    if (!plik) return;
    setPracuje(true);
    setBlad(null);
    setBledyImportu([]);
    try {
      const odpowiedz = await wyslij("podglad", mapa);
      const tresc = await odpowiedz.json();
      if (!odpowiedz.ok) {
        setBlad(
          typeof tresc.detail === "string"
            ? tresc.detail
            : "Nie udało się odczytać pliku.",
        );
        setPodglad(null);
        return;
      }
      const dane = tresc as Podglad;
      setPodglad(dane);
      // Pierwsze wejście: zgadujemy mapowanie z nagłówków, żeby człowiek
      // poprawiał, a nie wypełniał od zera.
      if (Object.keys(mapa).length === 0) {
        const zgadniete = Object.fromEntries(
          dane.naglowki.map((n) => [n, zgadnijPole(n)]),
        );
        setMapowanie(zgadniete);
        await wczytajPodglad(zgadniete);
      }
    } catch {
      setBlad("Brak połączenia z programem.");
    } finally {
      setPracuje(false);
    }
  }

  async function zaimportuj() {
    if (!plik) return;
    setPracuje(true);
    setBlad(null);
    setBledyImportu([]);
    try {
      const odpowiedz = await wyslij("wykonaj", mapowanie);
      const tresc = await odpowiedz.json();
      if (!odpowiedz.ok) {
        if (tresc.detail?.bledy) {
          setBlad(tresc.detail.komunikat);
          setBledyImportu(tresc.detail.bledy as string[]);
        } else {
          setBlad(
            typeof tresc.detail === "string"
              ? tresc.detail
              : "Import się nie powiódł.",
          );
        }
        return;
      }
      setWynik(tresc as WynikImportu);
      // Po imporcie wszystko na dashboardzie jest nieaktualne.
      kolejka.clear();
    } catch {
      setBlad("Brak połączenia z programem.");
    } finally {
      setPracuje(false);
    }
  }

  if (wynik) {
    return (
      <Zakonczenie
        wynik={wynik}
        onOdNowa={() => {
          setWynik(null);
          setPlik(null);
          setPodglad(null);
          setMapowanie({});
        }}
      />
    );
  }

  const gotowyDoImportu =
    podglad !== null &&
    podglad.bledy.length === 0 &&
    podglad.wierszy_poprawnych > 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold">Import z arkusza</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Wgraj arkusz, sprawdź, jak system go zrozumiał, a potem zapisz. Import
          zapisuje albo cały plik, albo nic.
        </p>
      </div>

      <section className="space-y-3 rounded-lg border bg-background p-4">
        <div className="space-y-1.5">
          <Label htmlFor="plik">Krok 1: plik XLSX</Label>
          <input
            id="plik"
            type="file"
            accept=".xlsx"
            className="block w-full text-sm file:mr-3 file:rounded-md file:border file:bg-muted file:px-3 file:py-1.5 file:text-sm"
            onChange={(e) => {
              setPlik(e.target.files?.[0] ?? null);
              setPodglad(null);
              setMapowanie({});
              setBlad(null);
              setBledyImportu([]);
            }}
          />
        </div>

        {plik && !podglad && (
          <Button onClick={() => void wczytajPodglad({})} disabled={pracuje}>
            {pracuje ? "Czytam plik…" : "Wczytaj plik"}
          </Button>
        )}
      </section>

      {blad && (
        <div className="space-y-2">
          <Blad komunikat={blad} />
          {bledyImportu.length > 0 && (
            <ul className="max-h-72 space-y-1 overflow-y-auto rounded-lg border bg-background p-3 text-sm">
              {bledyImportu.map((b, i) => (
                <li key={i} className="border-b py-1 last:border-b-0">
                  {b}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {podglad && (
        <>
          <section className="space-y-3 rounded-lg border bg-background p-4">
            <h2 className="text-sm font-medium">
              Krok 2: co jest w której kolumnie
            </h2>
            <p className="text-sm text-muted-foreground">
              System zgadł, na co wskazują nagłówki. Popraw, jeśli się pomylił.
            </p>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {podglad.naglowki.filter(Boolean).map((naglowek) => (
                <div key={naglowek} className="space-y-1">
                  <Label htmlFor={`kol-${naglowek}`} className="text-xs">
                    {naglowek}
                  </Label>
                  <select
                    id={`kol-${naglowek}`}
                    className="h-9 w-full rounded-md border bg-transparent px-2 text-sm"
                    value={mapowanie[naglowek] ?? ""}
                    onChange={(e) => {
                      const nowe = { ...mapowanie, [naglowek]: e.target.value };
                      setMapowanie(nowe);
                      void wczytajPodglad(nowe);
                    }}
                  >
                    {POLA.map((p) => (
                      <option key={p.wartosc} value={p.wartosc}>
                        {p.etykieta}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-medium">
              Krok 3: podgląd ({podglad.wierszy_poprawnych} z{" "}
              {podglad.wierszy_w_pliku} wierszy gotowych)
            </h2>

            {podglad.bledy.length > 0 && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                <p className="text-sm font-medium text-destructive">
                  {podglad.bledy.length === 1
                    ? "Jeden problem do poprawienia w arkuszu:"
                    : `${podglad.bledy.length} problemów do poprawienia w arkuszu:`}
                </p>
                <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
                  {podglad.bledy.map((b, i) => (
                    <li key={i}>{b.opis}</li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">
                  Popraw arkusz i wgraj go ponownie. Dopóki jest choć jeden
                  problem, nic nie zostanie zapisane.
                </p>
              </div>
            )}

            {podglad.podglad.length === 0 ? (
              <Pusto
                tytul="Nic do pokazania"
                opis="Żadna kolumna nie została zmapowana albo plik nie ma wierszy z danymi."
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border bg-background">
                <table className="w-full text-sm">
                  <thead className="border-b text-left text-muted-foreground">
                    <tr>
                      {Object.keys(podglad.podglad[0]).map((pole) => (
                        <th key={pole} className="px-3 py-2 font-medium">
                          {pole}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {podglad.podglad.map((wiersz, i) => (
                      <tr key={i} className="border-b last:border-b-0">
                        {Object.keys(podglad.podglad[0]).map((pole) => (
                          <td key={pole} className="px-3 py-2">
                            {wiersz[pole] ?? "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button
                onClick={() => void zaimportuj()}
                disabled={!gotowyDoImportu || pracuje}
              >
                {pracuje
                  ? "Importuję…"
                  : `Zapisz ${podglad.wierszy_poprawnych} wierszy`}
              </Button>
              {!gotowyDoImportu && podglad.bledy.length > 0 && (
                <span className="text-sm text-muted-foreground">
                  Najpierw popraw problemy wypisane wyżej.
                </span>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Zakonczenie({
  wynik,
  onOdNowa,
}: {
  wynik: WynikImportu;
  onOdNowa: () => void;
}) {
  const pozycje: [string, number][] = [
    ["Budynki", wynik.budynkow_dodanych],
    ["Lokale", wynik.lokali_dodanych],
    ["Najemcy", wynik.najemcow_dodanych],
    ["Umowy", wynik.umow_dodanych],
    ["Warunki (czynsz)", wynik.warunkow_dodanych],
    ["Składniki opłat", wynik.skladnikow_dodanych],
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Import zakończony</h1>

      <div className="rounded-lg border bg-background">
        <table className="w-full text-sm">
          <tbody>
            {pozycje.map(([nazwa, ile]) => (
              <tr key={nazwa} className="border-b last:border-b-0">
                <td className="px-3 py-2 text-muted-foreground">{nazwa}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">
                  {ile}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {wynik.pominiecia.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
          <p className="text-sm font-medium text-amber-900">
            Pominięto {wynik.wierszy_pominietych} wierszy:
          </p>
          <ul className="mt-2 space-y-1 text-sm text-amber-900">
            {wynik.pominiecia.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={onOdNowa}>Importuj kolejny plik</Button>
        <Button variant="outline" onClick={() => window.location.assign("/")}>
          Przejdź do listy lokali
        </Button>
      </div>
    </div>
  );
}
