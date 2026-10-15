import "server-only";
import { betterAuth } from "better-auth";
import { APIError, createAuthMiddleware } from "better-auth/api";
import { hashPassword, verifyPassword } from "better-auth/crypto";
import { nextCookies } from "better-auth/next-js";
import { compare } from "bcryptjs";
import { Pool } from "pg";
import { randomUUID } from "node:crypto";
import { after } from "next/server";
import { getPasswordError } from "@/lib/password-policy";
import { isEmailConfigured, sendAuthEmail } from "@/lib/auth-email";
import { isPublicRegistrationDisabled } from "@/lib/registration-policy";

const baseURL = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";
const pool = new Pool({ connectionString: process.env.AUTH_DATABASE_URL ?? "postgresql://postgres:password@localhost:5434/offers_db", max: 10, connectionTimeoutMillis: 10000 });

function createAuth() {
  if (!process.env.BETTER_AUTH_SECRET || process.env.BETTER_AUTH_SECRET.length < 32) throw new Error("Configure BETTER_AUTH_SECRET com pelo menos 32 caracteres aleatórios.");
  const origin = new URL(baseURL);
  if (process.env.NODE_ENV === "production" && origin.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname)) throw new Error("BETTER_AUTH_URL precisa usar HTTPS fora do ambiente local.");
  return betterAuth({
  appName: "Offers Bot", baseURL,
  secret: process.env.BETTER_AUTH_SECRET,
  trustedOrigins: [new URL(baseURL).origin],
  database: pool,
  advanced: { database: { generateId: () => randomUUID() }, backgroundTasks: { handler: (promise) => after(async () => { await promise; }) } },
  user: { modelName: "auth_users", fields: { emailVerified: "email_verified", createdAt: "created_at", updatedAt: "updated_at" } },
  session: { modelName: "auth_sessions", expiresIn: 60 * 60 * 24 * 7, cookieCache: { enabled: false }, fields: { userId: "user_id", expiresAt: "expires_at", createdAt: "created_at", updatedAt: "updated_at", ipAddress: "ip_address", userAgent: "user_agent" } },
  account: { modelName: "auth_accounts", accountLinking: { enabled: false }, fields: { userId: "user_id", accountId: "account_id", providerId: "provider_id", accessToken: "access_token", refreshToken: "refresh_token", idToken: "id_token", accessTokenExpiresAt: "access_token_expires_at", refreshTokenExpiresAt: "refresh_token_expires_at", createdAt: "created_at", updatedAt: "updated_at" } },
  verification: { modelName: "auth_verifications", storeIdentifier: "hashed", fields: { expiresAt: "expires_at", createdAt: "created_at", updatedAt: "updated_at" } },
  rateLimit: { enabled: true, storage: "database", modelName: "auth_rate_limits", fields: { lastRequest: "last_request" }, window: 60, max: 30, customRules: { "/request-password-reset": { window: 60, max: 3 }, "/reset-password": { window: 60, max: 5 }, "/sign-in/email": { window: 60, max: 5 }, "/sign-up/email": { window: 60, max: 5 } } },
  socialProviders: process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET ? { google: { clientId: process.env.GOOGLE_CLIENT_ID, clientSecret: process.env.GOOGLE_CLIENT_SECRET, disableSignUp: isPublicRegistrationDisabled } } : {},
  databaseHooks: { user: { create: { before: async () => {
    if (isPublicRegistrationDisabled) throw new APIError("FORBIDDEN", { code: "REGISTRATION_DISABLED", message: "Cadastros temporariamente indisponíveis." });
  } } } },
  emailAndPassword: {
    enabled: true, disableSignUp: isPublicRegistrationDisabled, minPasswordLength: 8, maxPasswordLength: 72,
    resetPasswordTokenExpiresIn: 15 * 60, revokeSessionsOnPasswordReset: true,
    password: { hash: hashPassword, verify: ({ hash, password }) => hash.startsWith("$2") ? compare(password, hash) : verifyPassword({ hash, password }) },
    sendResetPassword: async ({ user, token }) => {
      const resetURL = `${baseURL.replace(/\/$/, "")}/reset-password#token=${encodeURIComponent(token)}`;
      await sendAuthEmail(user.email, "Redefina sua senha — Offers Bot", `Recebemos um pedido para redefinir sua senha.\n\nAbra este link para criar uma nova senha:\n${resetURL}\n\nO link expira em 15 minutos e só pode ser usado uma vez. Se você não fez esse pedido, ignore este e-mail.`);
    },
    onPasswordReset: async ({ user }) => {
      after(() => sendAuthEmail(user.email, "Sua senha foi alterada — Offers Bot", "Sua senha foi alterada e as sessões anteriores foram encerradas. Se não foi você, solicite outra redefinição de senha imediatamente."));
    },
  },
  hooks: { before: createAuthMiddleware(async (context) => {
    if (context.path === "/sign-up/email") {
      if (typeof context.body?.name === "string" && context.body.name.trim().length > 255) throw new APIError("BAD_REQUEST", { message: "Use um nome com até 255 caracteres." });
      if (typeof context.body?.email === "string" && context.body.email.length > 255) throw new APIError("BAD_REQUEST", { message: "O e-mail informado ficou muito longo." });
    }
    if (["/sign-up/email", "/reset-password", "/change-password", "/set-password"].includes(context.path)) {
      const password = context.body?.newPassword ?? context.body?.password;
      if (typeof password === "string") {
        const message = getPasswordError(password);
        if (message) throw new APIError("BAD_REQUEST", { message });
      }
    }
    if (context.path === "/request-password-reset" && !isEmailConfigured()) throw new APIError("SERVICE_UNAVAILABLE", { message: "A recuperação de senha não está disponível no momento. Entre em contato com o administrador." });
  }) },
  plugins: [nextCookies()],
  });
}

let instance: ReturnType<typeof createAuth> | undefined;

export function getAuth() {
  // Build-time route discovery must not initialize auth or require runtime secrets.
  return instance ??= createAuth();
}
