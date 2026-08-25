/**
 * Cienki klient HTTP. Od etapu E4 typy endpointow beda generowane z OpenAPI
 * (openapi-typescript), a nie przepisywane recznie.
 */

export class BladApi extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'BladApi'
    this.status = status
  }
}

export async function pobierz<T>(sciezka: string): Promise<T> {
  const odpowiedz = await fetch(`/api/v1${sciezka}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!odpowiedz.ok) {
    throw new BladApi(odpowiedz.status, `Zadanie ${sciezka} zwrocilo ${odpowiedz.status}`)
  }
  return (await odpowiedz.json()) as T
}

export interface Zdrowie {
  status: 'ok' | 'degradacja'
  srodowisko: string
  baza: { polaczona: boolean; wersja?: string | null; blad?: string | null }
}
