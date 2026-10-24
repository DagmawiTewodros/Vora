import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { currentUser } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { FeedbackProvider } from "./lib/feedback";
import { I18nProvider } from "./lib/i18n";
import "@fontsource/cormorant-garamond/latin-500.css";
import "@fontsource/cormorant-garamond/latin-600.css";
import "@fontsource/cormorant-garamond/latin-700.css";
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider initial={currentUser()?.preferred_language ?? "en"}>
          <FeedbackProvider>
            <App />
          </FeedbackProvider>
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
