import { CheckCircle2, Lock, XCircle } from "lucide-react";
import { useState } from "react";
import type { PageProps } from "../App";
import { Alert, Button, Card, Field, Input, KeyValue, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { ApiError, get, post } from "../services/api";
import type { DoctorResponse } from "../services/types";

export function SettingsPage(_props: PageProps) {
  const doctor = useAsync(() => get<DoctorResponse>("/api/doctor"), []);
  const settings = useAsync(() => get<{ passphraseSet: boolean; stateDir: string; backendUrl: string; repoRoot: string; host: string; port: number }>("/api/settings"), []);
  const [pass, setPass] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string }>();

  async function savePass() {
    try {
      await post("/api/settings/passphrase", { passphrase: pass });
      setPass("");
      setMsg({ tone: "success", text: "Senha definida para esta execução do painel." });
      void settings.reload();
      void doctor.reload();
    } catch (e) {
      setMsg({ tone: "error", text: (e as ApiError).message });
    }
  }

  return (
    <>
      <PageHeader title="Configurações" description="Pré-requisitos, senha do estado do Pulumi e onde ficam os arquivos." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pré-requisitos" actions={<Button variant="secondary" onClick={() => void doctor.reload()} loading={doctor.loading}>Verificar de novo</Button>}>
          <ul className="space-y-2 text-sm">
            {doctor.data?.tools.map((t) => (
              <li key={t.name} className="flex items-start gap-2">
                {t.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden /> : <XCircle className={`mt-0.5 h-4 w-4 ${t.required ? "text-red-600" : "text-amber-500"}`} aria-hidden />}
                <div>
                  <p className="font-medium">
                    {t.name} {t.version && <span className="font-normal text-slate-500">{t.version}</span>} {!t.required && <span className="text-xs text-slate-500">(opcional)</span>}
                  </p>
                  {!t.ok && <p className="text-xs text-slate-600 dark:text-slate-400">{t.help}</p>}
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-500">O painel não instala nada sozinho: siga as instruções de cada item.</p>
        </Card>
        <Card title="Senha do estado do Pulumi" description="Cifra os segredos do stack (SECRET_KEY, senhas do banco e variáveis secretas). Sem ela nada é criado.">
          {settings.data?.passphraseSet ? (
            <Alert tone="success" title="Senha definida">Fica só na memória da API. Ao reiniciar o painel, informe de novo (ou use PULUMI_CONFIG_PASSPHRASE).</Alert>
          ) : (
            <Alert tone="warning" title="Senha não definida" />
          )}
          <form className="mt-4 space-y-3" onSubmit={(e) => { e.preventDefault(); void savePass(); }}>
            <Field label="Senha (mínimo 12 caracteres)" htmlFor="pp" help="Guarde num gerenciador de senhas: sem ela não dá para ler os segredos nem alterar o stack.">
              <Input id="pp" type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="new-password" minLength={12} />
            </Field>
            <Button type="submit" icon={<Lock className="h-4 w-4" />} disabled={pass.length < 12}>Definir senha</Button>
          </form>
          {msg && <div className="mt-3"><Alert tone={msg.tone}>{msg.text}</Alert></div>}
        </Card>
        <Card title="Arquivos e estado" className="lg:col-span-2">
          {settings.data && (
            <KeyValue
              items={[
                ["Repositório da aplicação", <code key="r" className="text-xs">{settings.data.repoRoot}</code>],
                ["Estado do painel", <code key="s" className="text-xs">{settings.data.stateDir}</code>],
                ["Backend do Pulumi", <code key="b" className="text-xs">{settings.data.backendUrl}</code>],
                ["API", `${settings.data.host}:${settings.data.port} (só local)`],
              ]}
            />
          )}
          <div className="mt-4">
            <Alert tone="info" title="Proteja o estado">
              A pasta .state guarda o estado do Pulumi (com os segredos cifrados) e os logs. Faça backup dela; sem o estado o Pulumi não consegue alterar nem destruir a
              infraestrutura. O backend local não tem trava entre computadores: gerencie cada stack de um só lugar.
            </Alert>
          </div>
        </Card>
      </div>
    </>
  );
}
