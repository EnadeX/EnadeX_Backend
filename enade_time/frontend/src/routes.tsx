import { Navigate, Route, Routes } from "react-router-dom";

import Home from "./pages/Home";
import Sobre from "./pages/Sobre";
import NotFound from "./pages/NotFound";

import EnadeLayout from "./pages/enade/EnadeLayout";
import EnadeAnual from "./pages/enade/Anual";
import EnadeRegional from "./pages/enade/Regional";
import EnadePorUF from "./pages/enade/PorUF";
import EnadePorIES from "./pages/enade/PorIES";
import EnadeRegistros from "./pages/enade/Registros";
import EnadeComparar from "./pages/enade/Comparar";

import SpdLayout from "./pages/spd/SpdLayout";
import SpdExecucoes from "./pages/spd/Execucoes";
import SpdComparativo from "./pages/spd/Comparativo";
import SpdMetricas from "./pages/spd/Metricas";
import SpdEtapaDetalhe from "./pages/spd/EtapaDetalhe";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />

      <Route path="/enade" element={<EnadeLayout />}>
        <Route index element={<Navigate to="anual" replace />} />
        <Route path="anual" element={<EnadeAnual />} />
        <Route path="regional" element={<EnadeRegional />} />
        <Route path="uf" element={<EnadePorUF />} />
        <Route path="ies" element={<EnadePorIES />} />
        <Route path="comparar" element={<EnadeComparar />} />
        <Route path="registros" element={<EnadeRegistros />} />
      </Route>

      <Route path="/spd" element={<SpdLayout />}>
        <Route index element={<Navigate to="comparativo" replace />} />
        <Route path="execucoes" element={<SpdExecucoes />} />
        <Route path="comparativo" element={<SpdComparativo />} />
        <Route path="metricas" element={<SpdMetricas />} />
        <Route path="etapas/:execucaoId" element={<SpdEtapaDetalhe />} />
      </Route>

      <Route path="/sobre" element={<Sobre />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
