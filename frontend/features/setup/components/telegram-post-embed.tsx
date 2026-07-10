"use client";

import { useTelegramPostEmbed } from "@/features/setup/hooks/use-telegram-post-embed";

const telegramEmbedScale = 0.86;

type TelegramPostEmbedProps = {
  onReady: (postId: string) => void;
  postId: string;
};

export function TelegramPostEmbed({ onReady, postId }: TelegramPostEmbedProps) {
  const { containerRef, scaledHeight } = useTelegramPostEmbed({
    onReady,
    postId,
    scale: telegramEmbedScale,
  });

  return (
    <div
      className="overflow-hidden"
      style={scaledHeight ? { height: scaledHeight } : undefined}
    >
      <div
        className="origin-top-left [&_.telegram-post]:mx-0 [&_.telegram-post]:my-0 [&_iframe]:mx-0 [&_iframe]:my-0"
        ref={containerRef}
        style={{
          transform: `scale(${telegramEmbedScale})`,
          width: `${100 / telegramEmbedScale}%`,
        }}
      />
    </div>
  );
}
