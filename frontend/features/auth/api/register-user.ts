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
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : "Could not create account.");
  }
}
