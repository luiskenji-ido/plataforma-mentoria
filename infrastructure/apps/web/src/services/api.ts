/** Cliente da API local. O token anti-CSRF vem de /api/session (só o próprio painel consegue ler). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly issues: { path: string; message: string }[] = [],
  ) {
    super(message);
  }
}

let csrfToken: string | undefined;

async function token(): Promise<string> {
  if (!csrfToken) {
    const res = await fetch("/api/session", { credentials: "same-origin" });
    csrfToken = ((await res.json()) as { csrfToken: string }).csrfToken;
  }
  return csrfToken;
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRF-Token"] = await token();
  }
  const res = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? (method === "GET" ? undefined : "{}") : JSON.stringify(options.body),
  });
  const data = (await res.json().catch(() => ({}))) as { error?: string; issues?: { path: string; message: string }[] };
  if (!res.ok) {
    if (res.status === 403 && /token/i.test(data.error ?? "")) {
      csrfToken = undefined; // a API reiniciou: o próximo pedido busca um token novo
    }
    throw new ApiError(data.error ?? `Erro ${res.status}`, res.status, data.issues ?? []);
  }
  return data as T;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: "POST", body });
export const put = <T>(path: string, body?: unknown) => api<T>(path, { method: "PUT", body });
