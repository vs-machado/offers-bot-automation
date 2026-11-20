"use client";

import { useState } from "react";
import { repostDelivery } from "@/features/dashboard/api/delivery-history-client";

export function useManualPublication(onPosted: () => void) {
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState("");
  const [queuedId, setQueuedId] = useState<string | null>(null);

  async function publish(deliveryId: string, chatId: string) {
    setIsPublishing(true);
    setError("");
    setQueuedId(null);
    try {
      const { id } = await repostDelivery(deliveryId, chatId);
      setQueuedId(id);
      onPosted();
      return true;
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível publicar a oferta agora. Tente novamente.",
      );
      return false;
    } finally {
      setIsPublishing(false);
    }
  }

  return { isPublishing, error, queuedId, publish };
}
