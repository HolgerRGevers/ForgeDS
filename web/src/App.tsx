import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthGuard } from "./components/AuthGuard";
import { useBridgeStore } from "./stores/bridgeStore";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import IdeaPage from "./pages/IdeaPage";
import DepthPickerPage from "./pages/DepthPickerPage";
import QuestionPage from "./pages/QuestionPage";
import BuildingPage from "./pages/BuildingPage";
import IdePage from "./pages/IdePage";
import DatabasePage from "./pages/DatabasePage";
import ApiPage from "./pages/ApiPage";
import PrivacyPage from "./pages/PrivacyPage";
import { ToastContainer } from "./components/ToastContainer";

function App() {
  const connect = useBridgeStore((s) => s.connect);

  // Connect to bridge only if available (optional — not required for GitHub features)
  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route
          path="/*"
          element={
            <AuthGuard>
              <AppShell>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/new/idea" element={<IdeaPage />} />
                  <Route path="/new/depth" element={<DepthPickerPage />} />
                  <Route path="/new/q/:n" element={<QuestionPage />} />
                  <Route path="/new/building" element={<BuildingPage />} />
                  <Route path="/ide" element={<IdePage />} />
                  <Route path="/database" element={<DatabasePage />} />
                  <Route path="/api" element={<ApiPage />} />
                </Routes>
              </AppShell>
            </AuthGuard>
          }
        />
      </Routes>
    </>
  );
}

export default App;
