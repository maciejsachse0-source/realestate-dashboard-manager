import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { useProfil } from '@/api/zapytania'
import Uklad from '@/komponenty/Uklad'
import Dashboard from '@/strony/Dashboard/Dashboard'
import Import from '@/strony/Import/Import'
import Kartoteka from '@/strony/Kartoteka/Kartoteka'
import KokpitTerminow from '@/strony/KokpitTerminow/KokpitTerminow'
import Logowanie from '@/strony/Logowanie/Logowanie'
import ProfilLokalu from '@/strony/ProfilLokalu/ProfilLokalu'
import Waloryzacja from '@/strony/Waloryzacja/Waloryzacja'
import './index.css'

const klientZapytan = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (proby, blad) => {
        // Brak sesji i brak uprawnien to nie sa bledy przejsciowe.
        const status = (blad as { status?: number }).status
        if (status === 401 || status === 403) return false
        return proby < 2
      },
      refetchOnWindowFocus: false,
    },
  },
})

function Aplikacja() {
  const profil = useProfil()

  if (profil.isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        Wczytywanie…
      </div>
    )
  }

  if (profil.isError || !profil.data) {
    return <Logowanie />
  }

  return (
    <Routes>
      <Route element={<Uklad />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/terminy" element={<KokpitTerminow />} />
        <Route path="/kartoteka" element={<Kartoteka />} />
        <Route path="/import" element={<Import />} />
        <Route path="/waloryzacja" element={<Waloryzacja />} />
        <Route path="/lokale/:lokalId" element={<ProfilLokalu />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={klientZapytan}>
      <BrowserRouter>
        <Aplikacja />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
