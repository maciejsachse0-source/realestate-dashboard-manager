import { describe, expect, it } from 'vitest'
import {
  BRAK_DANYCH,
  formatujDate,
  formatujKwote,
  formatujPowierzchnie,
  formatujProcent,
  formatujRoznice,
  opisTerminu,
} from './format'

describe('formatujKwote', () => {
  it('uzywa przecinka dziesietnego i spacji jako separatora tysiecy', () => {
    // Intl uzywa spacji nielamiacej, wiec porownujemy po normalizacji.
    expect(formatujKwote('1234.56').replace(/\u00a0|\u202f/g, ' ')).toBe('1 234,56 zł')
  })

  it('zawsze pokazuje dwa miejsca po przecinku', () => {
    expect(formatujKwote(1000).replace(/\u00a0|\u202f/g, ' ')).toBe('1 000,00 zł')
  })

  it('grupuje takze setki tysiecy', () => {
    expect(formatujKwote('987654.32').replace(/ | /g, ' ')).toBe('987 654,32 zł')
  })

  it('dla wartosci nieliczbowej zwraca znak braku, nie NaN', () => {
    expect(formatujKwote('brak')).toBe('—')
  })
})

describe('formatujPowierzchnie', () => {
  it('formatuje z jednostka', () => {
    expect(formatujPowierzchnie('128.5').replace(/\u00a0|\u202f/g, ' ')).toBe('128,50 m²')
  })
})

describe('formatujDate', () => {
  it('zamienia ISO na DD.MM.RRRR', () => {
    expect(formatujDate('2027-03-01')).toBe('01.03.2027')
  })

  it('nie cofa daty o dzien na przelomie miesiaca', () => {
    // Regresja na blad strefy czasowej: new Date('2027-03-01') to polnoc UTC,
    // czyli 28.02 wieczorem w niektorych strefach.
    expect(formatujDate('2027-03-01T00:00:00Z')).toBe('01.03.2027')
    expect(formatujDate('2026-01-01')).toBe('01.01.2026')
  })

  it('brak daty to znak braku, nie pusty string', () => {
    expect(formatujDate(null)).toBe('—')
    expect(formatujDate(undefined)).toBe('—')
  })
})

describe('formatujRoznice', () => {
  it('dodaje plus przy wzroscie', () => {
    expect(formatujRoznice('351.50').replace(/ | /g, ' ')).toBe('+351,50 zł')
  })

  it('przy deflacji zostawia sam minus, bez "+-"', () => {
    expect(formatujRoznice('-250.00').replace(/ | /g, ' ')).toBe('-250,00 zł')
  })

  it('zera nie oznacza plusem', () => {
    expect(formatujRoznice('0.00').replace(/ | /g, ' ')).toBe('0,00 zł')
  })
})

describe('formatujProcent', () => {
  it('uzywa przecinka dziesietnego', () => {
    expect(formatujProcent('3.7')).toBe('3,70%')
  })

  it('zachowuje znak ujemny', () => {
    expect(formatujProcent('-2.5')).toBe('-2,50%')
  })
})

describe('opisTerminu', () => {
  it('mowi, ile dni zostalo do terminu', () => {
    expect(opisTerminu(12)).toBe('za 12 dni')
    expect(opisTerminu(180)).toBe('za 180 dni')
  })

  it('dzis i jutro maja wlasne slowa', () => {
    // "za 0 dni" to nie jest zdanie, ktore ktos czyta bez zatrzymania.
    expect(opisTerminu(0)).toBe('dziś')
    expect(opisTerminu(1)).toBe('jutro')
  })

  it('po terminie mowi, o ile', () => {
    expect(opisTerminu(-8)).toBe('8 dni po terminie')
    expect(opisTerminu(-1)).toBe('wczoraj, po terminie')
  })

  it('brak liczby to brak danych, a nie zero', () => {
    // Decyzja D5: brak danych jest informacja. Zero znaczy "dzis"
    // i nie wolno mu udawac braku ani odwrotnie.
    expect(opisTerminu(null)).toBe(BRAK_DANYCH)
    expect(opisTerminu(undefined)).toBe(BRAK_DANYCH)
    expect(opisTerminu(0)).not.toBe(BRAK_DANYCH)
  })
})
