import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthGuard } from "./components/AuthGuard";
import { useBridgeStore } from "./stores/bridgeStore";
import LoginPage from "./pages/LoginPage";
import PromptPage from "./pages/PromptPage";
import IdePage from "./pages/IdePage";
import DatabasePage from "./pages/DatabasePage";
import ApiPage from "./pages/ApiPage";

function App() {
  const connect = useBridgeStore((s) => s.connect);
  const status = useBridgeStore((s) => s.status);

  // Connect to bridge only if available (optional — not required for GitHub features)
  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppShell bridgeStatus={status}>
              <Routes>
                <Route path="/" element={<PromptPage />} />
                <Route path="/ide" element={<IdePage />} />
                <Route path="/database" element={<DatabasePage />} />
                <Route path="/api" element={<ApiPage />} />
              </Routes>
            </AppShell>
          </AuthGuard>
        }
      />
    </Routes>
  );
}

export default App;
