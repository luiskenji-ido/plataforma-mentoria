/** Componentes de interface do painel (no espírito do shadcn/ui, feitos com Tailwind). */
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ComponentProps, type ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]) {
  return clsx(parts);
}

type Variant = "primary" | "secondary" | "danger" | "ghost" | "warning";
const variants: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-500 focus-visible:outline-indigo-600",
  secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800",
  danger: "bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600",
  warning: "bg-amber-500 text-slate-950 hover:bg-amber-400 focus-visible:outline-amber-500",
  ghost: "text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800",
};

export function Button({ variant = "primary", loading, icon, className, children, disabled, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

export function Card({ title, description, actions, children, className }: { title?: ReactNode; description?: ReactNode; actions?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
            {description && <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

const badgeTones = {
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300",
  red: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300",
  amber: "bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-200",
  blue: "bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-300",
  gray: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};
export function Badge({ tone = "gray", children }: { tone?: keyof typeof badgeTones; children: ReactNode }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", badgeTones[tone])}>{children}</span>;
}

const alertTones = {
  info: { cls: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950/60 dark:text-sky-100", Icon: Info },
  success: { cls: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-100", Icon: CheckCircle2 },
  warning: { cls: "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-100", Icon: AlertTriangle },
  error: { cls: "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/60 dark:text-red-100", Icon: XCircle },
};
export function Alert({ tone = "info", title, children }: { tone?: keyof typeof alertTones; title?: ReactNode; children?: ReactNode }) {
  const { cls, Icon } = alertTones[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border p-3 text-sm", cls)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="break-words">{children}</div>}
      </div>
    </div>
  );
}

export function Field({ label, help, error, children, htmlFor }: { label: ReactNode; help?: ReactNode; error?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {error ? <p className="text-xs font-medium text-red-700 dark:text-red-400">{error}</p> : help ? <p className="text-xs text-slate-600 dark:text-slate-400">{help}</p> : null}
    </div>
  );
}

const inputCls =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:disabled:bg-slate-900";

export function Input({ className, invalid, ...rest }: ComponentProps<"input"> & { invalid?: boolean }) {
  return <input className={cn(inputCls, invalid && "border-red-500", className)} aria-invalid={invalid || undefined} {...rest} />;
}

export function Select({ className, invalid, children, ...rest }: ComponentProps<"select"> & { invalid?: boolean }) {
  return (
    <select className={cn(inputCls, invalid && "border-red-500", className)} aria-invalid={invalid || undefined} {...rest}>
      {children}
    </select>
  );
}

export function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; description?: ReactNode; disabled?: boolean }) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn("relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full transition disabled:opacity-50", checked ? "bg-indigo-600" : "bg-slate-300 dark:bg-slate-700")}
      >
        <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      <label htmlFor={id} className="cursor-pointer text-sm">
        <span className="font-medium">{label}</span>
        {description && <span className="block text-xs text-slate-600 dark:text-slate-400">{description}</span>}
      </label>
    </div>
  );
}

/** Diálogo de confirmação: para ações cobradas ou destrutivas, exige digitar um texto exato. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  requireText,
  tone = "danger",
  loading,
  onConfirm,
  onClose,
  extraCheck,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  requireText?: string;
  tone?: "danger" | "warning" | "primary";
  loading?: boolean;
  onConfirm: (typed: string) => void;
  onClose: () => void;
  extraCheck?: { label: ReactNode; checked: boolean; onChange: (v: boolean) => void };
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal?.();
      if (!d.showModal) d.setAttribute("open", "");
    }
    if (!open && d.open) {
      d.close?.();
    }
  }, [open]);
  if (!open) return null;
  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="dlg-title" className="w-[min(560px,92vw)] rounded-xl border border-slate-200 bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
      <form
        method="dialog"
        className="space-y-4 p-6"
        onSubmit={(e) => {
          e.preventDefault();
          onConfirm(inputRef.current?.value ?? "");
        }}
      >
        <h2 id="dlg-title" className="text-lg font-semibold">
          {title}
        </h2>
        <div className="space-y-3 text-sm">{children}</div>
        {requireText && (
          <Field label={<>Digite <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">{requireText}</code> para confirmar</>} htmlFor="dlg-confirm">
            <Input id="dlg-confirm" ref={inputRef} autoComplete="off" spellCheck={false} />
          </Field>
        )}
        {extraCheck && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={extraCheck.checked} onChange={(e) => extraCheck.onChange(e.target.checked)} />
            <span>{extraCheck.label}</span>
          </label>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant={tone} loading={loading} disabled={extraCheck ? !extraCheck.checked : false}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </dialog>
  );
}

export function KeyValue({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
      {items.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-slate-600 dark:text-slate-400">{k}</dt>
          <dd className="min-w-0 break-words font-medium">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
