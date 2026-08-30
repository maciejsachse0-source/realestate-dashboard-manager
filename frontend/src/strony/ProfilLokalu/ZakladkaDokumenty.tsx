import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { pobierz } from "@/api/klient";
import { formatujDate, formatujRozmiar } from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Karta } from "./Wspolne";

interface Dokument {
  id: number;
  okres_najmu_id: number | null;
  typ: string;
  numer: string | null;
  data_dokumentu: string | null;
  data_obowiazywania_od: string | null;
  plik_nazwa_oryginalna: string | null;
  hash_sha256: string | null;
  rozmiar_bajty: number | null;
  typ_mime: string | null;
  dokument_nadrzedny_id: number | null;
  status_przetworzenia: string;
  utworzono: string;
  uwagi: string | null;
  wersja: number;
}

const TYPY = [
  { wartosc: "umowa", etykieta: "Umowa" },
  { wartosc: "aneks", etykieta: "Aneks" },
  { wartosc: "protokol_przekazania", etykieta: "Protokół przekazania" },
  { wartosc: "protokol_zdawczy", etykieta: "Protokół zdawczy" },
  { wartosc: "polisa", etykieta: "Polisa" },
  { wartosc: "protokol_przegladu", etykieta: "Protokół z przeglądu" },
  { wartosc: "wypowiedzenie", etykieta: "Wypowiedzenie" },
  { wartosc: "inne", etykieta: "Inne" },
];

const NAZWY_TYPOW = Object.fromEntries(
  TYPY.map((t) => [t.wartosc, t.etykieta]),
);

/**
 * Dokumenty umowy (koncepcja, sekcja 7.2).
 *
 * Dokument to źródło dowodu, nie źródło prawdy. Dane są w bazie, a stąd
 * prowadzi do nich odnośnik — dlatego aneks wskazuje na umowę nadrzędną.
 *
 * Plik otwiera się w nowej karcie, a nie pobiera na dysk: chodzi o obejrzenie
 * dokumentu, a nie o rozsianie kopii po komputerach.
 */
export function ZakladkaDokumenty({ okresId }: { okresId: number | null }) {
  const kolejka = useQueryClient();
  const [wgrywanie, setWgrywanie] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);

  const dokumenty = useQuery({
    queryKey: ["dokumenty", okresId],
    queryFn: () =>
      pobierz<Dokument[]>("/dokumenty", { okres_najmu_id: okresId }),
    enabled: okresId != null,
  });

  if (okresId === null) {
    return (
      <Pusto
        tytul="Brak umowy"
        opis="Dokumenty przypina się do umowy. Najpierw załóż umowę dla tego lokalu."
      />
    );
  }
  if (dokumenty.isPending) return <Ladowanie wierszy={3} />;
  if (dokumenty.isError) {
    return (
      <Blad
        komunikat={
          dokumenty.error instanceof Error
            ? dokumenty.error.message
            : "Nieznany błąd."
        }
        ponow={() => void dokumenty.refetch()}
      />
    );
  }

  async function wgraj(plik: File, typ: string, nadrzedny: string) {
    setWgrywanie(true);
    setBlad(null);
    try {
      const dane = new FormData();
      dane.append("plik", plik);
      const zapytanie = new URLSearchParams({
        typ,
        okres_najmu_id: String(okresId),
      });
      if (nadrzedny) zapytanie.set("dokument_nadrzedny_id", nadrzedny);

      const odpowiedz = await fetch(`/api/v1/dokumenty?${zapytanie}`, {
        method: "POST",
        body: dane,
        credentials: "same-origin",
      });
      const tresc = await odpowiedz.json();
      if (!odpowiedz.ok) {
        setBlad(
          typeof tresc.detail === "string"
            ? tresc.detail
            : "Nie udało się wgrać pliku.",
        );
        return;
      }
      void kolejka.invalidateQueries({ queryKey: ["dokumenty"] });
    } catch {
      setBlad("Brak połączenia z programem.");
    } finally {
      setWgrywanie(false);
    }
  }

  const umowy = dokumenty.data.filter((d) => d.typ === "umowa");

  return (
    <div className="space-y-4">
      <FormularzWgrywania
        umowy={umowy}
        wgrywanie={wgrywanie}
        onWgraj={(plik, typ, nadrzedny) => void wgraj(plik, typ, nadrzedny)}
      />

      {blad && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {blad}
        </p>
      )}

      {dokumenty.data.length === 0 ? (
        <Pusto
          tytul="Brak dokumentów"
          opis="Wgraj umowę, protokół przekazania albo polisę. System rozpozna, jeśli ten sam plik był już wgrany."
        />
      ) : (
        <Karta>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Rodzaj</th>
                  <th className="px-3 py-2 font-medium">Nazwa pliku</th>
                  <th className="px-3 py-2 font-medium">Data</th>
                  <th className="px-3 py-2 font-medium">Dotyczy</th>
                  <th className="px-3 py-2 text-right font-medium">Rozmiar</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {dokumenty.data.map((d) => (
                  <tr key={d.id} className="border-b last:border-b-0">
                    <td className="px-3 py-2.5">
                      <Badge
                        variant={d.typ === "umowa" ? "default" : "secondary"}
                      >
                        {NAZWY_TYPOW[d.typ] ?? d.typ}
                      </Badge>
                      {d.numer && (
                        <span className="ml-2 text-xs">nr {d.numer}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {d.plik_nazwa_oryginalna ?? "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      {formatujDate(d.data_dokumentu)}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {d.dokument_nadrzedny_id
                        ? `aneks do #${d.dokument_nadrzedny_id}`
                        : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">
                      {formatujRozmiar(d.rozmiar_bajty)}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <a
                        href={`/api/v1/dokumenty/${d.id}/plik`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm underline underline-offset-4"
                      >
                        Otwórz
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Karta>
      )}
    </div>
  );
}

function FormularzWgrywania({
  umowy,
  wgrywanie,
  onWgraj,
}: {
  umowy: Dokument[];
  wgrywanie: boolean;
  onWgraj: (plik: File, typ: string, nadrzedny: string) => void;
}) {
  const [plik, setPlik] = useState<File | null>(null);
  const [typ, setTyp] = useState("umowa");
  const [nadrzedny, setNadrzedny] = useState("");

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-lg border bg-background p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (plik) onWgraj(plik, typ, typ === "aneks" ? nadrzedny : "");
      }}
    >
      <div className="min-w-64 flex-1 space-y-1.5">
        <Label htmlFor="plik-dok">Plik</Label>
        <input
          id="plik-dok"
          type="file"
          accept=".pdf,.docx,.jpg,.jpeg,.png"
          className="block w-full text-sm file:mr-3 file:rounded-md file:border file:bg-muted file:px-3 file:py-1.5 file:text-sm"
          onChange={(e) => setPlik(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="typ-dok">Rodzaj</Label>
        <select
          id="typ-dok"
          className="h-9 rounded-md border bg-transparent px-3 text-sm"
          value={typ}
          onChange={(e) => setTyp(e.target.value)}
        >
          {TYPY.map((t) => (
            <option key={t.wartosc} value={t.wartosc}>
              {t.etykieta}
            </option>
          ))}
        </select>
      </div>

      {typ === "aneks" && (
        <div className="space-y-1.5">
          <Label htmlFor="nadrzedny">Aneks do umowy</Label>
          <select
            id="nadrzedny"
            className="h-9 rounded-md border bg-transparent px-3 text-sm"
            value={nadrzedny}
            onChange={(e) => setNadrzedny(e.target.value)}
          >
            <option value="">— wybierz umowę —</option>
            {umowy.map((u) => (
              <option key={u.id} value={u.id}>
                {u.plik_nazwa_oryginalna ?? `dokument #${u.id}`}
              </option>
            ))}
          </select>
        </div>
      )}

      <Button type="submit" disabled={!plik || wgrywanie}>
        {wgrywanie ? "Wgrywam…" : "Wgraj"}
      </Button>
    </form>
  );
}
