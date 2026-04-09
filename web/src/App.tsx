import { Routes, Route } from "react-router-dom";
import PromptPage from "./pages/PromptPage";
import IdePage from "./pages/IdePage";
import DatabasePage from "./pages/DatabasePage";
import ApiPage from "./pages/ApiPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<PromptPage />} />
      <Route path="/ide" element={<IdePage />} />
      <Route path="/database" element={<DatabasePage />} />
      <Route path="/api" element={<ApiPage />} />
    </Routes>
  );
}

export default App;
