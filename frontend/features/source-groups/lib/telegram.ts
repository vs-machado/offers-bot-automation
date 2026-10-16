export function getTelegramPostId(postUrl?: string) {
  if (!postUrl) {
    return null;
  }

  try {
    const url = new URL(postUrl);
    if (!["t.me", "telegram.me"].includes(url.hostname.toLowerCase())) {
      return null;
    }

    const parts = url.pathname.split("/").filter(Boolean);
    if (parts.length < 2) {
      return null;
    }

    return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
  } catch {
    return null;
  }
}
