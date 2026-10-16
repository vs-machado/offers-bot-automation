"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export function SettingsRedirect() {
  const router = useRouter();

  useEffect(() => {
    // Fragments are browser-only; preserve existing bookmarked settings links.
    const hash = window.location.hash;
    const section =
      hash === "#sources"
        ? "sources"
        : hash === "#affiliates"
          ? "affiliates"
          : "destinations";
    router.replace(`/settings/${section}${hash === "#whatsapp" ? hash : ""}`);
  }, [router]);

  return (
    <p role="status" className="text-sm text-muted-foreground">
      Abrindo configurações.{" "}
      <Link href="/settings/destinations" className="text-primary underline">
        Ir para destinos
      </Link>
    </p>
  );
}
