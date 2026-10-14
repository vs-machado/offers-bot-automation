"use client";

import Link from "next/link";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePasswordRecovery } from "@/features/auth/hooks/use-password-recovery";

export function PasswordRecovery({ mode }: { mode: "request" | "reset" }) {
  const recovery = usePasswordRecovery(mode);
  const inputClass = "mt-2 h-12 w-full rounded-xl border border-border bg-background px-3 text-foreground";
  const hasInvalidLink = mode === "reset" && recovery.isReady && !recovery.token;
  return <main className="flex min-h-dvh items-center justify-center bg-background px-4 py-10 text-foreground"><Card className="w-full max-w-md"><CardHeader><KeyRound className="mb-3 size-8 text-primary" /><CardTitle className="text-2xl">{mode === "request" ? "Esqueceu sua senha?" : "Crie uma nova senha"}</CardTitle><p className="mt-2 text-sm/6 text-muted-foreground">{mode === "request" ? "Informe seu e-mail para receber um link de recuperação. Ele será válido por 15 minutos." : "Use pelo menos 8 caracteres, uma letra maiúscula e um número ou símbolo."}</p></CardHeader><CardContent className="space-y-5">
    {recovery.isSuccess ? <p role="status" className="rounded-xl bg-primary/10 p-4 text-sm text-primary">{mode === "request" ? "Se houver uma conta para esse e-mail, você receberá um link de recuperação. Confira também a pasta de spam." : "Senha alterada! Suas sessões anteriores foram encerradas. Entre novamente com a nova senha."}</p> : hasInvalidLink ? <p role="alert" className="rounded-xl bg-destructive/10 p-4 text-sm text-destructive">O link não está completo ou não é válido. Solicite um novo link.</p> : <form onSubmit={recovery.submit} className="space-y-4">
      {mode === "request" ? <label className="block text-sm font-medium">E-mail<input name="email" type="email" required autoComplete="email" className={inputClass} placeholder="voce@exemplo.com.br" disabled={recovery.isSubmitting} /></label> : <><label className="block text-sm font-medium">Nova senha<input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={72} required className={inputClass} disabled={recovery.isSubmitting} /></label><label className="block text-sm font-medium">Confirme a nova senha<input name="confirmation" type="password" autoComplete="new-password" minLength={8} maxLength={72} required className={inputClass} disabled={recovery.isSubmitting} /></label></>}
      {recovery.error ? <p role="alert" className="text-sm text-destructive">{recovery.error}</p> : null}
      <Button type="submit" disabled={recovery.isSubmitting || (mode === "reset" && !recovery.isReady)} className="w-full">{recovery.isSubmitting ? "Aguarde…" : mode === "request" ? "Enviar link de recuperação" : "Salvar nova senha"}</Button>
    </form>}
    {hasInvalidLink || (mode === "reset" && recovery.error) ? <Link href="/forgot-password" className="block text-sm font-medium text-primary hover:underline">Solicitar outro link</Link> : null}
    <Link href="/?mode=signin" className="block text-center text-sm font-medium text-primary hover:underline">Voltar para entrar</Link>
  </CardContent></Card></main>;
}
