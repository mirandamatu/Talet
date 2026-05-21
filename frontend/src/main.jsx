import React from "react"
import { createRoot } from "react-dom/client"
import App from "./App.jsx"
import CareerPage from "./CareerPage.jsx"
import { ToastProvider, ConfirmProvider } from "./shared/ui.jsx"
import "./styles.css"

// Detect public career page routes: /careers/:slug
const pathMatch = window.location.pathname.match(/^\/careers\/([^/]+)\/?$/)
const careerSlug = pathMatch ? pathMatch[1] : null

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {careerSlug ? (
      <CareerPage slug={careerSlug} />
    ) : (
      <ToastProvider>
        <ConfirmProvider>
          <App />
        </ConfirmProvider>
      </ToastProvider>
    )}
  </React.StrictMode>
)
