/**
 * Zakładka „Jak to działa" na ekranie dokumentów z dysku.
 *
 * Pisana dla osoby, która programu **używa**, nie dla tej, która go rozwija.
 * Opis mechanizmu (wzorce nazw, sygnatury plików, liczenie skrótu) żyje
 * w docstringach modułów i w `docs/` — tam się go szuka przy zmianie kodu.
 *
 * Trzy rzeczy, których brak najbardziej bolał w poprzednich wersjach i które
 * wyznaczają dzisiejszy układ:
 *
 * 1. **Kontekst przed trasą.** Sama trasa z podpisami „Katalog · Budynki ·
 *    Lokale" nie mówi, dokąd prowadzi. Najpierw dwa zdania, czym jest ten ekran
 *    i co musi być spełnione, żeby zadziałał, dopiero potem kroki.
 * 2. **Przy każdej stacji: gdzie to się klika.** „Budynki" bez „Kartoteka"
 *    zostawia człowieka z pytaniem, w którym miejscu programu ma to zrobić.
 * 3. **Skrajne przypadki osobno i wyraźnie.** Wcześniej były rozsiane po
 *    akapitach jako zdania podrzędne, więc nie dało się ich znaleźć wtedy,
 *    kiedy są potrzebne, czyli gdy coś nie wygląda tak, jak powinno.
 *
 * Rysowane liniami i kółkami CSS, bez biblioteki (CLAUDE.md, „czego nie robić").
 */

// --------------------------------------------------------------------- ikony

/** Wspólna ramka ikony. Kreska, nie wypełnienie — ikony mają być ciche. */
function Ikona({ children }: { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-full"
    >
      {children}
    </svg>
  );
}

const IkonaFolder = () => (
  <Ikona>
    <path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2.5h7A1.5 1.5 0 0 1 19 9v8.5A1.5 1.5 0 0 1 17.5 19h-13A1.5 1.5 0 0 1 3 17.5z" />
  </Ikona>
);

const IkonaBudynek = () => (
  <Ikona>
    <path d="M4 20.5V5.5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v15" />
    <path d="M14 10h5a1 1 0 0 1 1 1v9.5" />
    <path d="M2.5 20.5h19M7 8h4M7 12h4M7 16h4" />
  </Ikona>
);

const IkonaDrzwi = () => (
  <Ikona>
    <path d="M6 20.5V4.5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v16" />
    <path d="M4 20.5h16M14.5 12h.01" />
  </Ikona>
);

const IkonaOsoba = () => (
  <Ikona>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20.5c0-3.6 3.1-6 7-6s7 2.4 7 6" />
  </Ikona>
);

const IkonaPodpis = () => (
  <Ikona>
    <path d="M6 3.5h7l5 5V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 20z" />
    <path d="M13 3.5V9h5" />
    <path d="M9 16.5c1.5-3 2.5-3 3 0s1.5 2 3-1" />
  </Ikona>
);

const IkonaMetka = () => (
  <Ikona>
    <path d="M20.5 12.9 12.9 20.5a1.5 1.5 0 0 1-2.1 0L3.5 13.2V4.5a1 1 0 0 1 1-1h8.7l7.3 7.3a1.5 1.5 0 0 1 0 2.1z" />
    <circle cx="8" cy="8" r="1.3" />
  </Ikona>
);

const IkonaWarstwy = () => (
  <Ikona>
    <path d="M12 3.5 21 8l-9 4.5L3 8z" />
    <path d="M3 12.5 12 17l9-4.5M3 16.5 12 21l9-4.5" />
  </Ikona>
);

const IkonaWymiana = () => (
  <Ikona>
    <path d="M4 8.5h13l-3-3M20 15.5H7l3 3" />
  </Ikona>
);

const IkonaOgniwo = () => (
  <Ikona>
    <path d="M10 13.5a4 4 0 0 0 5.7.4l2.8-2.8a4 4 0 0 0-5.7-5.7l-1.6 1.6" />
    <path d="M14 10.5a4 4 0 0 0-5.7-.4l-2.8 2.8a4 4 0 0 0 5.7 5.7l1.6-1.6" />
  </Ikona>
);

const IkonaUwaga = () => (
  <Ikona>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5v5M12 16h.01" />
  </Ikona>
);

// ------------------------------------------------------------------ elementy

function Naglowek({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold tracking-tight">{children}</h2>;
}

interface Stacja {
  ikona: React.ReactNode;
  tytul: string;
  gdzie: string;
  opis: string;
}

/**
 * Trasa: kółka na wspólnej linii.
 *
 * Linia jest jednym elementem pod spodem, a kółka zasłaniają ją swoim tłem.
 * Rysowanie odcinków między punktami wymagałoby liczenia szerokości kolumn
 * i rozjeżdżało się przy zawijaniu.
 */
function Trasa({ stacje }: { stacje: Stacja[] }) {
  return (
    <div className="relative overflow-x-auto pb-1">
      <span
        aria-hidden="true"
        className="absolute top-7 right-[8%] left-[8%] hidden h-px bg-border sm:block"
      />
      <ol className="relative flex min-w-max gap-6 sm:min-w-0 sm:gap-2">
        {stacje.map((s, i) => (
          <li
            key={s.tytul}
            className="flex w-36 flex-none flex-col items-center gap-1.5 text-center sm:w-auto sm:flex-1"
          >
            <span className="relative flex size-14 items-center justify-center rounded-full border bg-background">
              <span className="size-6 text-foreground">{s.ikona}</span>
              <span className="absolute -right-1 -bottom-1 flex size-5 items-center justify-center rounded-full bg-foreground text-[0.65rem] font-semibold tabular-nums text-background">
                {i + 1}
              </span>
            </span>
            <span className="mt-1 text-sm leading-tight font-medium">
              {s.tytul}
            </span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[0.68rem] leading-tight text-muted-foreground">
              {s.gdzie}
            </span>
            <span className="text-xs leading-tight text-muted-foreground">
              {s.opis}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/**
 * Krok opisany od strony tego, kto go wykonuje.
 *
 * Podział „ty / program" jest najważniejszą informacją na tej stronie. Bez
 * niego połowa czynności wygląda na ręczne, choć dzieje się sama — i odwrotnie:
 * łatwo czekać na to, czego program nigdy nie zrobi.
 */
function Krok({
  kto,
  children,
}: {
  kto: "ty" | "program";
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-2.5 py-1.5">
      <span
        className={`mt-px h-5 shrink-0 rounded px-1.5 text-[0.7rem] leading-5 font-medium ${
          kto === "ty"
            ? "bg-foreground text-background"
            : "bg-muted text-muted-foreground"
        }`}
      >
        {kto === "ty" ? "Ty" : "Program"}
      </span>
      <span className="min-w-0">{children}</span>
    </li>
  );
}

function Scenariusz({
  ikona,
  tytul,
  children,
}: {
  ikona: React.ReactNode;
  tytul: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-l pl-4">
      <div className="flex items-center gap-2">
        <span className="size-4 shrink-0 text-muted-foreground">{ikona}</span>
        <p className="font-medium">{tytul}</p>
      </div>
      <ol className="mt-1.5 divide-y">{children}</ol>
    </div>
  );
}

/** Sytuacja odbiegająca od normalnej i to, co się wtedy dzieje. */
function CoJesli({
  sytuacja,
  children,
}: {
  sytuacja: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-x-6 gap-y-1 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <p className="flex gap-2 font-medium">
        <span className="mt-0.5 size-4 shrink-0 text-muted-foreground">
          <IkonaUwaga />
        </span>
        <span>{sytuacja}</span>
      </p>
      <p className="text-muted-foreground sm:pt-0">{children}</p>
    </div>
  );
}

const TRASA_STARTU: Stacja[] = [
  {
    ikona: <IkonaFolder />,
    tytul: "Katalog",
    gdzie: "ten ekran",
    opis: "wskaż, gdzie na dysku leżą umowy",
  },
  {
    ikona: <IkonaBudynek />,
    tytul: "Budynki",
    gdzie: "Kartoteka",
    opis: "wskaż folder, jeśli nazwany inaczej",
  },
  {
    ikona: <IkonaDrzwi />,
    tytul: "Lokale",
    gdzie: "Kartoteka",
    opis: "oznaczenie i typ z ewidencji",
  },
  {
    ikona: <IkonaOsoba />,
    tytul: "Najemcy",
    gdzie: "Kartoteka",
    opis: "dane firmy, raz na najemcę",
  },
  {
    ikona: <IkonaPodpis />,
    tytul: "Umowa",
    gdzie: "profil lokalu",
    opis: "daty, okres, czynsz",
  },
  {
    ikona: <IkonaMetka />,
    tytul: "Dokumenty",
    gdzie: "ten ekran",
    opis: "sparuj folder i dodaj pliki",
  },
];

// -------------------------------------------------------------------- ekran

export default function JakToDziala() {
  return (
    <div className="space-y-10 text-sm leading-relaxed">
      {/* Kontekst przed instrukcją: czym to jest i czego wymaga. */}
      <section className="grid gap-x-10 gap-y-6 border-b pb-6 lg:grid-cols-2">
        <div className="space-y-2">
          <Naglowek>Co robi ten ekran</Naglowek>
          <p className="text-muted-foreground">
            Zagląda do folderów z umowami na twoim dysku i pokazuje, które pliki
            są już w programie, a których jeszcze nie ma. Plik, który dodasz,{" "}
            <strong className="text-foreground">zostaje na swoim miejscu</strong>{" "}
            — program zapisuje tylko odnośnik do niego.
          </p>
          <p className="text-muted-foreground">
            <strong className="text-foreground">
              Treści dokumentów program nie czyta.
            </strong>{" "}
            Rozpoznaje rodzaj po nazwie pliku i pamięta, który plik już widział.
            Daty, kwoty i terminy z wnętrza umowy wpisujesz sam.
          </p>
        </div>

        <div className="space-y-2">
          <Naglowek>Czego wymaga, żeby zadziałał</Naglowek>
          <ul className="space-y-2">
            <li className="flex gap-2.5">
              <span className="mt-px size-5 shrink-0 rounded bg-muted text-center text-[0.7rem] leading-5 font-semibold">
                1
              </span>
              <span>
                <strong>Foldery ułożone w trzech poziomach:</strong>{" "}
                <span className="text-muted-foreground">
                  budynek → „Umowy najmu" → folder lokalu → pliki.
                </span>
              </span>
            </li>
            <li className="flex gap-2.5">
              <span className="mt-px size-5 shrink-0 rounded bg-muted text-center text-[0.7rem] leading-5 font-semibold">
                2
              </span>
              <span>
                <strong>Budynki i lokale wpisane w Kartotece.</strong>{" "}
                <span className="text-muted-foreground">
                  Bez nich nie ma do czego przypiąć dokumentu. Nazwy nie musisz
                  dopasowywać do dysku — jeśli katalog nazywa się inaczej, wpisz
                  go w polu <strong>Folder na dysku</strong> przy budynku.
                </span>
              </span>
            </li>
            <li className="flex gap-2.5">
              <span className="mt-px size-5 shrink-0 rounded bg-muted text-center text-[0.7rem] leading-5 font-semibold">
                3
              </span>
              <span>
                <strong>Założona umowa dla lokalu.</strong>{" "}
                <span className="text-muted-foreground">
                  Dokument należy do umowy, nie do samego lokalu.
                </span>
              </span>
            </li>
          </ul>
        </div>
      </section>

      {/*
        Decyzja D3 z koncepcji, postawiona wprost, bo bez niej instrukcja
        wygląda tak, jakby wszystko miało zostać ręczne na zawsze — albo
        odwrotnie, jakby program kiedyś sam wyciągnął z umowy NIP najemcy.
        Ani jedno, ani drugie nie jest prawdą i oba wnioski są kosztowne.
      */}
      <section className="space-y-4">
        <div className="space-y-1">
          <Naglowek>Dwa tory danych</Naglowek>
          <p className="max-w-3xl text-muted-foreground">
            Dziś wszystko wpisujesz sam, bo czytania dokumentów jeszcze nie ma.
            Różnica dotyczy tego, co się zmieni: jedne pola program kiedyś
            zaproponuje z treści umowy, a drugich{" "}
            <strong className="text-foreground">nie tknie nigdy</strong>.
          </p>
        </div>

        <div className="grid gap-x-10 gap-y-6 lg:grid-cols-2">
          <div className="space-y-2 border-l-2 border-foreground pl-4">
            <p className="font-medium">
              Warunki umowy — kiedyś podpowie je z dokumentu
            </p>
            <p className="text-muted-foreground">
              Powierzchnia, stawka za m², czynsz i składniki opłat, terminy
              płatności, daty zawarcia i przekazania, okres najmu, zasady
              waloryzacji, kaucja, wymagana polisa, zakres przeglądów.
            </p>
            <p className="text-muted-foreground">
              To są liczby i terminy, które w umowie stoją czarno na białym.
              Program będzie je <strong>proponował</strong>, a ty zatwierdzał —
              nigdy nie zapisze wartości, której nie widziałeś.
            </p>
          </div>

          <div className="space-y-2 border-l-2 border-border pl-4">
            <p className="font-medium">Dane najemcy — zawsze tylko z ręki</p>
            <p className="text-muted-foreground">
              Nazwa firmy, NIP, REGON, KRS, adres siedziby i do korespondencji,
              e-mail, telefon, osoby kontaktowe, numery rachunków.
            </p>
            <p className="text-muted-foreground">
              Te pola są celowo poza torem automatycznym. Dokumenty, które
              kiedyś pójdą do czytania, mają być pozbawione danych
              identyfikujących klienta — dlatego wpisuje się je bezpośrednio
              w programie, w zakładce <strong>Najemca</strong>, i nigdzie
              indziej.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------- droga człowieka */}

      <section className="space-y-5">
        <div className="space-y-1">
          <Naglowek>Od czego zacząć</Naglowek>
          <p className="max-w-3xl text-muted-foreground">
            Trasa od pustego programu do wczytanych dokumentów. Sześć przystanków,
            robisz je <strong>raz na starcie</strong> — szara etykieta pod nazwą
            mówi, w którym miejscu programu to klikasz. Kolejność nie jest
            dowolna: każdy przystanek potrzebuje poprzedniego.
          </p>
        </div>

        <Trasa stacje={TRASA_STARTU} />

        <div className="grid gap-x-10 gap-y-3 border-t pt-4 lg:grid-cols-2">
          <p className="text-muted-foreground">
            Na końcu trasy program zaczyna pracować sam: co rano przelicza
            terminy i pokazuje je w zakładce <strong>Terminy</strong> z liczbą dni
            do końca. Dla jednego budynku cała trasa to kwadrans.
          </p>
          <p className="text-muted-foreground">
            Masz dane w Excelu? Ekran <strong>Import</strong> wczyta budynki,
            lokale, najemców i umowy za jednym razem — wtedy przystanki 2–5
            odpadają i zostaje pierwszy i ostatni.
          </p>
        </div>
      </section>

      {/* ------------------------------------------------ typowe sytuacje */}

      <section className="space-y-5">
        <div className="space-y-1">
          <Naglowek>Typowe sytuacje, krok po kroku</Naglowek>
          <p className="text-muted-foreground">
            Plakietka mówi, kto wykonuje dany krok. Część rzeczy dzieje się sama,
            a na drugą część program czeka.
          </p>
        </div>

        <div className="grid gap-x-10 gap-y-7 lg:grid-cols-2">
          <Scenariusz
            ikona={<IkonaPodpis />}
            tytul="Nowa umowa trafiła do folderu"
          >
            <Krok kto="ty">Załóż najemcę i umowę, jeśli jeszcze ich nie ma.</Krok>
            <Krok kto="ty">Naciśnij „Skanuj ponownie".</Krok>
            <Krok kto="program">
              Pokazuje nowy folder i pliki w nim jako <strong>nowe</strong>,
              z podpowiedzianym rodzajem.
            </Krok>
            <Krok kto="ty">
              Wybierz umowę przy folderze, „Powiąż". Raz — potem folder jest już
              rozpoznany.
            </Krok>
            <Krok kto="ty">
              Sprawdź rodzaj, wpisz datę z dokumentu, „Dodaj". Resztę odłóż
              przyciskiem „Pomiń".
            </Krok>
            <Krok kto="ty">
              Wpisz warunki w profilu lokalu: <strong>Finanse</strong>{" "}
              i <strong>Zabezpieczenia</strong>.
            </Krok>
          </Scenariusz>

          <Scenariusz
            ikona={<IkonaWarstwy />}
            tytul="Aneks do umowy, która już jest"
          >
            <Krok kto="ty">
              Wrzuć plik do tego samego folderu co umowa, „Skanuj ponownie".
            </Krok>
            <Krok kto="program">
              Podpowiada rodzaj „aneks" i wyciąga numer z nazwy. Folder jest
              sparowany, więc o nic nie pyta.
            </Krok>
            <Krok kto="ty">Wpisz datę aneksu i naciśnij „Dodaj".</Krok>
            <Krok kto="ty">
              W zakładce <strong>Finanse</strong> dodaj{" "}
              <strong>nową wartość</strong> z datą, od której obowiązuje. Nie
              poprawiaj starej — historia stawek ma zostać.
            </Krok>
            <Krok kto="program">
              Od tej daty pokazuje nową kwotę, poprzednią przenosi do{" "}
              <strong>Historii</strong>.
            </Krok>
          </Scenariusz>

          <Scenariusz
            ikona={<IkonaBudynek />}
            tytul="Nowy budynek i jego lokale"
          >
            <Krok kto="ty">
              Kartoteka → „Dodaj budynek". Nazwa taka, jak folder na dysku.
            </Krok>
            <Krok kto="ty">
              Dodaj lokale. Budynek bez lokali też jest widoczny — nie zniknie.
            </Krok>
            <Krok kto="ty">
              Na dysku: folder budynku, w nim „Umowy najmu", a w środku folder na
              każdy lokal.
            </Krok>
            <Krok kto="program">
              Przy następnym skanie zestawia folder z kartoteką po nazwie.
            </Krok>
          </Scenariusz>

          <Scenariusz ikona={<IkonaWymiana />} tytul="Zmiana najemcy w lokalu">
            <Krok kto="ty">
              Zakończ starą umowę i wpisz faktyczną datę zakończenia.
            </Krok>
            <Krok kto="ty">
              Na dysku załóż <strong>nowy folder</strong>. Stary zostaw — jest
              powiązany ze starą umową.
            </Krok>
            <Krok kto="ty">Dodaj najemcę, załóż umowę, sparuj nowy folder.</Krok>
            <Krok kto="program">
              Pokazuje nowego najemcę, a poprzedni okres najmu zostaje w historii
              lokalu ze swoimi dokumentami.
            </Krok>
          </Scenariusz>
        </div>
      </section>

      {/* ------------------------------------------------ skrajne przypadki */}

      <section className="space-y-4">
        <div className="space-y-1">
          <Naglowek>Co, jeśli coś wygląda inaczej</Naglowek>
          <p className="max-w-3xl text-muted-foreground">
            Sytuacje, w których program zachowuje się nie tak, jak się można
            spodziewać — zwykle dlatego, że woli powiedzieć „nie wiem" niż
            zgadnąć.
          </p>
        </div>

        <div className="divide-y border-y">
          <CoJesli sytuacja="Folder budynku nazywa się inaczej niż budynek w Kartotece">
            Program pokaże go z dopiskiem{" "}
            <strong className="text-foreground">
              „tego budynku nie ma w kartotece"
            </strong>{" "}
            i nie przypisze do niczego. Nie przemianowuj folderu — otwórz budynek
            w Kartotece i wpisz nazwę katalogu w polu{" "}
            <strong className="text-foreground">Folder na dysku</strong>.
          </CoJesli>

          <CoJesli sytuacja="Przy pliku nie ma podpowiedzianego rodzaju">
            Z nazwy nic nie wynika („skan0012.pdf") albo nazwa jest dwuznaczna
            („protokół zdawczo-odbiorczy" bywa i przy wydaniu lokalu, i przy
            zwrocie). Program{" "}
            <strong className="text-foreground">celowo nie zgaduje</strong> —
            wybierz rodzaj z listy.
          </CoJesli>

          <CoJesli sytuacja="W folderze leżą pliki, które nie są dokumentem umowy">
            Zdjęcia, notatki, korespondencja — użyj przycisku{" "}
            <strong className="text-foreground">„Pomiń"</strong>. Program
            zapamięta je po treści, więc nie wrócą na listę nawet po
            przemianowaniu. Pomyłkę cofa „Przywróć".
          </CoJesli>

          <CoJesli sytuacja="Ten sam dokument leży w dwóch miejscach">
            Zostanie rozpoznany jako{" "}
            <strong className="text-foreground">w systemie</strong>, choćby miał
            inną nazwę i leżał w innym folderze. Ten sam plik nie wejdzie do
            programu dwa razy.
          </CoJesli>

          <CoJesli sytuacja="Przeniosłeś albo przemianowałeś plik po dodaniu">
            Odnośnik jest zerwany i dokumentu nie da się otworzyć. Naciśnij{" "}
            <strong className="text-foreground">„Sprawdź odnośniki"</strong> —
            wypisze wszystkie takie pliki. Przywróć je pod starą ścieżkę albo
            dodaj jeszcze raz.
          </CoJesli>

          <CoJesli sytuacja="Skan pominął jakiś katalog">
            Nad listą pojawi się liczba pominiętych pozycji. Zwykle to katalog
            bez uprawnień, odłączony dysk sieciowy albo zbyt długa ścieżka.
            Jeden taki katalog{" "}
            <strong className="text-foreground">nie przerywa całego skanu</strong>
            .
          </CoJesli>

          <CoJesli sytuacja="Folder dotyczy najemcy, który już się wyprowadził">
            Lista wyboru przy parowaniu pokazuje dziś{" "}
            <strong className="text-foreground">tylko aktualne umowy</strong>.
            Archiwalnego folderu nie da się na razie sparować z zakończoną umową —
            to znane ograniczenie, nie usterka.
          </CoJesli>
        </div>
      </section>

      {/* ------------------------------------------------- statusy i rytm */}

      <section className="grid gap-x-10 gap-y-8 border-t pt-6 lg:grid-cols-2">
        <div className="space-y-3">
          <Naglowek>Statusy przy plikach</Naglowek>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium">nowy</dt>
              <dd className="text-muted-foreground">
                Program go nie zna. Czeka na twoją decyzję.
              </dd>
            </div>
            <div>
              <dt className="font-medium">w systemie</dt>
              <dd className="text-muted-foreground">
                Ten dokument już jest. Zamiast formularza jest „Otwórz".
              </dd>
            </div>
            <div>
              <dt className="font-medium">pominięty</dt>
              <dd className="text-muted-foreground">
                Świadomie odłożony i nie wraca na listę. Cofa się przyciskiem
                „Przywróć".
              </dd>
            </div>
          </dl>
        </div>

        <div className="space-y-3">
          <Naglowek>Rytm pracy</Naglowek>
          <div className="space-y-2">
            <p>
              <span className="font-medium">Codziennie.</span>{" "}
              <span className="text-muted-foreground">
                Zakładka <strong>Terminy</strong>. Licznik mówi, ile dni zostało;
                czerwony znaczy, że termin minął.
              </span>
            </p>
            <p>
              <span className="font-medium">Po każdej nowej umowie.</span>{" "}
              <span className="text-muted-foreground">
                „Skanuj ponownie" na tym ekranie.
              </span>
            </p>
            <p>
              <span className="font-medium">Co jakiś czas.</span>{" "}
              <span className="text-muted-foreground">
                „Sprawdź odnośniki", żeby wychwycić zerwane pliki, zanim okażą się
                potrzebne.
              </span>
            </p>
          </div>
        </div>
      </section>

      {/* Jedyne wyróżnienie na stronie, bo jedyna rzecz wymagająca działania. */}
      <section className="space-y-2 border-l-2 border-foreground pl-5">
        <div className="flex items-center gap-2">
          <span className="size-5 shrink-0">
            <IkonaOgniwo />
          </span>
          <h2 className="text-base font-semibold">
            Jedna rzecz, którą trzeba wiedzieć
          </h2>
        </div>
        <p className="max-w-4xl text-muted-foreground">
          Dokumenty są{" "}
          <strong className="text-foreground">linkowane, nie kopiowane</strong> —
          plik zostaje tam, gdzie leży. Dzięki temu nie ma dwóch wersji tej samej
          umowy, ale przeniesienie pliku zrywa odnośnik. Dlatego{" "}
          <strong className="text-foreground">
            kopia zapasowa musi obejmować bazę razem z katalogiem dokumentów
          </strong>
          . Sama baza to ścieżki do plików, których w niej nie ma.
        </p>
      </section>
    </div>
  );
}
