import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { useBridgeStore } from "./stores/bridgeStore";
import PromptPage from "./pages/PromptPage";
import IdePage from "./pages/IdePage";
import DatabasePage from "./pages/DatabasePage";
import ApiPage from "./pages/ApiPage";

function App() {
  const connect = useBridgeStore((s) => s.connect);

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<PromptPage />} />
        <Route path="/ide" element={<IdePage />} />
        <Route path="/database" element={<DatabasePage />} />
        <Route path="/api" element={<ApiPage />} />
      </Routes>
    </AppShell>
  );
}

export default App;
