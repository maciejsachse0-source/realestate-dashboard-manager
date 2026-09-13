import { useState } from "react";
import type { StatusPrzegladu } from "@/api/typy";
import { useProtokolPrzegladu, usePrzeglady } from "@/api/zapytania";
import { formatujDate } from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormularzPrzegladu } from "./Formularze";
import { Karta } from "./Wspolne";

const OPIS: Record<StatusPrzegladu, string> = {
  aktualny: "Aktualny",
  zbliza_sie: "Zbliża się",
  przeterminowany: "Przeterminowany",
  nieustalony: "Nieustalony",
};

/**
 * Obowiązki przeglądów (reguła R7).
 *
 * Element jest osobnym wierszem, a nie jednym polem tekstowym — dopiero wtedy
 * da się zapytać „wszystkie gaśnice do przeglądu w tym kwartale".
 *
 * Status `nieustalony` znaczy, że nie znamy daty ostatniego przeglądu.
 * To nie to samo co `aktualny`, choć na pierwszy rzut oka wygląda równie
 * niewinnie. Wpisanie protokołu jest jedyną drogą, która przesuwa termin.
 */
export function ZakladkaPrzeglady({ lokalId }: { lokalId: number }) {
  const przeglady = usePrzeglady(lokalId);
  const protokol = useProtokolPrzegladu();
  const [rejestrowany, setRejestrowany] = useState<number | null>(null);
  const [data, setData] = useState(new Date().toISOString().slice(0, 10));
  const [otwarty, setOtwarty] = useState(false);

  if (przeglady.isPending) return <Ladowanie wierszy={3} />;
  if (przeglady.isError) {
    return (
      <Blad
        komunikat={
          przeglady.error instanceof Error
            ? przeglady.error.message
            : "Nieznany błąd."
        }
        ponow={() => void przeglady.refetch()}
      />
    );
  }
  if (przeglady.data.length === 0) {
    return (
      <>
        <Pusto
          tytul="Brak obowiązków przeglądów"
          opis="Wpisz elementy wymagające przeglądu (gaśnice, brama, hydranty), żeby system pilnował ich terminów."
          akcja={
            <Button onClick={() => setOtwarty(true)}>Dodaj przegląd</Button>
          }
        />
        <FormularzPrzegladu
          otwarty={otwarty}
          onZamknij={() => setOtwarty(false)}
          lokalId={lokalId}
        />
      </>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setOtwarty(true)}>Dodaj przegląd</Button>
      </div>
      <Karta>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Element</th>
                <th className="px-3 py-2 font-medium">Obciąża</th>
                <th className="px-3 py-2 font-medium">Częstotliwość</th>
                <th className="px-3 py-2 font-medium">Ostatni</th>
                <th className="px-3 py-2 font-medium">Następny</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {przeglady.data.map((p) => (
                <tr key={p.id} className="border-b last:border-b-0">
                  <td className="px-3 py-2.5">{p.element}</td>
                  <td className="px-3 py-2.5">{p.kto_obciazany}</td>
                  <td className="px-3 py-2.5">
                    {p.czestotliwosc_miesiace
                      ? `${p.czestotliwosc_miesiace} mies.`
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    {formatujDate(p.ostatni_przeglad_data)}
                  </td>
                  <td className="px-3 py-2.5">
                    {formatujDate(p.nastepny_przeglad_data)}
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge
                      variant={
                        p.status === "przeterminowany"
                          ? "destructive"
                          : p.status === "aktualny"
                            ? "default"
                            : "secondary"
                      }
                    >
                      {OPIS[p.status]}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {rejestrowany === p.id ? (
                      <span className="flex items-center justify-end gap-2">
                        <Input
                          type="date"
                          className="h-8 w-36"
                          value={data}
                          onChange={(e) => setData(e.target.value)}
                          aria-label="Data protokołu"
                        />
                        <Button
                          size="sm"
                          disabled={protokol.isPending}
                          onClick={() =>
                            protokol.mutate(
                              { id: p.id, data },
                              { onSuccess: () => setRejestrowany(null) },
                            )
                          }
                        >
                          Zapisz
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setRejestrowany(null)}
                        >
                          Anuluj
                        </Button>
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRejestrowany(p.id)}
                      >
                        Wpisz protokół
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Karta>
      <FormularzPrzegladu
        otwarty={otwarty}
        onZamknij={() => setOtwarty(false)}
        lokalId={lokalId}
      />
    </div>
  );
}
