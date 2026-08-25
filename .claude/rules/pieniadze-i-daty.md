# Pieniądze, daty, formaty

Ta reguła ładuje się zawsze, bo to najczęstsze źródło błędów w tym projekcie.

- Kwoty: `Decimal`, kwantyzacja do dwóch miejsc, `ROUND_HALF_UP`.
  Nigdy `float`, także w testach i skryptach pomocniczych.
- Każda kwota ma jawnie: netto czy brutto, stawkę VAT i walutę.
  Kwota bez tych trzech informacji jest niekompletna i nie wolno jej zapisać.
- Daty biznesowe (`data_przekazania`, `obowiazuje_od`) to `date`.
  Znaczniki techniczne (`utworzono`) to `datetime` w UTC.
  Mieszanie tych dwóch daje błąd o jeden dzień na przełomie miesiąca.
- Nigdy `datetime.now()` wewnątrz reguły domenowej. Datę przekazuj argumentem,
  inaczej testu nie da się napisać deterministycznie.
- Format wyświetlania: `1 234,56 zł` — spacja jako separator tysięcy zawsze,
  także przy czterech cyfrach (CLDR dla `pl-PL` domyślnie tego nie robi,
  dlatego `useGrouping: 'always'` w `format.ts` jest konieczne).
- Daty wyświetlane `DD.MM.RRRR`. Parsuj ISO ręcznie, nie przez `new Date()`,
  bo `new Date('2027-03-01')` to północ UTC i potrafi cofnąć się o dzień.
- Terminy płatności przesuwane na następny dzień roboczy przez `domena/kalendarz.py`.
  Wielkanoc i święta ruchome liczone algorytmem, nie wpisywane na sztywno.
