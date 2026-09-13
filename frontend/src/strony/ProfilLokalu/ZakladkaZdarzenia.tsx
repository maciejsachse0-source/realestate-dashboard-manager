import type { Zdarzenie } from "@/api/typy";
import { formatujDate } from "@/funkcje/format";
import { Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Karta } from "./Wspolne";

/** Zdarzenia tego lokalu. Obsługa jest w kokpicie terminów — tu tylko podgląd. */
export function ZakladkaZdarzenia({ zdarzenia }: { zdarzenia: Zdarzenie[] }) {
  if (zdarzenia.length === 0) {
    return (
      <Pusto
        tytul="Brak zdarzeń"
        opis="Ten lokal nie wygenerował dotąd żadnego terminu do pilnowania."
      />
    );
  }

  const otwarte = zdarzenia.filter((z) => z.status === "otwarte");
  const zamkniete = zdarzenia.filter((z) => z.status !== "otwarte");

  return (
    <div className="space-y-4">
      {otwarte.length > 0 && (
        <Karta tytul={`Wymagają uwagi (${otwarte.length})`}>
          <ul className="divide-y">
            {otwarte.map((z) => (
              <Wiersz key={z.id} zdarzenie={z} />
            ))}
          </ul>
        </Karta>
      )}

      {zamkniete.length > 0 && (
        <Karta tytul={`Załatwione i odroczone (${zamkniete.length})`}>
          <ul className="divide-y opacity-70">
            {zamkniete.map((z) => (
              <Wiersz key={z.id} zdarzenie={z} />
            ))}
          </ul>
        </Karta>
      )}
    </div>
  );
}

function Wiersz({ zdarzenie }: { zdarzenie: Zdarzenie }) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
      <Badge
        variant={
          zdarzenie.waga === "krytyczne"
            ? "destructive"
            : zdarzenie.waga === "ostrzezenie"
              ? "secondary"
              : "outline"
        }
      >
        {zdarzenie.waga}
      </Badge>
      <span className="min-w-0 flex-1">{zdarzenie.tresc}</span>
      {zdarzenie.notatka && (
        <span className="text-xs text-muted-foreground">
          „{zdarzenie.notatka}"
        </span>
      )}
      <span className="text-xs text-muted-foreground">
        {formatujDate(zdarzenie.data_zdarzenia)}
        {zdarzenie.status === "odroczone" &&
          zdarzenie.odroczone_do &&
          ` · odroczone do ${formatujDate(zdarzenie.odroczone_do)}`}
        {zdarzenie.status === "obsluzone" && " · obsłużone"}
      </span>
    </li>
  );
}
