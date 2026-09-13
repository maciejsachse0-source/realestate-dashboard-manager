import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import {
  useBudynki,
  useLokal,
  useNajemca,
  useOkresNajmu,
  useStanLokalu,
  useZdarzenia,
} from "@/api/zapytania";
import { formatujDate } from "@/funkcje/format";
import { czytelnaNazwaPola } from "@/funkcje/nazwy";
import { Blad, Ladowanie } from "@/komponenty/Stany";
import { PasekKompletnosci } from "@/komponenty/PasekKompletnosci";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ZakladkaPrzeglad } from "./ZakladkaPrzeglad";
import { ZakladkaNajemca } from "./ZakladkaNajemca";
import { ZakladkaFinanse } from "./ZakladkaFinanse";
import { ZakladkaZabezpieczenia } from "./ZakladkaZabezpieczenia";
import { ZakladkaPrzeglady } from "./ZakladkaPrzeglady";
import { ZakladkaDokumenty } from "./ZakladkaDokumenty";
import { ZakladkaHistoria } from "./ZakladkaHistoria";
import { ZakladkaZdarzenia } from "./ZakladkaZdarzenia";

/**
 * Profil lokalu (koncepcja, sekcja 7.2).
 *
 * Zakładka jest w adresie, więc link do konkretnej zakładki da się wysłać
 * współpracownikowi, a przycisk „wstecz" w przeglądarce działa tak,
 * jak użytkownik się spodziewa.
 *
 * Pole „stan na dzień" jest nad zakładkami, bo dotyczy ich wszystkich:
 * to widoczna twarz decyzji D2. Aneks nie nadpisuje wartości, tylko dokłada
 * wersję, więc każdy dzień w przeszłości ma swoją odpowiedź.
 */
export default function ProfilLokalu() {
  const { lokalId } = useParams<{ lokalId: string }>();
  const [parametry, setParametry] = useSearchParams();
  const [naDzien, setNaDzien] = useState("");
  const identyfikator = Number(lokalId);

  const lokal = useLokal(identyfikator);
  const stan = useStanLokalu(identyfikator, naDzien || undefined);
  const budynki = useBudynki();
  const okresId = stan.data?.okres_najmu_id ?? null;
  const okres = useOkresNajmu(okresId);
  const najemca = useNajemca(okres.data?.najemca_id);
  const zdarzenia = useZdarzenia({
    lokal_id: identyfikator,
    limit: 100,
    status_zdarzenia: "",
  });

  if (Number.isNaN(identyfikator)) {
    return <Blad komunikat="Nieprawidłowy numer lokalu w adresie." />;
  }

  if (lokal.isPending || stan.isPending) {
    return <Ladowanie wierszy={6} />;
  }

  if (lokal.isError || stan.isError) {
    const blad = lokal.error ?? stan.error;
    return (
      <Blad
        komunikat={
          blad instanceof Error ? blad.message : "Nie udało się wczytać lokalu."
        }
        ponow={() => {
          void lokal.refetch();
          void stan.refetch();
        }}
      />
    );
  }

  const budynek = budynki.data?.pozycje.find(
    (b) => b.id === lokal.data?.budynek_id,
  );
  const otwartych =
    zdarzenia.data?.pozycje.filter((z) => z.status === "otwarte").length ?? 0;
  const doWeryfikacji = stan.data ? stan.data.brakujace_pola.length : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link
            to="/"
            className="text-sm text-muted-foreground underline underline-offset-4"
          >
            ← Wróć do listy
          </Link>
          <h1 className="mt-1 flex items-center gap-3 text-lg font-semibold">
            {lokal.data?.oznaczenie}
            {budynek && (
              <span className="text-sm font-normal text-muted-foreground">
                {budynek.nazwa}
              </span>
            )}
            {najemca.data && (
              <span className="text-sm font-normal">
                · {najemca.data.nazwa_pelna}
              </span>
            )}
          </h1>
        </div>

        <div className="flex items-end gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Kompletność</p>
            <div className="mt-1">
              <PasekKompletnosci
                procent={stan.data?.kompletnosc_procent ?? null}
                braki={stan.data?.brakujace_pola ?? []}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="na_dzien">Stan na dzień</Label>
            <Input
              id="na_dzien"
              type="date"
              className="w-40"
              value={naDzien}
              onChange={(e) => setNaDzien(e.target.value)}
            />
          </div>
        </div>
      </div>

      {naDzien && (
        <p className="rounded-md border border-sky-300 bg-sky-50 px-3 py-2 text-sm text-sky-900">
          Oglądasz stan z dnia {formatujDate(naDzien)}, a nie stan bieżący.{" "}
          <button
            type="button"
            className="underline underline-offset-4"
            onClick={() => setNaDzien("")}
          >
            Wróć do dzisiaj
          </button>
        </p>
      )}

      {stan.data?.powod_braku_daty_zakonczenia && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {stan.data.powod_braku_daty_zakonczenia}
        </p>
      )}

      {doWeryfikacji > 0 && (
        <p className="text-sm text-muted-foreground">
          Do uzupełnienia:{" "}
          {(stan.data?.brakujace_pola ?? []).map(czytelnaNazwaPola).join(", ")}
        </p>
      )}

      <Tabs
        value={parametry.get("zakladka") ?? "przeglad"}
        onValueChange={(wartosc) =>
          setParametry({ zakladka: wartosc }, { replace: true })
        }
      >
        <TabsList className="flex-wrap">
          <TabsTrigger value="przeglad">Przegląd</TabsTrigger>
          <TabsTrigger value="najemca">Najemca</TabsTrigger>
          <TabsTrigger value="finanse">Finanse</TabsTrigger>
          <TabsTrigger value="zabezpieczenia">Zabezpieczenia</TabsTrigger>
          <TabsTrigger value="przeglady">Przeglądy</TabsTrigger>
          <TabsTrigger value="dokumenty">Dokumenty</TabsTrigger>
          <TabsTrigger value="historia">Historia</TabsTrigger>
          <TabsTrigger value="zdarzenia">
            Zdarzenia
            {otwartych > 0 && (
              <Badge variant="destructive" className="ml-2">
                {otwartych}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <div className="mt-4">
          <TabsContent value="przeglad">
            {stan.data && lokal.data && (
              <ZakladkaPrzeglad
                stan={stan.data}
                lokal={lokal.data}
                okres={okres.data ?? null}
              />
            )}
          </TabsContent>

          <TabsContent value="najemca">
            <ZakladkaNajemca
              najemca={najemca.data ?? null}
              wczytywanie={najemca.isPending}
            />
          </TabsContent>

          <TabsContent value="finanse">
            <ZakladkaFinanse okresId={okresId} stan={stan.data ?? null} />
          </TabsContent>

          <TabsContent value="zabezpieczenia">
            <ZakladkaZabezpieczenia okresId={okresId} />
          </TabsContent>

          <TabsContent value="przeglady">
            <ZakladkaPrzeglady lokalId={identyfikator} />
          </TabsContent>

          <TabsContent value="dokumenty">
            <ZakladkaDokumenty okresId={okresId} />
          </TabsContent>

          <TabsContent value="historia">
            <ZakladkaHistoria okresId={okresId} />
          </TabsContent>

          <TabsContent value="zdarzenia">
            <ZakladkaZdarzenia zdarzenia={zdarzenia.data?.pozycje ?? []} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
