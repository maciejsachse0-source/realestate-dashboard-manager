import { useState } from "react";

import type { FolderZeSkanu, PlikZeSkanu } from "@/api/typy";
import {
  useCofnijPominiecie,
  useKatalogSkanu,
  useLokale,
  useOdepnijFolder,
  usePominPlik,
  usePowiazFolder,
  usePrzegladLinkow,
  useSkan,
  useUstawKatalogSkanu,
  useZaimportujZDysku,
} from "@/api/zapytania";
import { formatujRozmiar } from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import JakToDziala from "./JakToDziala";

const TYPY: { wartosc: string; etykieta: string }[] = [
  { wartosc: "", etykieta: "— wybierz rodzaj —" },
  { wartosc: "umowa", etykieta: "Umowa" },
  { wartosc: "aneks", etykieta: "Aneks" },
  { wartosc: "protokol_przekazania", etykieta: "Protokół przekazania" },
  { wartosc: "protokol_zdawczy", etykieta: "Protokół zdawczy" },
  { wartosc: "polisa", etykieta: "Polisa" },
  { wartosc: "protokol_przegladu", etykieta: "Protokół z przeglądu" },
  { wartosc: "wypowiedzenie", etykieta: "Wypowiedzenie" },
  { wartosc: "inne", etykieta: "Inne" },
];

/** Co człowiek wpisał przy jednym pliku, zanim nacisnął „Dodaj". */
interface Wpis {
  typ: string;
  numer: string;
  data: string;
}

/**
 * Dokumenty z dysku (skan folderów).
 *
 * Program zagląda do gotowego drzewa katalogów na dysku i pokazuje, co w nim
 * jest, a czego jeszcze nie ma w systemie. Trzy zasady, na których stoi
 * ten ekran:
 *
 * 1. Pliki są **linkowane, nie kopiowane**. Zostają tam, gdzie leżą.
 *    Cena: przeniesienie albo przemianowanie pliku zrywa odnośnik, dlatego
 *    jest przycisk „Sprawdź odnośniki", a kopia zapasowa musi obejmować
 *    bazę razem z katalogiem dokumentów.
 * 2. Oznaczeń lokali z nazw folderów **nie parsujemy**. Są nieregularne,
 *    a cicha pomyłka byłaby gorsza niż jedno kliknięcie: folder z umową
 *    paruje człowiek raz, a system to pamięta (decyzja D5).
 * 3. Nic nie importuje się samo. Typ dokumentu jest propozycją z nazwy pliku,
 *    a datę do etapu E9 wpisuje człowiek (decyzja D4).
 *
 * Zakładka „Jak to działa" opisuje ten mechanizm człowiekowi. Jest osobno od
 * listy plików, ale w tym samym miejscu, bo pytanie „skąd program wie, że to
 * aneks" pada przy pierwszym spojrzeniu na tę listę, a nie w dokumentacji.
 */
export default function Skan() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Dokumenty z dysku</h1>

      <Tabs defaultValue="pliki">
        <TabsList>
          <TabsTrigger value="pliki">Pliki</TabsTrigger>
          <TabsTrigger value="jak-to-dziala">Jak to działa</TabsTrigger>
        </TabsList>
        <TabsContent value="pliki" className="mt-2">
          <Pliki />
        </TabsContent>
        <TabsContent value="jak-to-dziala" className="mt-2">
          <JakToDziala />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** Co leży na dysku, czego jeszcze nie ma w systemie i co z tym zrobić. */
function Pliki() {
  const skan = useSkan();
  const [sprawdzam, setSprawdzam] = useState(false);
  const przeglad = usePrzegladLinkow(sprawdzam);

  if (skan.isPending) return <Ladowanie wierszy={6} />;
  if (skan.isError) {
    return (
      <Blad
        komunikat={
          skan.error instanceof Error ? skan.error.message : "Nieznany błąd."
        }
        ponow={() => void skan.refetch()}
      />
    );
  }

  const dane = skan.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <UstawienieKatalogu />
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setSprawdzam(true);
              void przeglad.refetch();
            }}
          >
            Sprawdź odnośniki
          </Button>
          <Button
            onClick={() => void skan.refetch()}
            disabled={skan.isFetching}
          >
            {skan.isFetching ? "Skanuję…" : "Skanuj ponownie"}
          </Button>
        </div>
      </div>

      {!dane.dostepny && (
        <Pusto
          tytul="Nie ma czego skanować"
          opis={
            dane.komunikat ??
            "Katalog z dokumentami jest niedostępny. Wskaż go w polu na górze ekranu."
          }
        />
      )}

      {sprawdzam && przeglad.data && (
        <PrzegladOdnosnikow dane={przeglad.data} />
      )}

      {dane.dostepny && (
        <p className="text-sm text-muted-foreground">
          {dane.nowych === 0
            ? "Wszystkie znalezione pliki są już w systemie albo zostały pominięte."
            : `Nowych plików do rozpatrzenia: ${dane.nowych}.`}
          {dane.obcietych > 0 &&
            ` Lista została ucięta — ${dane.obcietych} plików nie zmieściło się w tym przebiegu.`}
          {dane.niedostepnych > 0 &&
            ` ${dane.niedostepnych} katalogów lub plików system odmówił udostępnić — te pozycje nie są tu widoczne.`}
        </p>
      )}

      {dane.budynki.map((budynek) => (
        <section key={budynek.nazwa_folderu} className="space-y-3">
          <h2 className="flex items-baseline gap-2 border-b pb-1 font-medium">
            {budynek.nazwa_folderu}
            {budynek.budynek_id === null ? (
              <span className="text-sm font-normal text-muted-foreground">
                — tego budynku nie ma w kartotece
              </span>
            ) : (
              budynek.budynek_nazwa !== budynek.nazwa_folderu && (
                <span className="text-sm font-normal text-muted-foreground">
                  — w programie: {budynek.budynek_nazwa}
                </span>
              )
            )}
          </h2>

          {budynek.foldery.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Brak folderów lokali w tym budynku.
            </p>
          ) : (
            budynek.foldery.map((folder) => (
              <Folder key={folder.sciezka_wzgledna} folder={folder} />
            ))
          )}
        </section>
      ))}
    </div>
  );
}

/**
 * Katalog z dokumentami: pokazany i zmieniany tutaj, a nie w pliku .env.
 *
 * Wymaganie edycji pliku tekstowego od osoby, która ma obsługiwać umowy, było
 * przerzucaniem na nią pracy administratora. Katalog widać i da się go zmienić
 * z interfejsu — inaczej nie da się odpowiedzieć na pytanie „gdzie ten program
 * właściwie szuka".
 */
function UstawienieKatalogu() {
  const katalog = useKatalogSkanu();
  const ustaw = useUstawKatalogSkanu();
  const [edycja, setEdycja] = useState(false);
  const [sciezka, setSciezka] = useState("");
  const [blad, setBlad] = useState<string | null>(null);

  const dane = katalog.data;

  if (edycja) {
    return (
      <form
        className="mt-1 flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setBlad(null);
          ustaw.mutate(sciezka, {
            onSuccess: () => setEdycja(false),
            onError: (err) =>
              setBlad(
                err instanceof Error ? err.message : "Nie udało się zapisać.",
              ),
          });
        }}
      >
        <Input
          autoFocus
          aria-label="Katalog z dokumentami"
          className="h-9 w-[32rem] max-w-full font-mono text-xs"
          placeholder="C:\Users\Nazwa\Documents\Budynki"
          value={sciezka}
          onChange={(e) => setSciezka(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={ustaw.isPending}>
          {ustaw.isPending ? "Zapisuję…" : "Zapisz"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          type="button"
          onClick={() => {
            setEdycja(false);
            setBlad(null);
          }}
        >
          Anuluj
        </Button>
        {blad && (
          <span role="alert" className="w-full text-xs text-destructive">
            {blad}
          </span>
        )}
      </form>
    );
  }

  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <span className="font-mono text-xs">
        {dane?.sciezka ?? "Katalog nie jest jeszcze wskazany"}
      </span>
      {dane && !dane.istnieje && dane.sciezka && (
        <span className="rounded-full border border-destructive/40 px-2 py-0.5 text-xs text-destructive">
          nie istnieje
        </span>
      )}
      {dane?.zrodlo === "plik" && <span className="text-xs">z pliku .env</span>}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          setSciezka(dane?.sciezka ?? "");
          setEdycja(true);
        }}
      >
        Zmień
      </Button>
    </p>
  );
}

function PrzegladOdnosnikow({
  dane,
}: {
  dane: {
    sprawdzonych: number;
    zerwane: {
      dokument_id: number;
      nazwa: string | null;
      sciezka_wzgledna: string;
      powod: string;
    }[];
  };
}) {
  if (dane.zerwane.length === 0) {
    return (
      <p className="rounded-md border border-green-600/30 bg-green-600/5 p-3 text-sm">
        Wszystkie odnośniki działają. Sprawdzono: {dane.sprawdzonych}.
      </p>
    );
  }
  return (
    <div
      role="alert"
      className="space-y-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm"
    >
      <p className="font-medium text-destructive">
        Zerwane odnośniki: {dane.zerwane.length} z {dane.sprawdzonych}
      </p>
      <p className="text-muted-foreground">
        Dokumenty nie są kopiowane, więc przeniesienie albo przemianowanie pliku
        w Eksploratorze zrywa odnośnik. Przywróć plik pod starą ścieżkę albo
        dodaj go jeszcze raz.
      </p>
      <ul className="space-y-1">
        {dane.zerwane.map((z) => (
          <li key={z.dokument_id}>
            <span className="font-medium">
              {z.nazwa ?? `dokument #${z.dokument_id}`}
            </span>
            <span className="text-muted-foreground"> — {z.powod}</span>
            <div className="text-xs text-muted-foreground">
              {z.sciezka_wzgledna}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Folder({ folder }: { folder: FolderZeSkanu }) {
  const lokale = useLokale({ limit: 500 });
  const powiaz = usePowiazFolder();
  const odepnij = useOdepnijFolder();
  const [wybrany, setWybrany] = useState("");

  const doWyboru = (lokale.data?.pozycje ?? []).filter(
    (l) => l.okres_najmu_id !== null,
  );

  return (
    <div className="rounded-lg border">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/40 px-4 py-2.5">
        <div>
          <p className="font-medium">{folder.nazwa}</p>
          {folder.opis_umowy ? (
            <p className="text-sm text-muted-foreground">
              Umowa: {folder.opis_umowy}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Folder nie jest jeszcze przypisany do umowy.
            </p>
          )}
        </div>

        {folder.powiazanie_id ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => odepnij.mutate(folder.powiazanie_id as number)}
          >
            Odepnij
          </Button>
        ) : (
          <div className="flex items-center gap-2">
            <select
              aria-label={`Umowa dla folderu ${folder.nazwa}`}
              className="h-9 rounded-md border bg-transparent px-3 text-sm"
              value={wybrany}
              onChange={(e) => setWybrany(e.target.value)}
            >
              <option value="">— wybierz umowę —</option>
              {doWyboru.map((l) => (
                <option key={l.okres_najmu_id} value={String(l.okres_najmu_id)}>
                  {l.budynek_nazwa} / {l.oznaczenie} —{" "}
                  {l.najemca_nazwa ?? "bez najemcy"}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              disabled={!wybrany || powiaz.isPending}
              onClick={() =>
                powiaz.mutate({
                  sciezka_wzgledna: folder.sciezka_wzgledna,
                  okres_najmu_id: Number(wybrany),
                })
              }
            >
              Powiąż
            </Button>
          </div>
        )}
      </div>

      {folder.pliki.length === 0 ? (
        <p className="px-4 py-3 text-sm text-muted-foreground">
          Brak plików w tym folderze.
        </p>
      ) : (
        <ul className="divide-y">
          {folder.pliki.map((plik) => (
            <Plik
              key={plik.sciezka_wzgledna}
              plik={plik}
              okresNajmuId={folder.okres_najmu_id}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function Plik({
  plik,
  okresNajmuId,
}: {
  plik: PlikZeSkanu;
  okresNajmuId: number | null;
}) {
  const importuj = useZaimportujZDysku();
  const pomin = usePominPlik();
  const cofnij = useCofnijPominiecie();
  const [wpis, setWpis] = useState<Wpis>({
    typ: plik.typ_proponowany ?? "",
    numer: plik.numer_proponowany ?? "",
    data: "",
  });
  const [blad, setBlad] = useState<string | null>(null);

  if (plik.status === "w_systemie") {
    return (
      <li className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
        <span className="text-muted-foreground">{plik.nazwa}</span>
        <span className="flex items-center gap-3">
          <Badge variant="secondary">w systemie</Badge>
          {plik.dokument_id && (
            <a
              href={`/api/v1/dokumenty/${plik.dokument_id}/plik`}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-4"
            >
              Otwórz
            </a>
          )}
        </span>
      </li>
    );
  }

  if (plik.status === "pominiety") {
    return (
      <li className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
        <span className="text-muted-foreground line-through">{plik.nazwa}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => cofnij.mutate(plik.pominiecie_id as number)}
        >
          Przywróć
        </Button>
      </li>
    );
  }

  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="min-w-64 flex-1 text-sm font-medium">
          {plik.nazwa}
        </span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {formatujRozmiar(plik.rozmiar_bajty)}
        </span>

        <select
          aria-label={`Rodzaj dokumentu: ${plik.nazwa}`}
          className="h-9 rounded-md border bg-transparent px-2 text-sm"
          value={wpis.typ}
          onChange={(e) => setWpis({ ...wpis, typ: e.target.value })}
        >
          {TYPY.map((t) => (
            <option key={t.wartosc} value={t.wartosc}>
              {t.etykieta}
            </option>
          ))}
        </select>

        {wpis.typ === "aneks" && (
          <Input
            aria-label={`Numer aneksu: ${plik.nazwa}`}
            className="h-9 w-24"
            placeholder="nr"
            value={wpis.numer}
            onChange={(e) => setWpis({ ...wpis, numer: e.target.value })}
          />
        )}

        <Input
          type="date"
          aria-label={`Data dokumentu: ${plik.nazwa}`}
          className="h-9 w-40"
          value={wpis.data}
          onChange={(e) => setWpis({ ...wpis, data: e.target.value })}
        />

        <Button
          size="sm"
          disabled={!wpis.typ || okresNajmuId === null || importuj.isPending}
          onClick={() => {
            setBlad(null);
            importuj.mutate(
              {
                sciezka_wzgledna: plik.sciezka_wzgledna,
                typ: wpis.typ,
                okres_najmu_id: okresNajmuId,
                numer: wpis.numer || null,
                // Pusta data zostaje pusta. Do E9 system nie czyta treści
                // dokumentów, a „dziś" byłoby wartością zmyśloną (decyzja D5).
                data_dokumentu: wpis.data || null,
              },
              {
                onError: (e) =>
                  setBlad(
                    e instanceof Error ? e.message : "Nie udało się dodać.",
                  ),
              },
            );
          }}
        >
          Dodaj
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            pomin.mutate({ sciezka_wzgledna: plik.sciezka_wzgledna })
          }
        >
          Pomiń
        </Button>
      </div>

      {okresNajmuId === null && (
        <p className="text-xs text-muted-foreground">
          Najpierw powiąż ten folder z umową — dokument musi wiedzieć, do czego
          należy.
        </p>
      )}
      {plik.typ_proponowany === null && (
        <p className="text-xs text-muted-foreground">
          Z nazwy pliku nie wynika, co to za dokument. Wybierz rodzaj sam.
        </p>
      )}
      {blad && (
        <p role="alert" className="text-xs text-destructive">
          {blad}
        </p>
      )}
    </li>
  );
}
