"use client";

import { useEffect, useRef, useState } from "react";

type UseTelegramPostEmbedInput = {
  onReady: (postId: string) => void;
  postId: string;
  scale: number;
};

export function useTelegramPostEmbed({
  onReady,
  postId,
  scale,
}: UseTelegramPostEmbedInput) {
  const [scaledHeight, setScaledHeight] = useState<number>();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    container.innerHTML = "";
    let ready = false;
    let readinessStarted = false;
    let pollTimer: number | undefined;
    let resizeObserver: ResizeObserver | undefined;
    const startedAt = Date.now();

    const markReady = () => {
      if (ready) {
        return;
      }
      ready = true;
      onReady(postId);
    };

    const startReadinessCheck = () => {
      if (readinessStarted) {
        return;
      }
      const iframe = container.querySelector("iframe");
      if (!iframe) {
        return;
      }

      const syncScaledHeight = () => {
        const height = Math.round(iframe.offsetHeight || iframe.getBoundingClientRect().height);
        if (height > 0) {
          setScaledHeight(Math.ceil(height * scale) + 2);
        }
        return height;
      };

      readinessStarted = true;
      resizeObserver =
        typeof ResizeObserver === "undefined"
          ? undefined
          : new ResizeObserver(syncScaledHeight);
      resizeObserver?.observe(iframe);

      let lastHeight = syncScaledHeight();
      let stableSince = Date.now();

      pollTimer = window.setInterval(() => {
        const height = syncScaledHeight();
        if (Math.abs(height - lastHeight) > 2) {
          lastHeight = height;
          stableSince = Date.now();
        }

        const oldEnough = Date.now() - startedAt > 3600;
        const stableEnough = Date.now() - stableSince > 700;
        if (height > 80 && oldEnough && stableEnough) {
          markReady();
        }
      }, 150);
    };

    const observer = new MutationObserver(() => {
      const iframe = container.querySelector("iframe");
      if (iframe) {
        iframe.addEventListener("load", startReadinessCheck, { once: true });
        startReadinessCheck();
      }
    });
    observer.observe(container, { childList: true, subtree: true });

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?24";
    script.dataset.telegramPost = postId;
    script.dataset.width = "100%";
    script.dataset.lang = "pt";
    script.dataset.dark = document.documentElement.classList.contains("dark") ? "1" : "0";
    container.appendChild(script);
    const fallbackTimer = window.setTimeout(markReady, 7000);

    return () => {
      window.clearTimeout(fallbackTimer);
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
      resizeObserver?.disconnect();
      observer.disconnect();
      container.innerHTML = "";
    };
  }, [onReady, postId, scale]);

  return { containerRef, scaledHeight };
}
