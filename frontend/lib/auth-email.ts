import "server-only";
import nodemailer from "nodemailer";

export function isEmailConfigured() {
  return Boolean(process.env.SMTP_HOST && process.env.SMTP_FROM);
}

export async function sendAuthEmail(to: string, subject: string, text: string) {
  if (!isEmailConfigured()) { console.error("O envio de e-mails de autenticação não está configurado."); return; }
  const secure = process.env.SMTP_SECURE === "true";
  const transport = nodemailer.createTransport({
    host: process.env.SMTP_HOST, port: Number(process.env.SMTP_PORT ?? (secure ? "465" : "587")), secure,
    requireTLS: !secure && process.env.SMTP_REQUIRE_TLS !== "false",
    auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD } : undefined,
    connectionTimeout: 10000, greetingTimeout: 10000, socketTimeout: 10000,
  });
  try {
    await transport.sendMail({ from: process.env.SMTP_FROM, to, subject, text });
  } catch {
    // SMTP errors can contain recipients and credentials. Do not log their payloads.
    console.error("Não foi possível enviar um e-mail de autenticação.");
  } finally {
    transport.close();
  }
}
