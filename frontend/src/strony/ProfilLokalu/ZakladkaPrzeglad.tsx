import { useState } from 'react'
import type { Lokal, OkresNajmu, StanNaDzien } from '@/api/typy'
import { formatujDate, formatujKwote, formatujPowierzchnie } from '@/funkcje/format'
import { czytelnaNazwaPola } from '@/funkcje/nazwy'
import { Button } from '@/components/ui/button'
import { FormularzUmowy } from './Formularze'
import { Karta, OdznakaWeryfikacji, Pole } from './Wspolne'

const ETYKIETY_TYPU: Record<string, string> = {
  handlowy: 'handlowy',
  biurowy: 'biurowy',
  magazyn: 'magazyn',
  miejsce_postojowe: 'miejsce postojowe',
  inny: 'inny',
}

const ETYKIETY_STATUSU: Record<string, string> = {
  wolny: 'Wolny',
  wynajety: 'Wynajęty',
  w_trakcie_wydania: 'W trakcie wydania',
  przygotowanie: 'W przygotowaniu',
  aktywna: 'Aktywna',
  wypowiedziana: 'Wypowiedziana',
  zakonczona: 'Zakończona',
}

const NAZWY_PARAMETROW: Record<string, string> = {
  czynsz_podstawowy: 'Czynsz podstawowy',
  stawka_m2: 'Stawka za m²',
  powierzchnia: 'Powierzchnia z umowy',
  data_zakonczenia: 'Data zakończenia',
  oplata_eksploatacyjna: 'Opłata eksploatacyjna',
}

export function ZakladkaPrzeglad({
  stan,
  lokal,
  okres,
}: {
  stan: StanNaDzien
  lokal: Lokal
  okres: OkresNajmu | null
}) {
  const [zakladanie, setZakladanie] = useState(false)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Karta tytul="Lokal">
        <Pole etykieta="Oznaczenie">{lokal.oznaczenie}</Pole>
        <Pole etykieta="Typ">{ETYKIETY_TYPU[lokal.typ] ?? lokal.typ}</Pole>
        <Pole etykieta="Status">{ETYKIETY_STATUSU[lokal.status] ?? lokal.status}</Pole>
        <Pole etykieta="Kondygnacja">{lokal.kondygnacja}</Pole>
        <Pole etykieta="Powierzchnia z ewidencji">
          {lokal.powierzchnia_ewidencyjna
            ? formatujPowierzchnie(lokal.powierzchnia_ewidencyjna)
            : null}
        </Pole>
        <Pole etykieta="Uwagi">{lokal.uwagi}</Pole>
      </Karta>

      <Karta tytul="Umowa">
        {okres === null ? (
          <div className="px-3 py-8 text-center">
            <p className="text-sm text-muted-foreground">Lokal nie ma bieżącej umowy najmu.</p>
            <Button className="mt-3" onClick={() => setZakladanie(true)}>
              Załóż umowę
            </Button>
          </div>
        ) : (
          <>
            <Pole etykieta="Status">{ETYKIETY_STATUSU[okres.status] ?? okres.status}</Pole>
            <Pole etykieta="Data zawarcia">{formatujDate(okres.data_zawarcia)}</Pole>
            <Pole etykieta="Data przekazania">{formatujDate(okres.data_przekazania)}</Pole>
            <Pole etykieta="Okres">
              {okres.okres_zawarcia_miesiace ? `${okres.okres_zawarcia_miesiace} mies.` : null}
            </Pole>
            <Pole etykieta="Liczony od">
              {okres.bazuje_na_dacie === 'data_przekazania'
                ? 'daty przekazania lokalu'
                : 'daty zawarcia umowy'}
            </Pole>
            <Pole etykieta="Koniec umowy">
              {stan.data_zakonczenia ? (
                formatujDate(stan.data_zakonczenia)
              ) : (
                <span className="text-amber-700">nieustalona</span>
              )}
            </Pole>
            <Pole etykieta="Okres wypowiedzenia">
              {okres.okres_wypowiedzenia_miesiace
                ? `${okres.okres_wypowiedzenia_miesiace} mies.`
                : null}
            </Pole>
            <Pole etykieta="Waloryzacja">
              {okres.waloryzacja_podlega
                ? `tak, w miesiącu ${okres.waloryzacja_miesiac ?? '?'}`
                : 'nie'}
            </Pole>
          </>
        )}
      </Karta>

      <FormularzUmowy
        otwarty={zakladanie}
        onZamknij={() => setZakladanie(false)}
        lokalId={lokal.id}
      />

      <Karta tytul="Warunki obowiązujące">
        {Object.keys(stan.parametry).length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            Brak zatwierdzonych warunków. Wartości czekające na decyzję są w zakładce Historia.
          </p>
        ) : (
          Object.entries(stan.parametry).map(([klucz, wartosc]) => (
            <Pole key={klucz} etykieta={NAZWY_PARAMETROW[klucz] ?? czytelnaNazwaPola(klucz)}>
              <span className="inline-flex flex-wrap items-baseline gap-2">
                <span className="font-medium tabular-nums">
                  {wartosc.typ === 'kwota'
                    ? formatujKwote(wartosc.wartosc, wartosc.waluta ?? 'PLN')
                    : wartosc.wartosc}
                  {wartosc.rodzaj_kwoty && (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      {wartosc.rodzaj_kwoty}
                    </span>
                  )}
                </span>
                <OdznakaWeryfikacji status={wartosc.status_weryfikacji} />
                <span className="text-xs text-muted-foreground">
                  od {formatujDate(wartosc.obowiazuje_od)}
                  {wartosc.zrodlo_paragraf && ` · ${wartosc.zrodlo_paragraf}`}
                  {wartosc.zrodlo_strona && `, str. ${wartosc.zrodlo_strona}`}
                </span>
              </span>
            </Pole>
          ))
        )}
      </Karta>

      <Karta tytul="Braki">
        {stan.brakujace_pola.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-emerald-700">
            Profil jest kompletny.
          </p>
        ) : (
          <ul className="px-3 py-2 text-sm">
            {stan.brakujace_pola.map((pole) => (
              <li key={pole} className="border-b py-1.5 last:border-b-0">
                {czytelnaNazwaPola(pole)}
              </li>
            ))}
          </ul>
        )}
      </Karta>
    </div>
  )
}
