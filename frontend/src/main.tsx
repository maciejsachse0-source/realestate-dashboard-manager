import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Uklad from "@/komponenty/Uklad";
import Dashboard from "@/strony/Dashboard/Dashboard";
import Import from "@/strony/Import/Import";
import Kartoteka from "@/strony/Kartoteka/Kartoteka";
import KokpitTerminow from "@/strony/KokpitTerminow/KokpitTerminow";
import ProfilLokalu from "@/strony/ProfilLokalu/ProfilLokalu";
import Skan from "@/strony/Skan/Skan";
import Waloryzacja from "@/strony/Waloryzacja/Waloryzacja";
import "./index.css";

const klientZapytan = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (proby) => proby < 2,
      refetchOnWindowFocus: false,
    },
  },
});

function Aplikacja() {
  return (
    <Routes>
      <Route element={<Uklad />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/terminy" element={<KokpitTerminow />} />
        <Route path="/kartoteka" element={<Kartoteka />} />
        <Route path="/import" element={<Import />} />
        <Route path="/dokumenty-z-dysku" element={<Skan />} />
        <Route path="/waloryzacja" element={<Waloryzacja />} />
        <Route path="/lokale/:lokalId" element={<ProfilLokalu />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={klientZapytan}>
      <BrowserRouter>
        <Aplikacja />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
