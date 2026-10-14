import Link from "next/link";
import { Button } from "@/components/ui/button";

type PageNoticeProps = {
  title: string;
  description: string;
  onRetry?: () => void;
};

export function PageNotice({ title, description, onRetry }: PageNoticeProps) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="max-w-md space-y-4 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm/6 text-muted-foreground">{description}</p>
        {onRetry ? <Button onClick={onRetry}>Tentar novamente</Button> : null}
        <div><Link href="/" className="text-sm font-medium text-primary underline underline-offset-4">Voltar ao início</Link></div>
      </div>
    </main>
  );
}
