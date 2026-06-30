import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
    CredentialsProvider({
      name: "Email and password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = String(credentials?.email ?? "").trim();
        const password = String(credentials?.password ?? "");

        if (!email || !password) {
          return null;
        }

        const response = await fetch(`${apiBaseUrl}/auth/login`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
          return null;
        }

        const token = (await response.json()) as {
          access_token?: string;
          token_type?: string;
        };

        if (!token.access_token) {
          return null;
        }

        return {
          id: email,
          email,
          accessToken: token.access_token,
        };
      },
    }),
  ],
  callbacks: {
    async signIn({ account, profile, user }) {
      if (account?.provider !== "google") {
        return true;
      }

      const email = user.email ?? profile?.email;
      if (!email || !account.providerAccountId) {
        return false;
      }

      const response = await fetch(`${apiBaseUrl}/auth/session/exchange`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          provider: account.provider,
          provider_account_id: account.providerAccountId,
          full_name: user.name ?? profile?.name ?? null,
          secret: process.env.NEXTAUTH_BACKEND_SECRET,
        }),
      });

      if (!response.ok) {
        return false;
      }

      const token = (await response.json()) as { access_token?: string };
      user.accessToken = token.access_token;
      return Boolean(user.accessToken);
    },
    async jwt({ token, user, account, profile }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.provider = account?.provider;
        token.providerAccountId = account?.providerAccountId;
        token.email = user.email ?? profile?.email ?? token.email;
      }
      return token;
    },
    async session({ session, token }) {
      session.user = {
        ...session.user,
        email: token.email,
      };
      session.accessToken = token.accessToken;
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
  session: {
    strategy: "jwt",
  },
};
