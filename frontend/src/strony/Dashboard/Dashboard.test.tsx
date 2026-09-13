import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "./Dashboard";

const BUDYNKI = {
  pozycje: [
    {
      id: 1,
      nazwa: "Rycerska",
      nazwa_folderu: null,
      adres: "ul. Rycerska 18A",
      aktywny: true,
      uwagi: null,
      wersja: 1,
    },
    {
      id: 2,
      nazwa: "Nowatorów",
      nazwa_folderu: null,
      adres: null,
      aktywny: true,
      uwagi: null,
      wersja: 1,
    },
  ],
  wszystkich: 2,
  limit: 100,
  offset: 0,
};

function lokal(id: number, budynekId: number, oznaczenie: string) {
  return {
    lokal_id: id,
    budynek_id: budynekId,
    budynek_nazwa: budynekId === 1 ? "Rycerska" : "Nowatorów",
    oznaczenie,
    typ: "handlowy",
    status_lokalu: "wynajety",
    powierzchnia_ewidencyjna: "124.50",
    okres_najmu_id: 500 + id,
    najemca_id: 7,
    najemca_nazwa: "Piekarnia Złoty Kłos",
    status_umowy: "aktywna",
    data_przekazania: "2026-02-01",
    data_zakonczenia: "2028-01-31",
    powod_braku_daty_zakonczenia: null,
    czynsz: "9500.00",
    czynsz_waluta: "PLN",
    czynsz_rodzaj: "netto",
    waloryzacja_podlega: true,
    kompletnosc_procent: 80,
    brakujace_pola: [],
    zdarzen_otwartych: 0,
  };
}

// Kolejnosc jak z API: budynkami, wewnatrz budynku po oznaczeniu.
const LOKALE = {
  pozycje: [lokal(11, 1, "12"), lokal(12, 1, "14"), lokal(13, 2, "3")],
  wszystkich: 3,
  limit: 50,
  offset: 0,
};

/** Adresy, o ktore poprosil dashboard. Sprawdzamy na nich parametry zapytania. */
let zapytania: string[] = [];

function odpowiedz(dane: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(dane), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

beforeEach(() => {
  zapytania = [];
  vi.stubGlobal("fetch", (adres: string) => {
    zapytania.push(adres);
    if (adres.includes("/budynki")) return odpowiedz(BUDYNKI);
    if (adres.includes("/lokale")) return odpowiedz(LOKALE);
    throw new Error(`Nieoczekiwane żądanie: ${adres}`);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function pokaz() {
  const klient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={klient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Sama tabela. Nazwy budynkow sa tez w filtrze, wiec pytamy w jej granicach. */
async function tabelaLokali() {
  return within(await screen.findByRole("table"));
}

describe("Dashboard: lokale pogrupowane budynkami", () => {
  it("budynek jest nagłówkiem sekcji nad swoimi lokalami", async () => {
    pokaz();
    const tabela = await tabelaLokali();
    const naglowek = tabela.getByText("Rycerska").closest("tr")!;

    expect(within(naglowek).getByText("ul. Rycerska 18A")).toBeInTheDocument();
    expect(within(naglowek).getByText("lokali: 2")).toBeInTheDocument();
    expect(naglowek.className).toMatch(/border-y-2/);
    expect(tabela.getByText("Rycerska").className).toMatch(/uppercase/);
  });

  it("sekcje idą po kolei, a każdy lokal trafia pod swój budynek", async () => {
    pokaz();
    const tabela = await screen.findByRole("table");
    // Wiersze lokali maja role="link" (klikniecie otwiera profil), wiec nie
    // zlapie ich zapytanie o role "row". Czytamy je wprost z tbody.
    const kolejnosc = [...tabela.querySelectorAll("tbody tr")].map((w) =>
      (w.textContent ?? "").slice(0, 12),
    );

    expect(kolejnosc[0]).toMatch(/^Rycerska/);
    expect(kolejnosc[1]).toMatch(/^12/);
    expect(kolejnosc[2]).toMatch(/^14/);
    expect(kolejnosc[3]).toMatch(/^Nowatoró/);
    expect(kolejnosc[4]).toMatch(/^3/);
  });

  it("wiersz lokalu nie powtarza już nazwy budynku", async () => {
    pokaz();
    // Nazwa stala pod oznaczeniem w kazdym wierszu. Przy sekcjach to szum.
    const tabela = await tabelaLokali();
    const wiersz = tabela.getByText("12").closest("tr")!;
    expect(within(wiersz).queryByText("Rycerska")).toBeNull();
  });

  it("pyta API o dane posortowane budynkami", async () => {
    pokaz();
    await tabelaLokali();
    // Inna kolumna sortowania wymieszalaby budynki i sekcje przestalyby
    // cokolwiek znaczyc.
    expect(zapytania.some((a) => a.includes("sortuj=budynek"))).toBe(true);
  });
});
