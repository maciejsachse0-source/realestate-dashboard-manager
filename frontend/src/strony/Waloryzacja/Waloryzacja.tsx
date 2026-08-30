import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BladApi, pobierz, wyslij } from "@/api/klient";
import {
  BRAK_DANYCH,
  formatujDate,
  formatujKwote,
  formatujProcent,
  formatujRoznice,
} from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { PoleTekstowe, PoleWyboru } from "@/komponenty/Formularz";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Wskaznik {
  id: number;
  rok: number;
  rodzaj: string;
  wartosc_procent: string;
  data_publikacji: string | null;
}

interface Pozycja {
  okres_najmu_id: number;
  lokal_id: number;
  oznaczenie_lokalu: string;
  najemca: string;
  kwota_stara: string | null;
  kwota_nowa: string | null;
  roznica: string | null;
  waluta: string | null;
  rodzaj_kwoty: string | null;
  wskaznik_procent: string | null;
  obowiazuje_od: string | null;
  powod_wylaczenia: string | null;
}

interface Suma {
  waluta: string;
  umow: number;
  przed: string;
  po: string;
  roznica: string;
}

interface Przebieg {
  rok: number;
  wskazniki: Record<string, string>;
  objete: Pozycja[];
  wylaczone: Pozycja[];
  sumy: Suma[];
}

const RODZAJE = [
  { wartosc: "gus_rok_do_roku", etykieta: "GUS rok do roku" },
  { wartosc: "gus_srednioroczny", etykieta: "GUS średnioroczny" },
];

const NAZWY_RODZAJOW: Record<string, string> = {
  gus_rok_do_roku: "GUS rok do roku",
  gus_srednioroczny: "GUS średnioroczny",
  stala_stawka: "stała stawka z umowy",
};

/**
 * Waloryzacja roczna (koncepcja, sekcja 7.6).
 *
 * Wskaźnik wprowadza się raz, a efekt jest na wszystkich umowach. Dziś to
 * kilkanaście godzin pracy ręcznej raz do roku.
 *
 * Ekran ma dwa kroki. Podgląd niczego nie zapisuje, więc wycofanie się przed
 * zatwierdzeniem jest darmowe. Umowy wyłączone są pokazane razem z powodem
 * wyłączenia — bez tego nikt nie wie, czy system je pominął, czy o nich
 * zapomniał.
 *
 * Sumę zaznaczonych propozycji liczy serwer, także przy odznaczaniu. Front
 * nie liczy niczego na pieniądzach (reguła projektu).
 */
export default function Waloryzacja() {
  const kolejka = useQueryClient();
  // Rok trzymamy jako tekst. Number('') to 0, a `rok=0` to 422 z serwera
  // pokazane użytkownikowi tylko dlatego, że skasował pole, żeby wpisać
  // inną wartość. Do zapytań idzie dopiero wartość z dozwolonego zakresu.
  const [rokTekst, setRokTekst] = useState(() =>
    String(new Date().getFullYear()),
  );
  const [odznaczone, setOdznaczone] = useState<Set<number>>(new Set());
  const [wynik, setWynik] = useState<{ umow: number; weksle: number } | null>(
    null,
  );
  const [blad, setBlad] = useState<string | null>(null);

  const rok = poprawnyRok(rokTekst);

  const wskazniki = useQuery({
    queryKey: ["wskazniki", rok],
    queryFn: () =>
      pobierz<{ pozycje: Wskaznik[] }>("/waloryzacja/wskazniki", { rok }),
    enabled: rok !== null,
  });

  const przebieg = useQuery({
    queryKey: ["przebieg-waloryzacji", rok],
    queryFn: () => pobierz<Przebieg>("/waloryzacja/przebieg", { rok }),
    enabled: rok !== null,
  });

  const objete = useMemo(() => przebieg.data?.objete ?? [], [przebieg.data]);

  // Domyślnie zaznaczone jest wszystko, bo zatwierdzanie całości jest częstsze
  // niż wybieranie pojedynczych umów. Trzymamy więc zbiór odznaczonych.
  const doZatwierdzenia = useMemo(
    () => objete.filter((p) => !odznaczone.has(p.okres_najmu_id)),
    [objete, odznaczone],
  );
  const identyfikatory = doZatwierdzenia.map((p) => p.okres_najmu_id);

  const sumy = useQuery({
    // Klucz z posortowanych identyfikatorów: ten sam wybór to ten sam wynik,
    // więc odznaczenie i ponowne zaznaczenie nie wywołuje zapytania.
    queryKey: [
      "podsumowanie-waloryzacji",
      rok,
      [...identyfikatory].sort((a, b) => a - b),
    ],
    queryFn: () =>
      wyslij<Suma[]>("/waloryzacja/podsumowanie", {
        rok,
        okresy_najmu: identyfikatory,
      }),
    enabled: rok !== null && objete.length > 0,
    placeholderData: (poprzednie) => poprzednie,
  });

  const zatwierdzenie = useMutation({
    mutationFn: (okresy: number[]) =>
      wyslij<{ umow_zwaloryzowanych: number; zdarzen_o_wekslach: number }>(
        "/waloryzacja/zatwierdz",
        { rok, okresy_najmu: okresy },
      ),
    onSuccess: (odp) => {
      setWynik({
        umow: odp.umow_zwaloryzowanych,
        weksle: odp.zdarzen_o_wekslach,
      });
      setOdznaczone(new Set());
      // Waloryzacja zmienia czynsze, więc nieaktualne są też kartoteka,
      // profile lokali i kokpit terminów. Unieważniamy, a nie czyścimy:
      // `clear()` wyrzuca dane innych ekranów i wrzuca je w stan ładowania.
      void kolejka.invalidateQueries();
    },
    onError: (e) => {
      setBlad(e instanceof BladApi ? e.message : "Nie udało się zatwierdzić.");
      // Serwer odrzuca zatwierdzenie, gdy lista propozycji jest już nieaktualna
      // (409). Kazanie użytkownikowi „odświeżyć listę" i nieodświeżanie jej
      // byłoby złośliwe — po takim błędzie pobieramy przebieg na nowo.
      if (e instanceof BladApi && e.konflikt) {
        void kolejka.invalidateQueries({ queryKey: ["przebieg-waloryzacji"] });
        setOdznaczone(new Set());
      }
    },
  });

  function przelacz(id: number) {
    const nowe = new Set(odznaczone);
    if (nowe.has(id)) nowe.delete(id);
    else nowe.add(id);
    setOdznaczone(nowe);
  }

  function zmienRok(nowy: string) {
    setRokTekst(nowy);
    setOdznaczone(new Set());
    setWynik(null);
    setBlad(null);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Waloryzacja roczna</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Wskaźnik wprowadzasz raz. System policzy propozycje dla wszystkich
            umów, które mu podlegają.
          </p>
        </div>

        <div className="flex items-end gap-4">
          {/* Arkusz jest potrzebny głównie PO zatwierdzeniu, do pism dla
              najemców, więc link jest poza listą propozycji — inaczej znikałby
              dokładnie wtedy, kiedy się przydaje. */}
          <a
            href={`/api/v1/waloryzacja/eksport?rok=${rok}`}
            className="pb-2 text-sm underline underline-offset-4"
          >
            Pobierz listę zmian (XLSX)
          </a>

          <div className="space-y-1.5">
            <Label htmlFor="rok">Rok</Label>
            <Input
              id="rok"
              inputMode="numeric"
              className="w-28"
              aria-invalid={rok === null}
              value={rokTekst}
              onChange={(e) => zmienRok(e.target.value)}
            />
          </div>
        </div>
      </div>

      {wynik && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-900">
          <p className="font-medium">
            Zwaloryzowano {wynik.umow} {slowoUmowa(wynik.umow)}. Listę zmian do
            pism dla najemców pobierzesz przyciskiem „Pobierz listę zmian" u
            góry.
          </p>
          {wynik.weksle > 0 && (
            <p className="mt-1">
              Powstało {wynik.weksle}{" "}
              {wynik.weksle === 1 ? "zdarzenie" : "zdarzeń"} o zabezpieczeniach
              do przeliczenia. Znajdziesz je w Terminach.
            </p>
          )}
        </div>
      )}

      {rok === null ? (
        <Pusto
          tytul="Podaj rok waloryzacji"
          opis={`Rok musi być liczbą z zakresu ${ROK_MIN}–${ROK_MAX}.`}
        />
      ) : (
        <PanelWskaznika rok={rok} wskazniki={wskazniki.data?.pozycje ?? []} />
      )}

      {blad && <Blad komunikat={blad} />}

      {przebieg.isPending && <Ladowanie wierszy={4} />}

      {przebieg.isError && (
        <Blad
          komunikat={
            przebieg.error instanceof Error
              ? przebieg.error.message
              : "Nie udało się wczytać przebiegu."
          }
          ponow={() => void przebieg.refetch()}
        />
      )}

      {przebieg.data && objete.length === 0 && (
        <Pusto
          tytul="Żadna umowa nie kwalifikuje się do waloryzacji"
          opis={
            Object.keys(przebieg.data.wskazniki).length === 0
              ? `Najpierw wprowadź wskaźnik na rok ${rok}.`
              : "Sprawdź listę wyłączeń poniżej — każda pozycja ma podany powód."
          }
        />
      )}

      {przebieg.data && objete.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium">
            Do zatwierdzenia: {doZatwierdzenia.length} z {objete.length}
          </h2>

          <div className="overflow-x-auto rounded-lg border bg-background">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">
                    <input
                      type="checkbox"
                      className="size-4"
                      aria-label="Zaznacz wszystkie"
                      checked={odznaczone.size === 0}
                      onChange={(e) =>
                        setOdznaczone(
                          e.target.checked
                            ? new Set()
                            : new Set(objete.map((p) => p.okres_najmu_id)),
                        )
                      }
                    />
                  </th>
                  <th className="px-3 py-2 font-medium">Lokal</th>
                  <th className="px-3 py-2 font-medium">Najemca</th>
                  <th className="px-3 py-2 text-right font-medium">
                    Czynsz teraz
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    Po waloryzacji
                  </th>
                  <th className="px-3 py-2 text-right font-medium">Różnica</th>
                  <th className="px-3 py-2 font-medium">Od kiedy</th>
                </tr>
              </thead>
              <tbody>
                {objete.map((p) => {
                  const zaznaczona = !odznaczone.has(p.okres_najmu_id);
                  return (
                    <tr
                      key={p.okres_najmu_id}
                      className={`border-b last:border-b-0 ${zaznaczona ? "" : "opacity-50"}`}
                    >
                      <td className="px-3 py-2.5">
                        <input
                          type="checkbox"
                          className="size-4"
                          aria-label={`Zatwierdź ${p.oznaczenie_lokalu}`}
                          checked={zaznaczona}
                          onChange={() => przelacz(p.okres_najmu_id)}
                        />
                      </td>
                      <td className="px-3 py-2.5 font-medium">
                        {p.oznaczenie_lokalu}
                      </td>
                      <td className="px-3 py-2.5">{p.najemca}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">
                        {p.kwota_stara
                          ? formatujKwote(p.kwota_stara, p.waluta ?? "PLN")
                          : BRAK_DANYCH}
                      </td>
                      <td className="px-3 py-2.5 text-right font-medium tabular-nums">
                        {p.kwota_nowa
                          ? formatujKwote(p.kwota_nowa, p.waluta ?? "PLN")
                          : BRAK_DANYCH}
                        {p.rodzaj_kwoty && (
                          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                            {p.rodzaj_kwoty}
                          </span>
                        )}
                      </td>
                      <td
                        className={`px-3 py-2.5 text-right tabular-nums ${kolorZmiany(p.roznica)}`}
                      >
                        {p.roznica
                          ? formatujRoznice(p.roznica, p.waluta ?? "PLN")
                          : BRAK_DANYCH}
                      </td>
                      <td className="px-3 py-2.5">
                        {formatujDate(p.obowiazuje_od)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <Podsumowanie sumy={sumy.data ?? []} />

          <div className="flex flex-wrap items-center gap-3">
            <Button
              disabled={doZatwierdzenia.length === 0 || zatwierdzenie.isPending}
              onClick={() => {
                setBlad(null);
                setWynik(null);
                zatwierdzenie.mutate(identyfikatory);
              }}
            >
              {zatwierdzenie.isPending
                ? "Zapisuję…"
                : `Zatwierdź ${doZatwierdzenia.length} ${slowoUmowa(doZatwierdzenia.length)}`}
            </Button>
            <span className="text-sm text-muted-foreground">
              Zatwierdzenie zakłada nowy czynsz obowiązujący od miesiąca
              waloryzacji. Poprzednia kwota zostaje w historii.
            </span>
          </div>
        </section>
      )}

      {przebieg.data && przebieg.data.wylaczone.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">
            Wyłączone z waloryzacji ({przebieg.data.wylaczone.length})
          </h2>
          <ul className="divide-y rounded-lg border bg-background text-sm">
            {przebieg.data.wylaczone.map((p) => (
              <li
                key={p.okres_najmu_id}
                className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-3 py-2.5"
              >
                <span className="w-24 shrink-0 font-medium">
                  {p.oznaczenie_lokalu}
                </span>
                <span className="w-56 shrink-0 text-muted-foreground">
                  {p.najemca}
                </span>
                <span className="text-muted-foreground">
                  {p.powod_wylaczenia ?? BRAK_DANYCH}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Podgląd sumy zmian. Kwoty przychodzą policzone z serwera, w rozbiciu na waluty. */
function Podsumowanie({ sumy }: { sumy: Suma[] }) {
  if (sumy.length === 0) {
    return (
      <p className="rounded-lg border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
        Nic nie zaznaczono — nie ma czego zatwierdzić.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border bg-muted/40">
      <table className="w-full text-sm">
        <tbody>
          {sumy.map((s) => (
            <tr key={s.waluta} className="border-b last:border-b-0">
              <td className="px-3 py-2.5 font-medium">
                Razem {s.waluta} ({s.umow} {slowoUmowa(s.umow)})
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">
                {formatujKwote(s.przed, s.waluta)}
              </td>
              <td className="px-3 py-2.5 text-right font-medium tabular-nums">
                {formatujKwote(s.po, s.waluta)}
              </td>
              <td
                className={`px-3 py-2.5 text-right tabular-nums ${kolorZmiany(s.roznica)}`}
              >
                {formatujRoznice(s.roznica, s.waluta)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PanelWskaznika({
  rok,
  wskazniki,
}: {
  rok: number;
  wskazniki: Wskaznik[];
}) {
  const kolejka = useQueryClient();
  const [rodzaj, setRodzaj] = useState("gus_rok_do_roku");
  const [wartosc, setWartosc] = useState("");
  const [blad, setBlad] = useState<string | null>(null);

  const procent = poprawnyProcent(wartosc);

  const dodaj = useMutation({
    mutationFn: (wartosc_procent: string) =>
      wyslij<Wskaznik>("/waloryzacja/wskazniki", {
        rok,
        rodzaj,
        wartosc_procent,
      }),
    onSuccess: () => {
      setWartosc("");
      setBlad(null);
      void kolejka.invalidateQueries({ queryKey: ["wskazniki"] });
      void kolejka.invalidateQueries({ queryKey: ["przebieg-waloryzacji"] });
      void kolejka.invalidateQueries({
        queryKey: ["podsumowanie-waloryzacji"],
      });
    },
    onError: (e) =>
      setBlad(
        e instanceof BladApi ? e.message : "Nie udało się zapisać wskaźnika.",
      ),
  });

  return (
    <section className="space-y-3 rounded-lg border bg-background p-4">
      <h2 className="text-sm font-medium">Wskaźniki na rok {rok}</h2>

      {wskazniki.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Brak wskaźnika na ten rok. Bez niego system nie policzy propozycji.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-2 text-sm">
          {wskazniki.map((w) => (
            <li
              key={w.id}
              className="rounded-md border bg-muted/40 px-2.5 py-1"
            >
              {NAZWY_RODZAJOW[w.rodzaj] ?? w.rodzaj}:{" "}
              <strong>{formatujProcent(w.wartosc_procent)}</strong>
              {w.data_publikacji && (
                <span className="ml-2 text-xs text-muted-foreground">
                  ogłoszony {formatujDate(w.data_publikacji)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (procent === null) {
            setBlad(
              "Wskaźnik musi być liczbą z zakresu od -50 do 100, np. 3,7.",
            );
            return;
          }
          dodaj.mutate(procent);
        }}
      >
        <PoleWyboru
          nazwa="rodzaj"
          etykieta="Rodzaj wskaźnika"
          wartosc={rodzaj}
          onZmiana={setRodzaj}
          opcje={RODZAJE}
          wymagane
        />

        <PoleTekstowe
          nazwa="wartosc"
          etykieta="Wartość (%)"
          wartosc={wartosc}
          onZmiana={(v) => {
            setWartosc(v);
            setBlad(null);
          }}
          inputMode="decimal"
          className="w-28"
          placeholder="3,70"
          wymagane
          aria-invalid={wartosc !== "" && procent === null}
        />

        <Button
          type="submit"
          variant="outline"
          disabled={dodaj.isPending || !wartosc}
        >
          {dodaj.isPending ? "Zapisuję…" : "Wprowadź wskaźnik"}
        </Button>
      </form>

      <p className="text-xs text-muted-foreground">
        Wskaźnik wprowadza się raz na rok. Ujemny jest dopuszczalny — deflacja
        obniża czynsz, jeśli umowa tego nie wyklucza.
      </p>

      {blad && (
        <p role="alert" className="text-sm text-destructive">
          {blad}
        </p>
      )}
    </section>
  );
}

const ROK_MIN = 2000;
const ROK_MAX = 2200;

/**
 * Rok z pola tekstowego albo null.
 *
 * Pusty input dawał wcześniej `Number('') === 0`, a więc `?rok=0` i błąd 422
 * pokazany użytkownikowi tylko za to, że skasował pole przed wpisaniem
 * nowej wartości.
 */
function poprawnyRok(tekst: string): number | null {
  if (!/^\d{4}$/.test(tekst.trim())) return null;
  const liczba = Number(tekst);
  return liczba >= ROK_MIN && liczba <= ROK_MAX ? liczba : null;
}

/**
 * Wskaźnik z pola tekstowego, znormalizowany do postaci, jakiej oczekuje API.
 *
 * Użytkownik pisze po polsku, czyli z przecinkiem. Zakres jest ten sam,
 * co po stronie serwera — walidacja tutaj tylko oszczędza mu podróży
 * po komunikat Pydantica.
 */
function poprawnyProcent(tekst: string): string | null {
  const znormalizowany = tekst.trim().replace(",", ".");
  if (!/^-?\d{1,3}(\.\d{1,2})?$/.test(znormalizowany)) return null;
  const liczba = Number(znormalizowany);
  return liczba >= -50 && liczba <= 100 ? znormalizowany : null;
}

/** Zieleń dla podwyżki, czerwień dla obniżki. Zero jest neutralne. */
function kolorZmiany(roznica: string | null): string {
  const liczba = Number(roznica ?? 0);
  if (!Number.isFinite(liczba) || liczba === 0) return "text-muted-foreground";
  return liczba > 0 ? "text-emerald-700" : "text-red-700";
}

/** Polska odmiana po liczebniku: 1 umowę, 2 umowy, 5 umów. */
function slowoUmowa(ile: number): string {
  if (ile === 1) return "umowę";
  const dziesiatki = ile % 100;
  const jednosci = ile % 10;
  if (jednosci >= 2 && jednosci <= 4 && !(dziesiatki >= 12 && dziesiatki <= 14))
    return "umowy";
  return "umów";
}
