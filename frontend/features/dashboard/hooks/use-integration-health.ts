"use client";

import { useEffect, useState } from "react";
import { getIntegrationHealth, type IntegrationHealth } from "@/features/dashboard/api/integration-health-client";

export function useIntegrationHealth() {
  const [health, setHealth] = useState<IntegrationHealth | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let controller: AbortController | null = null;
    async function refresh() {
      if (document.hidden || controller) return;
      controller = new AbortController();
      const current = controller;
      try {
        const result = await getIntegrationHealth(current.signal);
        if (!current.signal.aborted) {
          setHealth(result);
          setHasError(false);
        }
      } catch {
        if (!current.signal.aborted) setHasError(true);
      } finally {
        controller = null;
      }
    }
    void refresh();
    const interval = setInterval(() => void refresh(), 60000);
    const onVisibilityChange = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", onVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", onVisibilityChange);
      controller?.abort();
    };
  }, []);

  return { health, hasError };
}
