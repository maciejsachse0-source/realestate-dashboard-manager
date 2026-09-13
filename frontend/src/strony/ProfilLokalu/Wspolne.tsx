import type { ReactNode } from "react";
import { BRAK_DANYCH } from "@/funkcje/format";

/** Wiersz „etykieta: wartość". Powtarza się na każdej zakładce profilu. */
export function Pole({
  etykieta,
  children,
}: {
  etykieta: string;
  children: ReactNode;
}) {
  const puste = children === null || children === undefined || children === "";
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b px-3 py-2.5 last:border-b-0">
      <span className="w-56 shrink-0 text-sm text-muted-foreground">
        {etykieta}
      </span>
      <span className="text-sm">
        {puste ? (
          <span className="text-muted-foreground">{BRAK_DANYCH}</span>
        ) : (
          children
        )}
      </span>
    </div>
  );
}

export function Karta({
  tytul,
  children,
}: {
  tytul?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-background">
      {tytul && (
        <h2 className="border-b px-3 py-2 text-sm font-medium">{tytul}</h2>
      )}
      {children}
    </section>
  );
}

/** Odznaka statusu weryfikacji. Wartość niezatwierdzona musi rzucać się w oczy
 *  (decyzja D4), bo nie wchodzi ani do stanu, ani do alertów. */
export function OdznakaWeryfikacji({ status }: { status: string }) {
  if (status === "zatwierdzona") return null;
  const kolor =
    status === "odrzucona"
      ? "border-destructive/50 text-destructive"
      : "border-amber-400 text-amber-700";
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-xs ${kolor}`}
      title="Nie wchodzi do stanu efektywnego"
    >
      {status}
    </span>
  );
}
