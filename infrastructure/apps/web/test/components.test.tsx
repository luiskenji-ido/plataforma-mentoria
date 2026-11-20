import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CostEstimate, OperationSummary } from "@infra/shared";
import { OperationPanel, StepList } from "../src/components/OperationView";
import { ConfirmDialog } from "../src/components/ui";
import { ConfigProvider } from "../src/hooks/useConfig";
import { CredentialsPage } from "../src/pages/Credentials";
import { CostTable } from "../src/pages/Ec2Config";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const summary: OperationSummary = {
  id: "1",
  kind: "provision",
  stackName: "mentoria-x",
  status: "failed",
  startedAt: new Date().toISOString(),
  error: "O build da imagem falhou",
  steps: [
    { key: "build", label: "Gerando a imagem Docker", status: "failed", detail: "código 1" },
    { key: "infra", label: "Criando a infraestrutura", status: "skipped" },
    { key: "credentials", label: "Validando as credenciais", status: "done" },
  ],
};

describe("acompanhamento das operações", () => {
  it("mostra o estado de cada passo de forma acessível", () => {
    render(<StepList summary={summary} />);
    expect(screen.getByText("(falhou)")).toBeInTheDocument();
    expect(screen.getByText("(não executado)")).toBeInTheDocument();
    expect(screen.getByText("código 1")).toBeInTheDocument();
  });

  it("falha mostra o erro e explica o que já pode existir", () => {
    render(<OperationPanel summary={summary} events={[{ seq: 1, time: new Date().toISOString(), type: "log", message: "docker build…", level: "error" }]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("O build da imagem falhou");
    expect(screen.getByRole("alert")).toHaveTextContent(/recursos já criados continuam na conta/);
    expect(screen.getByRole("log")).toHaveTextContent("docker build…");
  });
});

describe("custos", () => {
  it("lista os itens, o total e o que cobra com a EC2 parada", () => {
    const cost: CostEstimate = {
      lines: [
        { item: "EC2 t3.small", monthlyUsd: 15.18, source: "AWS Price List API", chargedWhenStopped: false },
        { item: "EBS raiz gp3 20 GiB", monthlyUsd: 1.9, source: "AWS Price List API", chargedWhenStopped: true },
        { item: "IPv4 público", monthlyUsd: null, source: "?", chargedWhenStopped: false },
      ],
      monthlyTotalUsd: 17.08,
      incomplete: true,
      pricingDate: "2026-11-20",
      disclaimer: "Estimativa.",
    };
    render(<CostTable cost={cost} />);
    expect(screen.getByText("17.08")).toBeInTheDocument();
    expect(screen.getByText(/sem os itens com \?/)).toBeInTheDocument();
    expect(screen.getByText("(cobra com a EC2 parada)")).toBeInTheDocument();
  });
});

describe("confirmação", () => {
  it("entrega o texto digitado e só habilita com o aceite marcado", async () => {
    const onConfirm = vi.fn();
    const Harness = () => {
      return (
        <ConfirmDialog open title="Destruir?" confirmLabel="Destruir" requireText="destruir x" onClose={() => undefined} onConfirm={onConfirm} extraCheck={{ label: "Entendo", checked: false, onChange: () => undefined }}>
          <p>texto</p>
        </ConfirmDialog>
      );
    };
    render(<Harness />);
    expect(screen.getByRole("button", { name: "Destruir" })).toBeDisabled();
  });

  it("envia o texto digitado para conferência", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open title="Destruir?" confirmLabel="Destruir" requireText="destruir x" onClose={() => undefined} onConfirm={onConfirm}>
        <p>texto</p>
      </ConfirmDialog>,
    );
    await userEvent.type(screen.getByLabelText(/para confirmar/), "destruir x");
    fireEvent.click(screen.getByRole("button", { name: "Destruir" }));
    expect(onConfirm).toHaveBeenCalledWith("destruir x");
  });
});

describe("credenciais", () => {
  it("conecta com credenciais temporárias, limpa o segredo da tela e não guarda nada no navegador", async () => {
    const calls: { url: string; body?: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, body: init?.body as string | undefined });
        const json = (data: unknown) => new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
        if (url === "/api/session") return json({ csrfToken: "t" });
        if (url === "/api/aws/profiles") return json({ profiles: [] });
        if (url === "/api/config") return json({ config: (await import("@infra/shared")).defaultDeploymentConfig(), updatedAt: "", secretsVersion: 0, configHash: "0000000000000000" });
        if (url === "/api/aws/connect") return json({ connected: true, mode: "temporary", region: "sa-east-1", accountId: "123456789012", arn: "arn:aws:sts::123456789012:assumed-role/Dev/eu" });
        return json({});
      }),
    );
    render(
      <ConfigProvider>
        <CredentialsPage go={() => undefined} aws={{ connected: false }} refreshAws={() => undefined} />
      </ConfigProvider>,
    );
    await userEvent.click(screen.getByRole("radio", { name: /Credenciais temporárias/ }));
    await userEvent.type(screen.getByLabelText("Access Key ID"), "ASIAABCDEFGHIJKLMNOP");
    await userEvent.type(screen.getByLabelText("Secret Access Key"), "segredo-que-nao-pode-ficar-na-tela-1234");
    await userEvent.click(screen.getByRole("button", { name: /Testar conexão/ }));
    await waitFor(() => expect(screen.getByText("Autenticado na AWS")).toBeInTheDocument());
    expect(screen.getByText("123456789012")).toBeInTheDocument();
    expect(screen.getByLabelText("Secret Access Key")).toHaveValue("");
    const connect = calls.find((c) => c.url === "/api/aws/connect");
    expect(JSON.parse(connect!.body!)).toMatchObject({ mode: "temporary", accessKeyId: "ASIAABCDEFGHIJKLMNOP" });
    expect(JSON.stringify({ ...localStorage })).not.toContain("segredo");
    expect(document.cookie).not.toContain("segredo");
  });
});
