import { useState } from 'react'

import {
  useDodajOkresNajmu,
  useDodajParametr,
  useDodajPrzeglad,
  useDodajSkladnik,
  useDodajZabezpieczenie,
  useNajemcy,
} from '@/api/zapytania'
import {
  DialogFormularza,
  PoleTekstowe,
  PoleWyboru,
  PoleZaznaczenia,
  liczbaLubNull,
  pustyNaNull,
} from '@/komponenty/Formularz'

const MIESIACE = [
  'styczeń',
  'luty',
  'marzec',
  'kwiecień',
  'maj',
  'czerwiec',
  'lipiec',
  'sierpień',
  'wrzesień',
  'październik',
  'listopad',
  'grudzień',
].map((nazwa, indeks) => ({ wartosc: String(indeks + 1), etykieta: nazwa }))

/** Nowa umowa dla lokalu. Bez niej lokal nie ma czego pokazywać. */
export function FormularzUmowy({
  otwarty,
  onZamknij,
  lokalId,
}: {
  otwarty: boolean
  onZamknij: () => void
  lokalId: number
}) {
  const dodaj = useDodajOkresNajmu()
  const najemcy = useNajemcy()
  const [najemcaId, setNajemcaId] = useState('')
  const [dataZawarcia, setDataZawarcia] = useState('')
  const [dataPrzekazania, setDataPrzekazania] = useState('')
  const [bazuje, setBazuje] = useState('data_przekazania')
  const [okresMiesiace, setOkresMiesiace] = useState('')
  const [wypowiedzenie, setWypowiedzenie] = useState('')
  const [waloryzacja, setWaloryzacja] = useState(false)
  const [miesiacWaloryzacji, setMiesiacWaloryzacji] = useState('1')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={onZamknij}
      tytul="Nowa umowa najmu"
      opis="Data zakończenia wyliczy się sama z okresu i daty, od której liczymy."
      etykietaZapisu="Załóż umowę"
      onZapisz={() =>
        dodaj.mutateAsync({
          lokal_id: lokalId,
          najemca_id: Number(najemcaId),
          data_zawarcia: pustyNaNull(dataZawarcia),
          data_przekazania: pustyNaNull(dataPrzekazania),
          bazuje_na_dacie: bazuje,
          okres_zawarcia_miesiace: liczbaLubNull(okresMiesiace),
          okres_wypowiedzenia_miesiace: liczbaLubNull(wypowiedzenie),
          waloryzacja_podlega: waloryzacja,
          waloryzacja_miesiac: waloryzacja ? Number(miesiacWaloryzacji) : null,
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleWyboru
        nazwa="najemca"
        etykieta="Najemca"
        wartosc={najemcaId}
        onZmiana={setNajemcaId}
        wymagane
        opcje={(najemcy.data?.pozycje ?? []).map((n) => ({
          wartosc: String(n.id),
          etykieta: n.nazwa_pelna,
        }))}
        podpowiedz="Najemcy dodaje się w Kartotece."
      />
      <PoleTekstowe
        nazwa="data_zawarcia"
        etykieta="Data zawarcia"
        typ="date"
        wartosc={dataZawarcia}
        onZmiana={setDataZawarcia}
      />
      <PoleTekstowe
        nazwa="data_przekazania"
        etykieta="Data przekazania lokalu"
        typ="date"
        wartosc={dataPrzekazania}
        onZmiana={setDataPrzekazania}
        podpowiedz="Z protokołu przekazania. Bez niej data zakończenia zostanie nieustalona."
      />
      <PoleWyboru
        nazwa="bazuje"
        etykieta="Okres liczony od"
        wartosc={bazuje}
        onZmiana={setBazuje}
        wymagane
        pusteEtykieta=""
        opcje={[
          { wartosc: 'data_przekazania', etykieta: 'daty przekazania lokalu' },
          { wartosc: 'data_zawarcia', etykieta: 'daty zawarcia umowy' },
        ]}
      />
      <PoleTekstowe
        nazwa="okres"
        etykieta="Okres zawarcia (miesiące)"
        typ="number"
        min="1"
        wartosc={okresMiesiace}
        onZmiana={setOkresMiesiace}
      />
      <PoleTekstowe
        nazwa="wypowiedzenie"
        etykieta="Okres wypowiedzenia (miesiące)"
        typ="number"
        min="1"
        wartosc={wypowiedzenie}
        onZmiana={setWypowiedzenie}
      />
      <PoleZaznaczenia
        nazwa="waloryzacja"
        etykieta="Umowa podlega waloryzacji"
        wartosc={waloryzacja}
        onZmiana={setWaloryzacja}
      />
      {waloryzacja && (
        <PoleWyboru
          nazwa="miesiac_waloryzacji"
          etykieta="Miesiąc waloryzacji"
          wartosc={miesiacWaloryzacji}
          onZmiana={setMiesiacWaloryzacji}
          wymagane
          pusteEtykieta=""
          opcje={MIESIACE}
        />
      )}
    </DialogFormularza>
  )
}

/**
 * Nowa wartość parametru umowy.
 *
 * Wchodzi jako „zaproponowana" i nie liczy się, dopóki ktoś jej nie zatwierdzi
 * w zakładce Historia. Decyzja D4 nie robi wyjątku dla wpisania z klawiatury.
 */
export function FormularzParametru({
  otwarty,
  onZamknij,
  okresId,
}: {
  otwarty: boolean
  onZamknij: () => void
  okresId: number
}) {
  const dodaj = useDodajParametr()
  const [klucz, setKlucz] = useState('czynsz_podstawowy')
  const [typ, setTyp] = useState('kwota')
  const [kwota, setKwota] = useState('')
  const [rodzaj, setRodzaj] = useState('netto')
  const [vat, setVat] = useState('23')
  const [liczba, setLiczba] = useState('')
  const [data, setData] = useState('')
  const [tekst, setTekst] = useState('')
  const [obowiazujeOd, setObowiazujeOd] = useState('')
  const [paragraf, setParagraf] = useState('')
  const [strona, setStrona] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={onZamknij}
      tytul="Nowy warunek umowy"
      opis="Wartość trafi do zakładki Historia jako propozycja. Zacznie obowiązywać po zatwierdzeniu."
      onZapisz={() =>
        dodaj.mutateAsync({
          okresId,
          dane: {
            klucz: klucz.trim(),
            typ_wartosci: typ,
            obowiazuje_od: obowiazujeOd,
            wartosc_kwota: typ === 'kwota' ? liczbaLubNull(kwota) : null,
            wartosc_waluta: typ === 'kwota' ? 'PLN' : null,
            wartosc_rodzaj_kwoty: typ === 'kwota' ? rodzaj : null,
            wartosc_stawka_vat: typ === 'kwota' && rodzaj === 'netto' ? liczbaLubNull(vat) : null,
            wartosc_liczba: typ === 'liczba' ? liczbaLubNull(liczba) : null,
            wartosc_data: typ === 'data' ? pustyNaNull(data) : null,
            wartosc_tekst: typ === 'tekst' ? pustyNaNull(tekst) : null,
            zrodlo_paragraf: pustyNaNull(paragraf),
            zrodlo_strona: liczbaLubNull(strona),
          },
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleWyboru
        nazwa="klucz"
        etykieta="Czego dotyczy"
        wartosc={klucz}
        onZmiana={setKlucz}
        wymagane
        pusteEtykieta=""
        opcje={[
          { wartosc: 'czynsz_podstawowy', etykieta: 'Czynsz podstawowy' },
          { wartosc: 'oplata_eksploatacyjna', etykieta: 'Opłata eksploatacyjna' },
          { wartosc: 'stawka_m2', etykieta: 'Stawka za m²' },
          { wartosc: 'powierzchnia', etykieta: 'Powierzchnia z umowy' },
        ]}
      />
      <PoleWyboru
        nazwa="typ"
        etykieta="Rodzaj wartości"
        wartosc={typ}
        onZmiana={setTyp}
        wymagane
        pusteEtykieta=""
        opcje={[
          { wartosc: 'kwota', etykieta: 'Kwota' },
          { wartosc: 'liczba', etykieta: 'Liczba' },
          { wartosc: 'data', etykieta: 'Data' },
          { wartosc: 'tekst', etykieta: 'Tekst' },
        ]}
      />

      {typ === 'kwota' && (
        <>
          <PoleTekstowe
            nazwa="kwota"
            etykieta="Kwota"
            typ="number"
            step="0.01"
            wartosc={kwota}
            onZmiana={setKwota}
            wymagane
          />
          <PoleWyboru
            nazwa="rodzaj"
            etykieta="Netto czy brutto"
            wartosc={rodzaj}
            onZmiana={setRodzaj}
            wymagane
            pusteEtykieta=""
            opcje={[
              { wartosc: 'netto', etykieta: 'netto' },
              { wartosc: 'brutto', etykieta: 'brutto' },
            ]}
            podpowiedz="Kwota bez tej informacji nie jest kwotą — nie da się jej przeliczyć."
          />
          {rodzaj === 'netto' && (
            <PoleTekstowe
              nazwa="vat"
              etykieta="Stawka VAT (%)"
              typ="number"
              step="0.01"
              wartosc={vat}
              onZmiana={setVat}
              wymagane
            />
          )}
        </>
      )}

      {typ === 'liczba' && (
        <PoleTekstowe
          nazwa="liczba"
          etykieta="Wartość"
          typ="number"
          step="0.000001"
          wartosc={liczba}
          onZmiana={setLiczba}
          wymagane
        />
      )}

      {typ === 'data' && (
        <PoleTekstowe
          nazwa="wartosc_data"
          etykieta="Data"
          typ="date"
          wartosc={data}
          onZmiana={setData}
          wymagane
        />
      )}

      {typ === 'tekst' && (
        <PoleTekstowe nazwa="tekst" etykieta="Treść" wartosc={tekst} onZmiana={setTekst} wymagane />
      )}

      <PoleTekstowe
        nazwa="obowiazuje_od"
        etykieta="Obowiązuje od"
        typ="date"
        wartosc={obowiazujeOd}
        onZmiana={setObowiazujeOd}
        wymagane
        podpowiedz="Aneks nie nadpisuje poprzedniej wartości, tylko zaczyna obowiązywać od swojej daty."
      />
      <PoleTekstowe
        nazwa="paragraf"
        etykieta="Paragraf w dokumencie"
        wartosc={paragraf}
        onZmiana={setParagraf}
        podpowiedz="Na przykład: par. 5 ust. 1. Dzięki temu widać, skąd ta liczba."
      />
      <PoleTekstowe
        nazwa="strona"
        etykieta="Strona"
        typ="number"
        min="1"
        wartosc={strona}
        onZmiana={setStrona}
      />
    </DialogFormularza>
  )
}

/** Składnik opłaty: co jest płatne i którego dnia (reguła R3). */
export function FormularzSkladnika({
  otwarty,
  onZamknij,
  okresId,
}: {
  otwarty: boolean
  onZamknij: () => void
  okresId: number
}) {
  const dodaj = useDodajSkladnik()
  const [nazwa, setNazwa] = useState('')
  const [klucz, setKlucz] = useState('czynsz_podstawowy')
  const [dzien, setDzien] = useState('')
  const [waloryzowany, setWaloryzowany] = useState(false)
  const [sposob, setSposob] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={onZamknij}
      tytul="Nowy składnik opłaty"
      opis="Ta pozycja mówi, CO i KIEDY jest płatne. ILE — mówi powiązany warunek umowy."
      onZapisz={() =>
        dodaj.mutateAsync({
          okresId,
          dane: {
            nazwa: nazwa.trim(),
            klucz_parametru: klucz.trim(),
            dzien_platnosci_miesiaca: liczbaLubNull(dzien),
            czy_waloryzowany: waloryzowany,
            sposob_wyliczenia: pustyNaNull(sposob),
          },
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleTekstowe
        nazwa="nazwa"
        etykieta="Nazwa"
        wartosc={nazwa}
        onZmiana={setNazwa}
        wymagane
        podpowiedz="Na przykład: Czynsz podstawowy, Opłata eksploatacyjna, Media."
      />
      <PoleWyboru
        nazwa="klucz"
        etykieta="Kwotę bierze z warunku"
        wartosc={klucz}
        onZmiana={setKlucz}
        wymagane
        pusteEtykieta=""
        opcje={[
          { wartosc: 'czynsz_podstawowy', etykieta: 'Czynsz podstawowy' },
          { wartosc: 'oplata_eksploatacyjna', etykieta: 'Opłata eksploatacyjna' },
        ]}
      />
      <PoleTekstowe
        nazwa="dzien"
        etykieta="Płatne do którego dnia miesiąca"
        typ="number"
        min="1"
        max="31"
        wartosc={dzien}
        onZmiana={setDzien}
        podpowiedz="System sam pokaże faktyczny dzień roboczy, gdy termin wypadnie w weekend albo święto."
      />
      <PoleZaznaczenia
        nazwa="waloryzowany"
        etykieta="Podlega waloryzacji"
        wartosc={waloryzowany}
        onZmiana={setWaloryzowany}
      />
      <PoleTekstowe
        nazwa="sposob"
        etykieta="Sposób wyliczenia"
        wartosc={sposob}
        onZmiana={setSposob}
        podpowiedz="Gdy kwoty nie da się podać wprost, na przykład: wg zużycia licznikowego."
      />
    </DialogFormularza>
  )
}

/** Kaucja, weksel, gwarancja albo polisa (reguły R4, R5, R6). */
export function FormularzZabezpieczenia({
  otwarty,
  onZamknij,
  okresId,
}: {
  otwarty: boolean
  onZamknij: () => void
  okresId: number
}) {
  const dodaj = useDodajZabezpieczenie()
  const [rodzaj, setRodzaj] = useState('')
  const [wartosc, setWartosc] = useState('')
  const [rodzajKwoty, setRodzajKwoty] = useState('brutto')
  const [sposob, setSposob] = useState('')
  const [wymagalnosc, setWymagalnosc] = useState('')
  const [waznosc, setWaznosc] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={onZamknij}
      tytul="Nowe zabezpieczenie"
      onZapisz={() =>
        dodaj.mutateAsync({
          okresId,
          dane: {
            rodzaj,
            status: 'wymagane',
            wymagana_wartosc: liczbaLubNull(wartosc),
            wymagana_waluta: wartosc.trim() ? 'PLN' : null,
            wymagana_rodzaj_kwoty: wartosc.trim() ? rodzajKwoty : null,
            wymagana_stawka_vat: wartosc.trim() && rodzajKwoty === 'netto' ? 23 : null,
            sposob_wyliczenia: pustyNaNull(sposob),
            data_wymagalnosci: pustyNaNull(wymagalnosc),
            data_waznosci: pustyNaNull(waznosc),
          },
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleWyboru
        nazwa="rodzaj"
        etykieta="Rodzaj"
        wartosc={rodzaj}
        onZmiana={setRodzaj}
        wymagane
        opcje={[
          { wartosc: 'kaucja', etykieta: 'Kaucja' },
          { wartosc: 'weksel', etykieta: 'Weksel' },
          { wartosc: 'gwarancja_bankowa', etykieta: 'Gwarancja bankowa' },
          { wartosc: 'polisa', etykieta: 'Polisa' },
        ]}
      />
      <PoleTekstowe
        nazwa="wartosc"
        etykieta="Wymagana wartość"
        typ="number"
        step="0.01"
        min="0"
        wartosc={wartosc}
        onZmiana={setWartosc}
      />
      {wartosc.trim() !== '' && (
        <PoleWyboru
          nazwa="rodzaj_kwoty"
          etykieta="Netto czy brutto"
          wartosc={rodzajKwoty}
          onZmiana={setRodzajKwoty}
          wymagane
          pusteEtykieta=""
          opcje={[
            { wartosc: 'brutto', etykieta: 'brutto' },
            { wartosc: 'netto', etykieta: 'netto' },
          ]}
        />
      )}
      <PoleTekstowe
        nazwa="sposob"
        etykieta="Sposób wyliczenia"
        wartosc={sposob}
        onZmiana={setSposob}
        podpowiedz="Na przykład: czterokrotność czynszu. Po waloryzacji trzeba to przeliczyć."
      />
      <PoleTekstowe
        nazwa="wymagalnosc"
        etykieta="Termin dostarczenia"
        typ="date"
        wartosc={wymagalnosc}
        onZmiana={setWymagalnosc}
      />
      {rodzaj === 'polisa' && (
        <PoleTekstowe
          nazwa="waznosc"
          etykieta="Polisa ważna do"
          typ="date"
          wartosc={waznosc}
          onZmiana={setWaznosc}
          podpowiedz="System przypomni 30 dni przed wygaśnięciem."
        />
      )}
    </DialogFormularza>
  )
}

/** Obowiązek przeglądu okresowego (reguła R7). */
export function FormularzPrzegladu({
  otwarty,
  onZamknij,
  lokalId,
}: {
  otwarty: boolean
  onZamknij: () => void
  lokalId: number
}) {
  const dodaj = useDodajPrzeglad()
  const [element, setElement] = useState('')
  const [ktoObciazany, setKtoObciazany] = useState('najemca')
  const [czestotliwosc, setCzestotliwosc] = useState('12')
  const [ostatni, setOstatni] = useState('')

  return (
    <DialogFormularza
      otwarty={otwarty}
      onZamknij={onZamknij}
      tytul="Nowy obowiązek przeglądu"
      opis="Każdy element osobno — dopiero wtedy da się zapytać o wszystkie gaśnice w budynku."
      onZapisz={() =>
        dodaj.mutateAsync({
          lokal_id: lokalId,
          element: element.trim(),
          kto_obciazany: ktoObciazany,
          czestotliwosc_miesiace: liczbaLubNull(czestotliwosc),
          ostatni_przeglad_data: pustyNaNull(ostatni),
        })
      }
      zapisywanie={dodaj.isPending}
    >
      <PoleTekstowe
        nazwa="element"
        etykieta="Element"
        wartosc={element}
        onZmiana={setElement}
        wymagane
        podpowiedz="Na przykład: gaśnice, brama, hydranty, instalacja elektryczna."
      />
      <PoleWyboru
        nazwa="kto"
        etykieta="Kogo obciąża"
        wartosc={ktoObciazany}
        onZmiana={setKtoObciazany}
        wymagane
        pusteEtykieta=""
        opcje={[
          { wartosc: 'najemca', etykieta: 'najemcę' },
          { wartosc: 'wynajmujacy', etykieta: 'wynajmującego' },
        ]}
      />
      <PoleTekstowe
        nazwa="czestotliwosc"
        etykieta="Co ile miesięcy"
        typ="number"
        min="1"
        wartosc={czestotliwosc}
        onZmiana={setCzestotliwosc}
      />
      <PoleTekstowe
        nazwa="ostatni"
        etykieta="Data ostatniego przeglądu"
        typ="date"
        wartosc={ostatni}
        onZmiana={setOstatni}
        podpowiedz="Bez niej termin kolejnego pozostanie nieustalony — a to nie to samo, co aktualny."
      />
    </DialogFormularza>
  )
}
