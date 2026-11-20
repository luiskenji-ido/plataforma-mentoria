import {
  Activity,
  Cloud,
  Container,
  Gauge,
  HardDrive,
  KeyRound,
  LayoutDashboard,
  Moon,
  Rocket,
  ScanEye,
  ScrollText,
  Server,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";
import type { AwsConnectionStatus } from "@infra/shared";
import { Badge, cn } from "./components/ui";
import { ConfigProvider } from "./hooks/useConfig";
import { useAsync } from "./hooks/useAsync";
import { get } from "./services/api";
import { CredentialsPage } from "./pages/Credentials";
import { DockerAppPage } from "./pages/DockerApp";
import { Ec2ConfigPage } from "./pages/Ec2Config";
import { InstancesPage } from "./pages/Instances";
import { LogsPage } from "./pages/Logs";
import { OverviewPage } from "./pages/Overview";
import { PreviewPage } from "./pages/Preview";
import { ProvisionPage } from "./pages/Provision";
import { SettingsPage } from "./pages/Settings";
import { StorageNetworkPage } from "./pages/StorageNetwork";

export interface PageProps {
  go: (page: PageKey) => void;
  aws: AwsConnectionStatus | undefined;
  refreshAws: () => void;
}

const PAGES = {
  overview: { label: "Visão geral", icon: LayoutDashboard, Component: OverviewPage },
  credentials: { label: "Credenciais AWS", icon: KeyRound, Component: CredentialsPage },
  ec2: { label: "Configuração da EC2", icon: Server, Component: Ec2ConfigPage },
  storage: { label: "Armazenamento e rede", icon: HardDrive, Component: StorageNetworkPage },
  docker: { label: "Docker e aplicação", icon: Container, Component: DockerAppPage },
  preview: { label: "Prévia da infraestrutura", icon: ScanEye, Component: PreviewPage },
  provision: { label: "Provisionamento e deploy", icon: Rocket, Component: ProvisionPage },
  instances: { label: "Instâncias e monitoramento", icon: Activity, Component: InstancesPage },
  logs: { label: "Logs e diagnóstico", icon: ScrollText, Component: LogsPage },
  settings: { label: "Configurações", icon: SettingsIcon, Component: SettingsPage },
} satisfies Record<string, { label: string; icon: ComponentType<{ className?: string }>; Component: ComponentType<PageProps> }>;
export type PageKey = keyof typeof PAGES;

function currentPage(): PageKey {
  const key = window.location.hash.replace(/^#\/?/, "");
  return key in PAGES ? (key as PageKey) : "overview";
}

function useTheme() {
  const [dark, setDark] = useState(() => {
    try {
      return localStorage.getItem("tema") === "escuro" || (!localStorage.getItem("tema") && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
    } catch {
      return false;
    }
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("tema", dark ? "escuro" : "claro"); // só a preferência de tema; nada sensível
    } catch {
      /* navegador sem localStorage */
    }
  }, [dark]);
  return [dark, setDark] as const;
}

export function App() {
  const [page, setPage] = useState<PageKey>(currentPage);
  const [dark, setDark] = useTheme();
  const aws = useAsync(() => get<AwsConnectionStatus>("/api/aws/status"), []);

  useEffect(() => {
    const onHash = () => setPage(currentPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (p: PageKey) => {
    window.location.hash = `/${p}`;
    setPage(p);
    window.scrollTo({ top: 0 });
  };
  const { Component } = PAGES[page];
  const status = aws.data;

  return (
    <ConfigProvider>
      <div className="flex min-h-screen">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-4 md:flex dark:border-slate-800 dark:bg-slate-900">
          <div className="mb-6 flex items-center gap-2 px-2">
            <Cloud className="h-6 w-6 text-indigo-600" aria-hidden />
            <div>
              <p className="text-sm font-bold leading-tight">Painel de Infraestrutura</p>
              <p className="text-xs text-slate-500">AWS EC2 · Pulumi · Docker</p>
            </div>
          </div>
          <nav aria-label="Seções" className="flex-1 space-y-0.5 overflow-y-auto">
            {(Object.keys(PAGES) as PageKey[]).map((key, i) => {
              const { label, icon: Icon } = PAGES[key];
              return (
                <a
                  key={key}
                  href={`#/${key}`}
                  aria-current={page === key ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                    page === key ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                  <span className="flex-1">{label}</span>
                  <span className="text-xs text-slate-400">{i + 1}</span>
                </a>
              );
            })}
          </nav>
          <p className="px-2 pt-4 text-xs text-slate-500">Acesso só por este computador (localhost).</p>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
            <select
              className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm md:hidden dark:border-slate-700 dark:bg-slate-950"
              value={page}
              onChange={(e) => go(e.target.value as PageKey)}
              aria-label="Seção"
            >
              {(Object.keys(PAGES) as PageKey[]).map((k) => (
                <option key={k} value={k}>
                  {PAGES[k].label}
                </option>
              ))}
            </select>
            <div className="flex flex-1 items-center justify-end gap-3">
              <Gauge className="hidden h-4 w-4 text-slate-400 sm:block" aria-hidden />
              {status?.connected ? (
                <Badge tone="green">
                  AWS {status.accountId} · {status.region}
                </Badge>
              ) : (
                <Badge tone="amber">AWS desconectada</Badge>
              )}
              <button
                type="button"
                onClick={() => setDark(!dark)}
                className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                aria-label={dark ? "Usar tema claro" : "Usar tema escuro"}
              >
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
            </div>
          </header>
          <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
            <Component go={go} aws={status} refreshAws={() => void aws.reload()} />
          </main>
        </div>
      </div>
    </ConfigProvider>
  );
}
