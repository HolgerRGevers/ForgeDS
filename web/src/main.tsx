import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import "dockview-react/dist/styles/dockview.css";
import "./styles/dockview-theme.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename="/ForgeDS">
      <App />
    </BrowserRouter>
  </StrictMode>,
);
