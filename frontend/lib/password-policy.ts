export function getPasswordError(password: string): string {
  if (password.length < 8) return "Use uma senha com pelo menos 8 caracteres.";
  if (new TextEncoder().encode(password).length > 72) return "Sua senha ficou muito longa. Use até 72 bytes.";
  if (!/[A-Z]/.test(password)) return "Inclua uma letra maiúscula na senha.";
  if (!/[0-9\W_]/.test(password)) return "Inclua um número ou símbolo na senha.";
  if (["password1", "qwerty123", "admin123"].includes(password.toLowerCase())) return "Essa senha é muito comum. Escolha outra.";
  return "";
}
