import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { FiltryZdarzen, WagaZdarzenia, Zdarzenie } from "@/api/typy";
import { BladApi } from "@/api/klient";
import {
  useBudynki,
  useObsluzZdarzenie,
  useOdroczZdarzenie,
  useZdarzenia,
} from "@/api/zapytania";
import { formatujDate, opisTerminu } from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const OPIS_WAGI: Record<WagaZdarzenia, string> = {
  krytyczne: "Krytyczne",
  ostrzezenie: "Ostrzeżenie",
  informacja: "Informacja",
};

/** Kolejność grup na ekranie. Najpilniejsze na górze — po to jest ten ekran. */
const KOLEJNOSC: WagaZdarzenia[] = ["krytyczne", "ostrzezenie", "informacja"];

/**
 * Kokpit terminów (koncepcja, sekcja 7.3).
 *
 * To jest właściwy produkt tego systemu. Tabela lokali jest widokiem;
 * po to, co jest tutaj, ktoś wchodzi do programu w poniedziałek rano.
 *
 * Bez wyskakujących powiadomień — w tego typu pracy szum zabija uwagę
 * szybciej niż brak alertu.
 */
export default function KokpitTerminow() {
  const nawigacja = useNavigate();
  const [filtry, setFiltry] = useState<FiltryZdarzen>({
    status_zdarzenia: "otwarte",
    limit: 200,
  });
  const [blad, setBlad] = useState<string | null>(null);

  const zdarzenia = useZdarzenia(filtry as Record<string, unknown>);
  const budynki = useBudynki();
  const obsluz = useObsluzZdarzenie();
  const odrocz = useOdroczZdarzenie();

  const pozycje = zdarzenia.data?.pozycje ?? [];
  const pogrupowane = KOLEJNOSC.map((waga) => ({
    waga,
    lista: pozycje.filter((z) => z.waga === waga),
  })).filter((g) => g.lista.length > 0);

  function zglosBlad(e: unknown) {
    setBlad(e instanceof BladApi ? e.message : "Nie udało się zapisać zmiany.");
  }

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Terminy</h1>
        {zdarzenia.data && (
          <p className="text-sm text-muted-foreground">
            {zdarzenia.data.wszystkich === 0
              ? "Brak wyników"
              : `${pozycje.length} z ${zdarzenia.data.wszystkich}`}
          </p>
        )}
      </div>

      <Filtry
        filtry={filtry}
        budynki={budynki.data?.pozycje ?? []}
        onZmiana={setFiltry}
      />

      {blad && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {blad}
        </p>
      )}

      {zdarzenia.isPending && <Ladowanie wierszy={5} />}

      {zdarzenia.isError && (
        <Blad
          komunikat={
            zdarzenia.error instanceof Error
              ? zdarzenia.error.message
              : "Nieznany błąd."
          }
          ponow={() => void zdarzenia.refetch()}
        />
      )}

      {zdarzenia.data && pozycje.length === 0 && (
        <Pusto
          tytul={
            filtry.status_zdarzenia === "otwarte"
              ? "Nic nie wymaga uwagi"
              : "Brak zdarzeń"
          }
          opis={
            filtry.status_zdarzenia === "otwarte"
              ? "Wszystkie terminy są obsłużone. Generator sprawdza je codziennie o 6:00."
              : "Zmień filtry albo sprawdź, czy w systemie są wprowadzone umowy."
          }
        />
      )}

      {pogrupowane.map(({ waga, lista }) => (
        <section key={waga} className="space-y-2">
          <h2 className="flex items-center gap-2 text-sm font-medium">
            <Badge variant={waga === "krytyczne" ? "destructive" : "secondary"}>
              {OPIS_WAGI[waga]}
            </Badge>
            <span className="text-muted-foreground">{lista.length}</span>
          </h2>

          <ul className="divide-y rounded-lg border bg-background">
            {lista.map((zdarzenie) => (
              <Wiersz
                key={zdarzenie.id}
                zdarzenie={zdarzenie}
                zajety={obsluz.isPending || odrocz.isPending}
                naLokal={() =>
                  zdarzenie.lokal_id &&
                  nawigacja(`/lokale/${zdarzenie.lokal_id}`)
                }
                naObsluzone={(notatka) =>
                  obsluz.mutate(
                    { id: zdarzenie.id, notatka },
                    { onError: zglosBlad },
                  )
                }
                naOdroczenie={(doDnia, notatka) =>
                  odrocz.mutate(
                    { id: zdarzenie.id, do_dnia: doDnia, notatka },
                    { onError: zglosBlad },
                  )
                }
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function Filtry({
  filtry,
  budynki,
  onZmiana,
}: {
  filtry: FiltryZdarzen;
  budynki: { id: number; nazwa: string }[];
  onZmiana: (f: FiltryZdarzen) => void;
}) {
  function ustaw(zmiana: Partial<FiltryZdarzen>) {
    onZmiana({ ...filtry, ...zmiana });
  }

  return (
    <div className="grid gap-4 rounded-lg border bg-background p-4 md:grid-cols-4">
      <div className="space-y-1.5">
        <Label htmlFor="status">Stan</Label>
        <select
          id="status"
          className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          value={filtry.status_zdarzenia ?? ""}
          onChange={(e) =>
            ustaw({
              status_zdarzenia: e.target
                .value as FiltryZdarzen["status_zdarzenia"],
            })
          }
        >
          <option value="otwarte">Nieobsłużone</option>
          <option value="odroczone">Odroczone</option>
          <option value="obsluzone">Obsłużone</option>
          <option value="">Wszystkie</option>
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="budynek">Budynek</Label>
        <select
          id="budynek"
          className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          value={filtry.budynek_id ?? ""}
          onChange={(e) =>
            ustaw({
              budynek_id: e.target.value ? Number(e.target.value) : undefined,
            })
          }
        >
          <option value="">Wszystkie</option>
          {budynki.map((b) => (
            <option key={b.id} value={b.id}>
              {b.nazwa}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="do_dnia">Termin do dnia</Label>
        <Input
          id="do_dnia"
          type="date"
          value={filtry.do_dnia ?? ""}
          onChange={(e) => ustaw({ do_dnia: e.target.value || undefined })}
        />
      </div>
    </div>
  );
}

/**
 * Ile dni zostalo do terminu. To jest informacja, dla ktorej ktos otwiera
 * ten ekran: sama data wymaga liczenia w glowie, a przy dwudziestu wierszach
 * nikt tego nie robi.
 *
 * Po terminie kolor jest ostrzegawczy, bo to juz nie jest zapowiedz.
 */
function LicznikDni({ dni }: { dni: number | null }) {
  if (dni === null) return null;

  const poTerminie = dni < 0;
  const dzisiaj = dni === 0;
  const styl = poTerminie
    ? "border-destructive/40 bg-destructive/10 text-destructive"
    : dzisiaj
      ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
      : "border-border bg-muted text-foreground";

  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium tabular-nums ${styl}`}
    >
      {opisTerminu(dni)}
    </span>
  );
}

function Wiersz({
  zdarzenie,
  zajety,
  naLokal,
  naObsluzone,
  naOdroczenie,
}: {
  zdarzenie: Zdarzenie;
  zajety: boolean;
  naLokal: () => void;
  naObsluzone: (notatka?: string) => void;
  naOdroczenie: (doDnia: string, notatka?: string) => void;
}) {
  const [tryb, setTryb] = useState<"brak" | "obsluga" | "odroczenie">("brak");
  const [notatka, setNotatka] = useState("");
  const [doDnia, setDoDnia] = useState(() => {
    const za_tydzien = new Date();
    za_tydzien.setDate(za_tydzien.getDate() + 7);
    return za_tydzien.toISOString().slice(0, 10);
  });

  return (
    <li className="space-y-2 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm">{zdarzenie.tresc}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <LicznikDni dni={zdarzenie.dni_do_terminu} />
            {formatujDate(zdarzenie.data_zdarzenia)}
            {zdarzenie.status === "odroczone" &&
              zdarzenie.odroczone_do &&
              ` · odroczone do ${formatujDate(zdarzenie.odroczone_do)}`}
            {zdarzenie.notatka && ` · „${zdarzenie.notatka}"`}
          </p>
        </div>

        {zdarzenie.lokal_id && (
          <Button variant="ghost" size="sm" onClick={naLokal}>
            Pokaż lokal
          </Button>
        )}

        {zdarzenie.status !== "obsluzone" && (
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={zajety}
              onClick={() =>
                setTryb(tryb === "odroczenie" ? "brak" : "odroczenie")
              }
            >
              Odrocz
            </Button>
            <Button
              size="sm"
              disabled={zajety}
              onClick={() => setTryb(tryb === "obsluga" ? "brak" : "obsluga")}
            >
              Obsłużone
            </Button>
          </>
        )}
      </div>

      {tryb === "obsluga" && (
        <div className="flex flex-wrap items-end gap-2 rounded-md bg-muted/40 p-2">
          <div className="min-w-56 flex-1 space-y-1">
            <Label htmlFor={`notatka-${zdarzenie.id}`} className="text-xs">
              Notatka (opcjonalna)
            </Label>
            <Input
              id={`notatka-${zdarzenie.id}`}
              className="h-8"
              placeholder="Co zrobiono?"
              value={notatka}
              onChange={(e) => setNotatka(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            disabled={zajety}
            onClick={() => {
              naObsluzone(notatka || undefined);
              setTryb("brak");
            }}
          >
            Zapisz
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setTryb("brak")}>
            Anuluj
          </Button>
        </div>
      )}

      {tryb === "odroczenie" && (
        <div className="flex flex-wrap items-end gap-2 rounded-md bg-muted/40 p-2">
          <div className="space-y-1">
            <Label htmlFor={`do-${zdarzenie.id}`} className="text-xs">
              Wróć do tego dnia
            </Label>
            <Input
              id={`do-${zdarzenie.id}`}
              type="date"
              className="h-8 w-40"
              value={doDnia}
              onChange={(e) => setDoDnia(e.target.value)}
            />
          </div>
          <div className="min-w-56 flex-1 space-y-1">
            <Label htmlFor={`powod-${zdarzenie.id}`} className="text-xs">
              Powód odroczenia
            </Label>
            <Input
              id={`powod-${zdarzenie.id}`}
              className="h-8"
              placeholder="Dlaczego to może poczekać?"
              value={notatka}
              onChange={(e) => setNotatka(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            disabled={zajety}
            onClick={() => {
              naOdroczenie(doDnia, notatka || undefined);
              setTryb("brak");
            }}
          >
            Odrocz
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setTryb("brak")}>
            Anuluj
          </Button>
        </div>
      )}
    </li>
  );
}
