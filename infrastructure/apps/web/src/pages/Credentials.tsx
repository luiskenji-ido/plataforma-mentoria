import { LogIn, LogOut, PlugZap } from "lucide-react";
import { useState } from "react";
import { AWS_REGIONS, type AwsConnectionInput, type AwsConnectionStatus } from "@infra/shared";
import type { PageProps } from "../App";
import { Alert, Button, Card, Field, Input, KeyValue, PageHeader, Select, cn } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { ApiError, get, post } from "../services/api";

type Mode = AwsConnectionInput["mode"];
const MODES: { key: Mode; title: string; text: string }[] = [
  { key: "profile", title: "Perfil da AWS CLI", text: "Usa um perfil de ~/.aws (chaves ou papel). Nada é copiado para o painel." },
  { key: "sso", title: "AWS SSO (IAM Identity Center)", text: "Login oficial pelo navegador; o painel nunca vê sua senha." },
  { key: "temporary", title: "Credenciais temporárias", text: "Access key + secret (+ session token). Ficam só na memória da API." },
];

export function CredentialsPage({ aws, refreshAws }: PageProps) {
  const { draft } = useConfig();
  const profiles = useAsync(() => get<{ profiles: { name: string; kind: string; region?: string }[] }>("/api/aws/profiles"), []);
  const [mode, setMode] = useState<Mode>("profile");
  const [profile, setProfile] = useState("");
  const [region, setRegion] = useState(draft?.instance.region ?? "sa-east-1");
  const [accessKeyId, setAccessKeyId] = useState("");
  const [secretAccessKey, setSecretAccessKey] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [result, setResult] = useState<AwsConnectionStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const list = profiles.data?.profiles ?? [];
  const filtered = mode === "sso" ? list.filter((p) => p.kind === "sso") : list.filter((p) => p.kind !== "sso");

  async function connect() {
    setBusy(true);
    setError(undefined);
    try {
      const body: AwsConnectionInput =
        mode === "temporary" ? { mode, accessKeyId, secretAccessKey, sessionToken: sessionToken || undefined, region } : { mode, profile, region };
      const r = await post<AwsConnectionStatus>("/api/aws/connect", body);
      setResult(r);
      if (r.connected) {
        setSecretAccessKey("");
        setSessionToken("");
      }
      refreshAws();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function ssoLogin() {
    setBusy(true);
    setError(undefined);
    try {
      const r = await post<{ ok: boolean; error?: string }>("/api/aws/sso-login", { profile });
      if (!r.ok) setError(r.error);
      else await connect();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const shown = result ?? aws;
  return (
    <>
      <PageHeader title="Credenciais AWS" description="Escolha como o painel acessa a sua conta. Use um usuário IAM, um papel ou o SSO — nunca a conta root." />
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card title="Conectar">
          <div role="radiogroup" aria-label="Forma de conexão" className="mb-5 grid gap-3 sm:grid-cols-3">
            {MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                role="radio"
                aria-checked={mode === m.key}
                onClick={() => setMode(m.key)}
                className={cn(
                  "rounded-lg border p-3 text-left text-sm transition",
                  mode === m.key ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500/30 dark:bg-indigo-950" : "border-slate-200 hover:border-slate-400 dark:border-slate-700",
                )}
              >
                <span className="block font-semibold">{m.title}</span>
                <span className="mt-1 block text-xs text-slate-600 dark:text-slate-400">{m.text}</span>
              </button>
            ))}
          </div>
          <form
            className="grid gap-4 sm:grid-cols-2"
            autoComplete="off"
            onSubmit={(e) => {
              e.preventDefault();
              void connect();
            }}
          >
            {mode !== "temporary" ? (
              <Field label="Perfil" htmlFor="perfil" help={filtered.length ? undefined : mode === "sso" ? "Nenhum perfil SSO em ~/.aws/config. Configure com: aws configure sso" : "Nenhum perfil em ~/.aws. Configure com: aws configure"}>
                {filtered.length ? (
                  <Select id="perfil" value={profile} onChange={(e) => setProfile(e.target.value)} required>
                    <option value="">Escolha…</option>
                    {filtered.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.name} ({p.kind})
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input id="perfil" value={profile} onChange={(e) => setProfile(e.target.value)} placeholder="default" required />
                )}
              </Field>
            ) : (
              <>
                <Field label="Access Key ID" htmlFor="akid">
                  <Input id="akid" value={accessKeyId} onChange={(e) => setAccessKeyId(e.target.value.trim())} placeholder="ASIA…" autoComplete="off" spellCheck={false} required />
                </Field>
                <Field label="Secret Access Key" htmlFor="sak">
                  <Input id="sak" type="password" value={secretAccessKey} onChange={(e) => setSecretAccessKey(e.target.value)} autoComplete="new-password" required />
                </Field>
                <Field label="Session Token" htmlFor="st" help="Obrigatório para credenciais temporárias (ASIA…).">
                  <Input id="st" type="password" value={sessionToken} onChange={(e) => setSessionToken(e.target.value)} autoComplete="new-password" />
                </Field>
              </>
            )}
            <Field label="Região" htmlFor="regiao" help="Região usada para o teste e as consultas.">
              <Select id="regiao" value={region} onChange={(e) => setRegion(e.target.value)}>
                {AWS_REGIONS.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.name} — {r.code}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button type="submit" icon={<PlugZap className="h-4 w-4" />} loading={busy}>
                Testar conexão com a AWS
              </Button>
              {mode === "sso" && (
                <Button variant="secondary" icon={<LogIn className="h-4 w-4" />} onClick={() => void ssoLogin()} disabled={!profile || busy}>
                  Entrar com SSO
                </Button>
              )}
              {aws?.connected && (
                <Button
                  variant="ghost"
                  icon={<LogOut className="h-4 w-4" />}
                  onClick={() => void post("/api/aws/disconnect").then(() => {
                    setResult(undefined);
                    refreshAws();
                  })}
                >
                  Desconectar
                </Button>
              )}
            </div>
          </form>
          {error && (
            <div className="mt-4">
              <Alert tone="error">{error}</Alert>
            </div>
          )}
        </Card>
        <Card title="Situação">
          {shown?.connected ? (
            <div className="space-y-3">
              <Alert tone="success" title="Autenticado na AWS" />
              <KeyValue
                items={[
                  ["Conta", shown.accountId],
                  ["Identidade", <code key="arn" className="text-xs">{shown.arn}</code>],
                  ["Região", shown.region],
                  ["Forma", shown.mode === "temporary" ? "credenciais temporárias (memória)" : `${shown.mode} · ${shown.profile}`],
                ]}
              />
            </div>
          ) : shown?.error ? (
            <Alert tone="error" title="Autenticação falhou">
              {shown.error}
            </Alert>
          ) : (
            <p className="text-sm text-slate-600 dark:text-slate-400">Ainda não conectado.</p>
          )}
          <p className="mt-4 text-xs text-slate-500">O teste usa STS GetCallerIdentity. Nenhuma chave é mostrada, gravada ou enviada a terceiros.</p>
        </Card>
      </div>
    </>
  );
}
