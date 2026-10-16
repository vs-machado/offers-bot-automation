"use client";

import { useCallback, useEffect, useEffectEvent, useMemo, useState } from "react";

import { getSourceGroups } from "@/features/source-groups/api/source-groups-client";
import { getTelegramPostId } from "@/features/source-groups/lib/telegram";
import type { SourceGroup } from "@/features/source-groups/types";
import { getRequestErrorMessage } from "@/lib/api-error-message";

type UseSourceGroupPreviewsInput = {
  enabled: boolean;
  catalog?: { url: string; label: string }[];
  onCatalogLoad?: (sourceIds: string[]) => void;
};

/** Cache real previews and progressively mount embeds while this view is enabled. */
export function useSourceGroupPreviews({
  enabled,
  catalog,
  onCatalogLoad,
}: UseSourceGroupPreviewsInput) {
  const [loadedGroups, setSourceGroups] = useState<SourceGroup[]>([]);
  const [sourceGroupsLoaded, setSourceGroupsLoaded] = useState(false);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [mountedSourceGroupIds, setMountedSourceGroupIds] = useState<string[]>([]);
  const [readyTelegramPostIds, setReadyTelegramPostIds] = useState<string[]>([]);
  const sourceGroups = useMemo(
    () => catalog ? catalog.map((source) => ({
        id: source.url,
        label: source.label,
        messages: loadedGroups.find((group) => group.id === source.url)?.messages,
      })) : loadedGroups,
    [catalog, loadedGroups]
  );

  const activeSourceGroup = useMemo(
    () =>
      (activeSourceId
        ? sourceGroups.find((group) => group.id === activeSourceId)
        : undefined) ?? sourceGroups[0],
    [activeSourceId, sourceGroups]
  );
  const activeTelegramPostsReady = useMemo(() => {
    const postIds = (activeSourceGroup?.messages ?? [])
      .map((message) => getTelegramPostId(message.post_url))
      .filter((postId): postId is string => Boolean(postId));
    return postIds.every((postId) => readyTelegramPostIds.includes(postId));
  }, [activeSourceGroup, readyTelegramPostIds]);
  const sourceGroupsLoading = enabled && !sourceGroupsLoaded;
  const notifyCatalogLoaded = useEffectEvent((groups: SourceGroup[]) => {
    onCatalogLoad?.(groups.map((group) => group.id));
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const controller = new AbortController();

    async function loadSourceGroups() {
      try {
        const groups = await getSourceGroups(controller.signal);
        if (!controller.signal.aborted) {
          setSourceGroups(groups);
          notifyCatalogLoaded(groups);
          setError("");
          setActiveSourceId((current) => current ?? groups[0]?.id ?? null);
          setMountedSourceGroupIds((current) =>
            current.length > 0 || !groups[0] ? current : [groups[0].id]
          );
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(getRequestErrorMessage(cause, "Não foi possível carregar as mensagens dos grupos."));
        }
      } finally {
        if (!controller.signal.aborted) {
          setSourceGroupsLoaded(true);
        }
      }
    }

    void loadSourceGroups();
    return () => {
      controller.abort();
    };
  }, [enabled, retryCount]);

  useEffect(() => {
    if (
      !enabled ||
      !activeSourceGroup ||
      !activeTelegramPostsReady ||
      sourceGroups.every((group) => mountedSourceGroupIds.includes(group.id))
    ) {
      return;
    }

    const idleWindow = window as Window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    let idleId: number | undefined;
    const delayId = window.setTimeout(() => {
      const mountNextGroup = () => {
        setMountedSourceGroupIds((current) => {
          const nextGroup = sourceGroups.find((group) => !current.includes(group.id));
          return nextGroup ? [...current, nextGroup.id] : current;
        });
      };

      if (idleWindow.requestIdleCallback) {
        idleId = idleWindow.requestIdleCallback(mountNextGroup, { timeout: 2500 });
        return;
      }

      mountNextGroup();
    }, 700);

    return () => {
      window.clearTimeout(delayId);
      if (idleId !== undefined) {
        idleWindow.cancelIdleCallback?.(idleId);
      }
    };
  }, [
    activeSourceGroup,
    activeTelegramPostsReady,
    mountedSourceGroupIds,
    enabled,
    sourceGroups,
  ]);

  const markTelegramPostReady = useCallback((postId: string) => {
    setReadyTelegramPostIds((current) =>
      current.includes(postId) ? current : [...current, postId]
    );
  }, []);

  const selectSourceGroup = useCallback((groupId: string) => {
    setMountedSourceGroupIds((current) =>
      current.includes(groupId) ? current : [...current, groupId]
    );
    setActiveSourceId(groupId);
  }, []);

  return {
    activeSourceGroup,
    markTelegramPostReady,
    mountedSourceGroupIds,
    readyTelegramPostIds,
    selectSourceGroup,
    sourceGroups,
    sourceGroupsLoading,
    error,
    retry: () => {
      setSourceGroupsLoaded(false);
      setError("");
      setRetryCount((current) => current + 1);
    },
  };
}
