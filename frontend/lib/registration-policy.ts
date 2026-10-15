import "server-only";

// Registration stays closed unless an operator explicitly reopens it.
export const isPublicRegistrationDisabled = process.env.DISABLE_PUBLIC_REGISTRATION !== "false";
