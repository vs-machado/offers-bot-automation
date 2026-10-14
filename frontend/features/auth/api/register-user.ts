import { getApiErrorMessage } from "@/lib/api-error-message";

type RegisterInput = {
  email: string;
  full_name: string | null;
  password: string;
};

export async function registerUser(input: RegisterInput) {
  const response = await fetch("/api/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getApiErrorMessage(data, "Não foi possível criar sua conta. Tente novamente."));
  }
}
