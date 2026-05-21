import { useEffect, useState } from "react";
import { getAppConfig } from "../api";
import { errorMessage } from "../lib/errors";
import type { AppConfig } from "../types";

export function useAppConfig() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getAppConfig()
      .then((appConfig) => {
        if (active) {
          setConfig(appConfig);
        }
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load app config"));
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return { config, error };
}
