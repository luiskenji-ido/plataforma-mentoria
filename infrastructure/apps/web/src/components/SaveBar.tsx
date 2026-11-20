import { Save, Undo2 } from "lucide-react";
import { useConfig } from "../hooks/useConfig";
import { Alert, Button } from "./ui";

/** Barra fixa com Salvar/Descartar quando o rascunho da configuração tem mudanças. */
export function SaveBar() {
  const { dirty, saving, save, discard, saveError, issues } = useConfig();
  const count = Object.keys(issues).length;
  if (!dirty && !saveError) return null;
  return (
    <div className="sticky bottom-0 z-10 -mx-6 mt-6 border-t border-slate-200 bg-white/95 px-6 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
      {saveError && (
        <div className="mb-2">
          <Alert tone="error" title="Não foi possível salvar">
            {saveError}
          </Alert>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {count ? `${count} campo(s) para corrigir antes de salvar.` : "Mudanças não salvas. Salvar não cria nada na AWS."}
        </p>
        <div className="flex gap-2">
          <Button variant="secondary" icon={<Undo2 className="h-4 w-4" />} onClick={discard} disabled={saving}>
            Descartar
          </Button>
          <Button icon={<Save className="h-4 w-4" />} onClick={() => void save()} loading={saving} disabled={count > 0}>
            Salvar configuração
          </Button>
        </div>
      </div>
    </div>
  );
}
