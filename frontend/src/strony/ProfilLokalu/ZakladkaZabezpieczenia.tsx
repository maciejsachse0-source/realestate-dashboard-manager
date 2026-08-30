import { useState } from "react";
import type { StatusZabezpieczenia, Zabezpieczenie } from "@/api/typy";
import { BladApi } from "@/api/klient";
import { useZabezpieczenia, useZmienZabezpieczenie } from "@/api/zapytania";
import { formatujDate, formatujKwote } from "@/funkcje/format";
import { Blad, Ladowanie, Pusto } from "@/komponenty/Stany";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormularzZabezpieczenia } from "./Formularze";
import { Karta } from "./Wspolne";

const NAZWY: Record<string, string> = {
  kaucja: "Kaucja",
  weksel: "Weksel",
  gwarancja_bankowa: "Gwarancja bankowa",
  polisa: "Polisa",
};

const OPIS_STATUSU: Record<StatusZabezpieczenia, string> = {
  wymagane: "Wymagane",
  dostarczone: "Dostarczone",
  zwrocone: "Zwrócone",
  zatrzymane: "Zatrzymane",
  brak: "Brak",
};

/**
 * Przejścia dozwolone przez regułę R4. Front pokazuje tylko te, które przejdą.
 * Serwer i tak sprawdza je ponownie — interfejs nie jest zabezpieczeniem,
 * tylko wygodą.
 */
const DOZWOLONE: Record<StatusZabezpieczenia, StatusZabezpieczenia[]> = {
  brak: ["wymagane"],
  wymagane: ["dostarczone", "brak"],
  dostarczone: ["zwrocone", "zatrzymane"],
  // Powrot do 'dostarczone' istnieje, bo zwrot i zatrzymanie sa o jeden klik
  // od pomylki, a wczesniej nie bylo z nich wyjscia.
  zwrocone: ["dostarczone"],
  zatrzymane: ["dostarczone"],
};

/** Powrot ze stanu koncowego nazywa sie cofnieciem, nie kolejnym krokiem. */
function etykietaPrzycisku(
  obecny: StatusZabezpieczenia,
  nowy: StatusZabezpieczenia,
): string {
  const cofniecie =
    nowy === "dostarczone" &&
    (obecny === "zwrocone" || obecny === "zatrzymane");
  return cofniecie ? "Cofnij" : OPIS_STATUSU[nowy];
}

function dzisiaj(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ZakladkaZabezpieczenia({
  okresId,
}: {
  okresId: number | null;
}) {
  const zabezpieczenia = useZabezpieczenia(okresId);
  const zmiana = useZmienZabezpieczenie();
  const [blad, setBlad] = useState<string | null>(null);
  const [otwarty, setOtwarty] = useState(false);

  if (okresId === null) {
    return <Pusto tytul="Brak umowy" opis="Bez umowy nie ma zabezpieczeń." />;
  }
  if (zabezpieczenia.isPending) return <Ladowanie wierszy={2} />;
  if (zabezpieczenia.isError) {
    return (
      <Blad
        komunikat={
          zabezpieczenia.error instanceof Error
            ? zabezpieczenia.error.message
            : "Nieznany błąd."
        }
        ponow={() => void zabezpieczenia.refetch()}
      />
    );
  }
  if (zabezpieczenia.data.length === 0) {
    return (
      <>
        <Pusto
          tytul="Brak zabezpieczeń"
          opis="Kaucja i polisa są polami krytycznymi profilu. Dopóki ich nie ma, kompletność nie sięgnie 100%."
          akcja={
            <Button onClick={() => setOtwarty(true)}>
              Dodaj zabezpieczenie
            </Button>
          }
        />
        <FormularzZabezpieczenia
          otwarty={otwarty}
          onZamknij={() => setOtwarty(false)}
          okresId={okresId}
        />
      </>
    );
  }

  function zmienStatus(z: Zabezpieczenie, nowy: StatusZabezpieczenia) {
    setBlad(null);
    zmiana.mutate(
      {
        id: z.id,
        dane: {
          rodzaj: z.rodzaj,
          status: nowy,
          wymagana_wartosc: z.wymagana_wartosc,
          wymagana_waluta: z.wymagana_waluta,
          wymagana_rodzaj_kwoty: z.wymagana_rodzaj_kwoty,
          wymagana_stawka_vat: z.wymagana_stawka_vat,
          sposob_wyliczenia: z.sposob_wyliczenia,
          data_wymagalnosci: z.data_wymagalnosci,
          // Odnotowanie dostarczenia bez daty byłoby śladem połowicznym.
          data_dostarczenia:
            nowy === "dostarczone" && !z.data_dostarczenia
              ? dzisiaj()
              : z.data_dostarczenia,
          data_waznosci: z.data_waznosci,
          // Cofniecie zwrotu zdejmuje jego date. Zostawiona kluciloby sie
          // ze statusem i wygladalaby na kaucje zwrocona mimo wszystko.
          data_zwrotu:
            nowy === "zwrocone" && !z.data_zwrotu
              ? dzisiaj()
              : nowy === "dostarczone"
                ? null
                : z.data_zwrotu,
          miejsce_przechowywania: z.miejsce_przechowywania,
          dokument_id: z.dokument_id,
          uwagi: z.uwagi,
          wersja: z.wersja,
        },
      },
      {
        onError: (e) =>
          setBlad(
            e instanceof BladApi ? e.message : "Nie udało się zapisać zmiany.",
          ),
      },
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setOtwarty(true)}>Dodaj zabezpieczenie</Button>
      </div>

      {blad && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {blad}
        </p>
      )}

      {zabezpieczenia.data.map((z) => (
        <Karta key={z.id} tytul={NAZWY[z.rodzaj] ?? z.rodzaj}>
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 px-3 py-3">
            <div>
              <p className="text-xs text-muted-foreground">Status</p>
              <Badge
                variant={z.status === "dostarczone" ? "default" : "secondary"}
                className="mt-1"
              >
                {OPIS_STATUSU[z.status]}
              </Badge>
            </div>

            <div>
              <p className="text-xs text-muted-foreground">Wymagana wartość</p>
              <p className="mt-1 text-sm tabular-nums">
                {z.wymagana_wartosc
                  ? formatujKwote(
                      z.wymagana_wartosc,
                      z.wymagana_waluta ?? "PLN",
                    )
                  : z.sposob_wyliczenia || "—"}
              </p>
            </div>

            <div>
              <p className="text-xs text-muted-foreground">
                Termin dostarczenia
              </p>
              <p className="mt-1 text-sm">
                {formatujDate(z.data_wymagalnosci)}
              </p>
            </div>

            <div>
              <p className="text-xs text-muted-foreground">Dostarczono</p>
              <p className="mt-1 text-sm">
                {formatujDate(z.data_dostarczenia)}
              </p>
            </div>

            {z.rodzaj === "polisa" && (
              <div>
                <p className="text-xs text-muted-foreground">Ważna do</p>
                <p className="mt-1 text-sm">{formatujDate(z.data_waznosci)}</p>
              </div>
            )}

            <div className="ml-auto flex gap-2">
              {DOZWOLONE[z.status].map((nowy) => (
                <Button
                  key={nowy}
                  variant="outline"
                  size="sm"
                  disabled={zmiana.isPending}
                  onClick={() => zmienStatus(z, nowy)}
                >
                  {etykietaPrzycisku(z.status, nowy)}
                </Button>
              ))}
            </div>
          </div>
        </Karta>
      ))}

      <FormularzZabezpieczenia
        otwarty={otwarty}
        onZamknij={() => setOtwarty(false)}
        okresId={okresId}
      />
    </div>
  );
}
