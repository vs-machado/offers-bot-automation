"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getDeliveryHistory } from "@/features/dashboard/api/delivery-history-client";
import type { DeliveryHistoryData, DeliveryStatus } from "@/features/dashboard/types";

export function useDeliveryHistory(initialData: DeliveryHistoryData | null) {
  const [data, setData] = useState(initialData);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<DeliveryStatus | "">("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(initialData ? "" : "Não foi possível carregar o histórico. Clique em Atualizar para tentar novamente.");
  const activeRequest = useRef<AbortController | null>(null);

  const loadHistory = useCallback(async (nextPage: number, nextStatus: DeliveryStatus | "") => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setIsLoading(true);
    try {
      const result = await getDeliveryHistory(nextPage, nextStatus, controller.signal);
      if (controller.signal.aborted) return;
      setData(result);
      setPage(nextPage);
      setStatus(nextStatus);
      setError("");
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause instanceof TypeError ? "Não foi possível conectar ao servidor. Confira sua conexão." : cause instanceof Error ? cause.message : "Não foi possível atualizar o histórico.");
      }
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (!document.hidden) void loadHistory(page, status);
    }, 30000);
    return () => {
      clearInterval(interval);
      activeRequest.current?.abort();
    };
  }, [loadHistory, page, status]);

  return { data, page, status, isLoading, error, loadHistory };
}
