import { describe, expect, it } from 'vitest'
import { formatujDate, formatujKwote, formatujPowierzchnie } from './format'

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
