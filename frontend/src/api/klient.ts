/**
 * Klient HTTP.
 *
 * Program nie ma logowania (ADR 009), więc nie ma tu ani sesji, ani nagłówka
 * uwierzytelniającego. `credentials: 'same-origin'` zostaje, bo nic nie kosztuje.
 */

export class BladApi extends Error {
  readonly status: number;
  /** Wersja rekordu, która jest teraz w bazie. Wypełniona przy konflikcie 409. */
  readonly wersjaBiezaca: number | null;

  constructor(
    status: number,
    message: string,
    wersjaBiezaca: number | null = null,
  ) {
    super(message);
    this.name = "BladApi";
    this.status = status;
    this.wersjaBiezaca = wersjaBiezaca;
  }

  /** Czy ktoś zapisał zmiany przed nami. */
  get konflikt(): boolean {
    return this.status === 409;
  }
}

const PODSTAWA = "/api/v1";

async function zadanie<T>(
  sciezka: string,
  opcje: RequestInit & { params?: Record<string, unknown> } = {},
): Promise<T> {
  const { params, ...reszta } = opcje;

  let adres = `${PODSTAWA}${sciezka}`;
  if (params) {
    const zapytanie = new URLSearchParams();
    for (const [klucz, wartosc] of Object.entries(params)) {
      // Pomijamy puste filtry, żeby nie wysyłać `?szukaj=` i nie zawężać wyniku
      // do rekordów z pustym tekstem.
      if (wartosc === undefined || wartosc === null || wartosc === "") continue;
      zapytanie.set(klucz, String(wartosc));
    }
    const tekst = zapytanie.toString();
    if (tekst) adres += `?${tekst}`;
  }

  const odpowiedz = await fetch(adres, {
    ...reszta,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(reszta.body ? { "Content-Type": "application/json" } : {}),
      ...reszta.headers,
    },
  });

  if (odpowiedz.status === 204) {
    return undefined as T;
  }

  if (!odpowiedz.ok) {
    const naglowek = odpowiedz.headers.get("X-Wersja-Biezaca");
    let komunikat = `Błąd ${odpowiedz.status}`;
    try {
      const tresc = (await odpowiedz.json()) as { detail?: unknown };
      if (typeof tresc.detail === "string") {
        komunikat = tresc.detail;
      } else if (Array.isArray(tresc.detail)) {
        // Walidacja Pydantica zwraca listę problemów. Sklejamy je w jedno zdanie,
        // bo użytkownik nie czyta struktur JSON.
        komunikat = tresc.detail
          .map((p) => (p as { msg?: string }).msg ?? "")
          .filter(Boolean)
          .join("; ");
      }
    } catch {
      // Odpowiedź bez treści JSON. Zostaje komunikat z kodem.
    }
    throw new BladApi(
      odpowiedz.status,
      komunikat,
      naglowek ? Number(naglowek) : null,
    );
  }

  return (await odpowiedz.json()) as T;
}

export function pobierz<T>(
  sciezka: string,
  params?: Record<string, unknown>,
): Promise<T> {
  return zadanie<T>(sciezka, { method: "GET", params });
}

export function wyslij<T>(sciezka: string, dane?: unknown): Promise<T> {
  return zadanie<T>(sciezka, {
    method: "POST",
    body: dane === undefined ? undefined : JSON.stringify(dane),
  });
}

export function zapisz<T>(sciezka: string, dane: unknown): Promise<T> {
  return zadanie<T>(sciezka, { method: "PUT", body: JSON.stringify(dane) });
}

export function usun(sciezka: string): Promise<void> {
  return zadanie<void>(sciezka, { method: "DELETE" });
}
