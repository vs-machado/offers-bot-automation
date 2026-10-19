import { cn } from "@/lib/utils";

export function PlatformLogo({ platform, className }: {
  platform: "telegram" | "whatsapp";
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={cn("size-5 shrink-0", className)}
      fill="none"
    >
      {platform === "whatsapp" ? (
        <>
          <circle cx="12" cy="12" r="12" fill="#25D366" />
          <path d="M6.2 17.8 7 14.9a6.3 6.3 0 1 1 2.3 2.2l-3.1.7Z" stroke="white" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M9.1 8.3c-.3-.1-.6 0-.8.3-.5.7-.4 1.6.2 2.7 1 1.9 2.4 3 4.5 3.6.9.2 1.7 0 2.1-.7.2-.3.3-.7.1-.8l-1.8-.9c-.2-.1-.3 0-.5.2l-.6.7c-.1.2-.3.2-.5.1a5.4 5.4 0 0 1-2.4-2.1c-.1-.2-.1-.3.1-.5l.5-.6c.1-.2.2-.3.1-.5l-1-1.5Z" fill="white" />
        </>
      ) : (
        <>
          <circle cx="12" cy="12" r="12" fill="#26A5E4" />
          <path d="m5.1 11.6 12.7-4.9c.6-.2 1 .1.8.8l-2.2 10.1c-.1.7-.6.9-1.1.5l-3.4-2.5-1.6 1.6c-.2.2-.3.3-.6.3l.2-3.5 6.3-5.7c.3-.3-.1-.4-.4-.2l-7.8 4.9-3.3-1c-.7-.2-.7-.7.4-1.1Z" fill="white" />
        </>
      )}
    </svg>
  );
}
