"use client";

import { useState } from "react";
import { repostDelivery } from "@/features/dashboard/api/delivery-history-client";

export function useManualPublication(onPosted: () => void) {
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState("");
  const [lastPostedChatId, setLastPostedChatId] = useState<string | null>(null);

  async function publish(deliveryId: string, chatId: string) {
    setIsPublishing(true);
    setError("");
    setLastPostedChatId(null);
    try {
      await repostDelivery(deliveryId, chatId);
      setLastPostedChatId(chatId);
      onPosted();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível publicar a oferta agora. Tente novamente.",
      );
    } finally {
      setIsPublishing(false);
    }
  }

  return { isPublishing, error, lastPostedChatId, publish };
}
