"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getSourceGroups } from "@/features/setup/api/setup-client";
import { getTelegramPostId } from "@/features/setup/lib/telegram";
import type { SourceGroup } from "@/features/setup/types";
import type { ConfigSummary } from "@/shared/contracts/user-config";

type UseSourceGroupPreviewsInput = {
  configs: ConfigSummary[];
  open: boolean;
  screen: "destination" | "providers" | "sources";
};

function getSavedSourceChats(configs: ConfigSummary[]) {
  const sourceConfig = configs.find((config) => config.config_type === "source_chats");
  const sourceChats = sourceConfig?.config_data?.source_chats;
  return Array.isArray(sourceChats)
    ? sourceChats.filter((chat): chat is string => typeof chat === "string")
    : [];
}

export function useSourceGroupPreviews({
  configs,
  open,
  screen,
}: UseSourceGroupPreviewsInput) {
  const [sourceGroups, setSourceGroups] = useState<SourceGroup[]>([]);
  const [sourceGroupsLoaded, setSourceGroupsLoaded] = useState(false);
  const [selectedSourceChats, setSelectedSourceChats] = useState<string[]>(() =>
    getSavedSourceChats(configs)
  );
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [mountedSourceGroupIds, setMountedSourceGroupIds] = useState<string[]>([]);
  const [readyTelegramPostIds, setReadyTelegramPostIds] = useState<string[]>([]);

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
  const sourceGroupsLoading = open && !sourceGroupsLoaded && sourceGroups.length === 0;

  useEffect(() => {
    if (!open || sourceGroupsLoaded || sourceGroups.length > 0) {
      return;
    }

    let cancelled = false;

    async function loadSourceGroups() {
      try {
        const groups = await getSourceGroups();
        if (!cancelled) {
          setSourceGroups(groups);
          setSelectedSourceChats((current) => current.filter((chat) => groups.some((group) => group.id === chat)));
          setActiveSourceId((current) => current ?? groups[0]?.id ?? null);
          setMountedSourceGroupIds((current) =>
            current.length > 0 || !groups[0] ? current : [groups[0].id]
          );
        }
      } catch {
        if (!cancelled) {
          setSourceGroups([]);
        }
      } finally {
        if (!cancelled) {
          setSourceGroupsLoaded(true);
        }
      }
    }

    void loadSourceGroups();
    return () => {
      cancelled = true;
    };
  }, [open, sourceGroups.length, sourceGroupsLoaded]);

  useEffect(() => {
    if (
      !open ||
      screen !== "sources" ||
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
    open,
    screen,
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

  const toggleSourceChat = useCallback((chat: string) => {
    setSelectedSourceChats((current) =>
      current.includes(chat)
        ? current.filter((item) => item !== chat)
        : [...current, chat]
    );
  }, []);

  return {
    activeSourceGroup,
    markTelegramPostReady,
    mountedSourceGroupIds,
    readyTelegramPostIds,
    selectSourceGroup,
    selectedSourceChats,
    sourceGroups,
    sourceGroupsLoading,
    toggleSourceChat,
  };
}
