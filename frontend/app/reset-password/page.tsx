import type { Metadata } from "next";
import { PasswordRecovery } from "@/features/auth/PasswordRecovery";

export const metadata: Metadata = { referrer: "no-referrer", robots: { index: false, follow: false } };
export default function Page() { return <PasswordRecovery mode="reset" />; }
