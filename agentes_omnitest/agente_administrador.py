"""
AGENTE OMNITEST — PERFIL ADMINISTRADOR
Uso: python agentes_omnitest/agente_administrador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Administrador. Para rodar todos os perfis use executar_todos.py.
Atenção: na Manutenção (DB) o agente nunca clica em restaurar nem em apagar dados.
Backup e restauração saíram da plataforma: o agente confere que os endereços antigos respondem 404.
"""
from nucleo import AgenteOmniTest, executar_cli, BASE_URL, APROVADO, FALHA


class AgenteAdministrador(AgenteOmniTest):
    chave_perfil = "administrador"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "todos"

    # Regra 2: o Administrador acede ao Portal de Demandas, à Biblioteca e gere utilizadores
    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "usuarios", "grupos", "demandas", "banca", "esg_csv", "esg_pdf", "atividades_extras", "reunioes", "agenda_bancas", "avaliadores_banca", "minhas_bancas", "indicadores", "certificados", "repositorio", "agentes_ia"]
    ROTAS_BLOQUEADAS = []
    MENU_VISIVEL = ["agentes_ia", "indicadores", "agenda_bancas", "avaliadores_banca", "atividades_extras", "reunioes", "dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "usuarios", "demandas", "biblioteca"]
    MENU_OCULTO = []

    ROTEIRO = [
        "Cadastros & Usuários: tabela carregada e busca pelo e-mail do próprio utilizador de teste (Regra 2)",
        "Painel Geral: KPIs recalculados com todos os alunos da plataforma",
        "Relógio de Voluntariado visível e modal de lançamento manual",
        "Portal de Demandas: abrir ticket e responder oficialmente como gestor",
        "Relatório ESG (CSV): uma linha por lançamento, com a empresa de cada colaborador; página de impressão aberta",
        "Backup fora da plataforma: os endereços antigos de backup e restauração respondem 404 (serviço privado mentoria-backup)",
        "[--escrita] Ciclo completo de ticket (abrir e responder) e 1h de voluntariado (apagados no fim)",
    ]

    def testes_especificos(self):
        self.etapa("Cadastros & Usuários", "Tabela e busca", self.verificar_cadastros)
        self.etapa("Painel Geral", "KPIs no escopo do perfil", self.verificar_kpis_equipe)
        self.etapa("Voluntariado ESG", "Relógio visível", lambda: self.verificar_relogio_voluntariado(deve_existir=True))
        self.etapa("Exportar ESG (CSV)", "Conteúdo do relatório", self.verificar_relatorio_esg)
        self.etapa("Portal de Demandas", "Permissões no portal", lambda: self.verificar_portal_demandas(eh_gestor=True))
        if self.escrita:
            def ciclo_ticket():
                titulo = self.abrir_ticket_demanda()
                self.responder_ticket_demanda(titulo)
            self.etapa("Portal de Demandas", "Ciclo completo de ticket (escrita)", ciclo_ticket)
        self.etapa("Backup fora da plataforma", "Endereços antigos respondem 404", self.verificar_backup_fora_da_plataforma)

    def verificar_backup_fora_da_plataforma(self):
        """Backup e restauração saíram da plataforma pública: nem o Administrador acha esses endereços (404)."""
        for metodo, caminho in (("GET", "/admin/banco"), ("POST", "/admin/banco"), ("GET", "/admin/banco/arquivo?f=manuais/x.db"),
                                ("GET", "/admin/banco/relatorio/execucoes.csv"), ("POST", "/admin/ambiente/backups-padrao")):
            resposta = (self.context.request.get if metodo == "GET" else self.context.request.post)(BASE_URL + caminho, max_redirects=0)
            if resposta.status == 404:
                self.registrar("Backup fora da plataforma", f"{metodo} {caminho}", APROVADO, "404: a operação não existe aqui.", evidencia=False)
            else:
                self.registrar("Backup fora da plataforma", f"{metodo} {caminho}", FALHA,
                               f"HTTP {resposta.status}: a plataforma pública ainda responde um endereço de backup.", arquivos="app.py")



if __name__ == "__main__":
    executar_cli(AgenteAdministrador)
