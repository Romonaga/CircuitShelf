import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

function installStaleBundleRecovery() {
  const reloadKey = "circuitshelf-stale-bundle-reloaded";
  const recover = (reason: unknown) => {
    const text = String(reason instanceof Error ? reason.message : reason ?? "");
    const isStaleBundle =
      text.includes("Failed to fetch dynamically imported module") ||
      text.includes("error loading dynamically imported module") ||
      text.includes("Importing a module script failed") ||
      text.includes("disallowed MIME type");
    if (!isStaleBundle || sessionStorage.getItem(reloadKey) === "1") {
      return;
    }
    sessionStorage.setItem(reloadKey, "1");
    window.location.reload();
  };

  window.addEventListener("error", (event) => recover(event.error ?? event.message));
  window.addEventListener("unhandledrejection", (event) => recover(event.reason));
  window.addEventListener("load", () => sessionStorage.removeItem(reloadKey));
}

installStaleBundleRecovery();

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
