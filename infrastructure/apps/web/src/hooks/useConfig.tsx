/**
 * Rascunho da configuração compartilhado entre as telas. Nada é gravado (nem criado na AWS) até o usuário clicar
 * em Salvar; criar recursos exige prévia + confirmação explícita em outra tela.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { deploymentConfigSchema, type DeploymentConfig } from "@infra/shared";
import { ApiError, get, post, put } from "../services/api";
import type { StoredConfigResponse } from "../services/types";

interface ConfigState {
  saved?: StoredConfigResponse;
  draft?: DeploymentConfig;
  dirty: boolean;
  saving: boolean;
  loadError?: string;
  saveError?: string;
  issues: Record<string, string>;
  update: (fn: (c: DeploymentConfig) => DeploymentConfig) => void;
  save: () => Promise<boolean>;
  discard: () => void;
  reload: () => Promise<void>;
  resolveAmi: () => Promise<void>;
}

const Ctx = createContext<ConfigState | null>(null);

function issuesFrom(list: { path: string; message: string }[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const i of list) {
    out[i.path] ??= i.message;
  }
  return out;
}

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<StoredConfigResponse>();
  const [draft, setDraft] = useState<DeploymentConfig>();
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const [saveError, setSaveError] = useState<string>();
  const [serverIssues, setServerIssues] = useState<Record<string, string>>({});

  const reload = useCallback(async () => {
    try {
      const r = await get<StoredConfigResponse>("/api/config");
      setSaved(r);
      setDraft(r.config);
      setLoadError(undefined);
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const dirty = useMemo(() => Boolean(saved && draft && JSON.stringify(saved.config) !== JSON.stringify(draft)), [saved, draft]);

  const clientIssues = useMemo(() => {
    if (!draft) return {};
    const r = deploymentConfigSchema.safeParse(draft);
    return r.success ? {} : issuesFrom(r.error.issues.map((i) => ({ path: i.path.join("."), message: i.message })));
  }, [draft]);

  const update = useCallback((fn: (c: DeploymentConfig) => DeploymentConfig) => {
    setDraft((c) => (c ? fn(c) : c));
    setServerIssues({});
    setSaveError(undefined);
  }, []);

  const save = useCallback(async () => {
    if (!draft) return false;
    setSaving(true);
    setSaveError(undefined);
    try {
      const r = await put<StoredConfigResponse>("/api/config", draft);
      setSaved(r);
      setDraft(r.config);
      setServerIssues({});
      return true;
    } catch (e) {
      const err = e as ApiError;
      setSaveError(err.message);
      setServerIssues(issuesFrom(err.issues ?? []));
      return false;
    } finally {
      setSaving(false);
    }
  }, [draft]);

  const resolveAmi = useCallback(async () => {
    const r = await post<StoredConfigResponse>("/api/config/resolve-ami");
    setSaved(r);
    setDraft(r.config);
  }, []);

  const value: ConfigState = {
    saved,
    draft,
    dirty,
    saving,
    loadError,
    saveError,
    issues: { ...clientIssues, ...serverIssues },
    update,
    save,
    discard: () => saved && setDraft(saved.config),
    reload,
    resolveAmi,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useConfig(): ConfigState {
  const c = useContext(Ctx);
  if (!c) throw new Error("useConfig fora do ConfigProvider");
  return c;
}
