/**
 * Mascara segredos antes de qualquer texto sair do processo (logs, eventos ao vivo, arquivos de log e respostas).
 * Além dos padrões conhecidos (chaves AWS, tokens, senhas em URL), todo segredo que a API manipula é registrado aqui.
 */
const known = new Set<string>();

// Os padrões exigem um separador de atribuição (= ou :) para não mascarar texto comum ("senha não definida").
const PATTERNS: [RegExp, string][] = [
  [/\b(AKIA|ASIA)[A-Z0-9]{16}\b/g, "$1****************"],
  [/(aws_secret_access_key|aws_session_token|secretAccessKey|sessionToken|SecretAccessKey|SessionToken)(["']?\s*[:=]\s*["']?)[A-Za-z0-9/+=]{16,}/g, "$1$2****"],
  [/(PULUMI_CONFIG_PASSPHRASE)(["']?\s*[:=]\s*["']?)[^\s"']+/g, "$1$2****"],
  [/([a-z][a-z0-9+.-]*:\/\/[^:/\s@]+:)[^@\s/]+@/gi, "$1****@"],
  [/(Authorization["']?\s*[:=]\s*["']?(?:Basic|Bearer)\s+)[A-Za-z0-9._~+/=-]+/gi, "$1****"],
  [/((?:password|passwd|senha)["']?\s*[:=]\s*["']?)[^\s"',}]+/gi, "$1****"],
];

export function registerSecret(value: string | undefined | null): void {
  if (value && value.length >= 6) {
    known.add(value);
  }
}

export function forgetSecret(value: string | undefined | null): void {
  if (value) {
    known.delete(value);
  }
}

export function redact(text: string): string {
  let out = text;
  for (const secret of known) {
    if (out.includes(secret)) {
      out = out.split(secret).join("****");
    }
  }
  for (const [pattern, replacement] of PATTERNS) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

/** Mensagem de erro segura para mostrar na tela: sem pilha, sem segredos. */
export function safeErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return redact(message).slice(0, 2000);
}
