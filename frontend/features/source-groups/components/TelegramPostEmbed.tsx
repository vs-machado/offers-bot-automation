"use client";

import { useTelegramPostEmbed } from "@/features/source-groups/hooks/use-telegram-post-embed";

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
        className="origin-top-left [&_.telegram-post]:m-0 [&_iframe]:m-0"
        ref={containerRef}
        style={{
          transform: `scale(${telegramEmbedScale})`,
          width: `${100 / telegramEmbedScale}%`,
        }}
      />
    </div>
  );
}
