"use client";

import { PageNotice } from "@/components/PageNotice";

export default function ErrorPage({ unstable_retry }: { unstable_retry: () => void }) {
  return <PageNotice title="Não foi possível carregar esta página" description="Tivemos um problema ao carregar as informações. Tente novamente em instantes." onRetry={unstable_retry} />;
}
