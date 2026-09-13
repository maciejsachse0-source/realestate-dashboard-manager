import { czytelnaNazwaPola } from "@/funkcje/nazwy";

/**
 * Wskaznik kompletnosci profilu (decyzja D6, regula R9).
 *
 * Dziury w danych sa widoczne i policzalne, bo to one generuja ryzyko.
 * To jedyny sposob, zeby migracja starych umow kiedykolwiek sie skonczyla.
 */
export function PasekKompletnosci({
  procent,
  braki,
}: {
  procent: number | null;
  braki: string[];
}) {
  if (procent === null) {
    return <span className="text-muted-foreground">—</span>;
  }

  // Prog 40 procent jest regula produktowa, nie estetyka: ponizej niego
  // system nie ma dosc danych, zeby cokolwiek na nich opierac.
  const kolor =
    procent === 100
      ? "bg-emerald-600"
      : procent >= 40
        ? "bg-amber-500"
        : "bg-destructive";

  const opis =
    braki.length === 0
      ? "Profil kompletny"
      : `Brakuje: ${braki.map(czytelnaNazwaPola).join(", ")}`;

  return (
    <div className="flex items-center gap-2" title={opis}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${kolor}`} style={{ width: `${procent}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {procent}%
      </span>
    </div>
  );
}
