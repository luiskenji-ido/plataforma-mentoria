import type { HealthState } from "@infra/shared";

export interface HttpResult {
  ok: boolean;
  status?: number;
  error?: string;
  ms?: number;
}

export type HttpCheck = (url: string, timeoutMs?: number) => Promise<HttpResult>;

export const httpCheck: HttpCheck = async (url, timeoutMs = 8000) => {
  const started = Date.now();
  try {
    const res = await fetch(url, { method: "GET", redirect: "manual", signal: AbortSignal.timeout(timeoutMs) });
    // 2xx e 3xx (ex.: a tela de login redirecionando) contam como app respondendo
    return { ok: res.status >= 200 && res.status < 400, status: res.status, ms: Date.now() - started };
  } catch (error) {
    return { ok: false, error: (error as Error).name === "TimeoutError" ? "tempo esgotado" : (error as Error).message, ms: Date.now() - started };
  }
};

/** Tenta de novo com espera crescente (10 s, 15 s, 22 s… até 60 s) até o limite. */
export async function waitHealthy(
  url: string,
  check: HttpCheck,
  timeoutMs: number,
  onAttempt: (r: HttpResult, attempt: number) => void,
  wait: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms)),
): Promise<HttpResult> {
  const deadline = Date.now() + timeoutMs;
  let delay = 10_000;
  let attempt = 0;
  let last: HttpResult = { ok: false, error: "não verificado" };
  while (Date.now() < deadline) {
    attempt += 1;
    last = await check(url);
    onAttempt(last, attempt);
    if (last.ok) {
      return last;
    }
    await wait(Math.min(delay, Math.max(0, deadline - Date.now())));
    delay = Math.min(60_000, Math.round(delay * 1.5));
  }
  return last;
}

export interface HealthInputs {
  ec2State?: string;
  ssmOnline?: boolean;
  container?: { state: string; status: string };
  http?: HttpResult;
}

/** Estado do app com base em verificações reais (nada é presumido). */
export function classifyHealth(i: HealthInputs): { state: HealthState; reason: string } {
  if (!i.ec2State) {
    return { state: "Unknown", reason: "Instância não encontrada." };
  }
  if (["stopped", "stopping", "shutting-down", "terminated"].includes(i.ec2State)) {
    return { state: "Stopped", reason: `EC2 ${i.ec2State}.` };
  }
  if (i.ec2State !== "running") {
    return { state: "Unknown", reason: `EC2 ${i.ec2State}.` };
  }
  const containerKnown = Boolean(i.container);
  const containerUp = i.container?.state === "running" && !/unhealthy/.test(i.container.status);
  if (i.http?.ok && (containerUp || !containerKnown)) {
    return { state: "Running", reason: `HTTP ${i.http.status} em ${i.http.ms} ms${containerKnown ? " e contêiner saudável" : ""}.` };
  }
  if (i.http?.ok && containerKnown && !containerUp) {
    return { state: "Degraded", reason: `Responde HTTP, mas o contêiner está ${i.container?.status}.` };
  }
  if (containerKnown && !containerUp) {
    return { state: "Degraded", reason: `Contêiner ${i.container?.status || i.container?.state}.` };
  }
  if (containerUp && i.http && !i.http.ok) {
    return { state: "Degraded", reason: `Contêiner rodando, mas o HTTP falhou (${i.http.error ?? i.http.status}).` };
  }
  if (!i.http && !containerKnown) {
    return { state: "Unknown", reason: i.ssmOnline === false ? "Sem acesso pelo Systems Manager e sem URL pública." : "Ainda sem verificação." };
  }
  return { state: "Degraded", reason: `HTTP falhou (${i.http?.error ?? i.http?.status}).` };
}
