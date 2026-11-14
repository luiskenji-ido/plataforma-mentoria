"""
AGENTE OMNITEST — PERFIL ADMINISTRADOR
Uso: python agentes_omnitest/agente_administrador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Administrador. Para rodar todos os perfis use executar_todos.py.
Atenção: o agente apenas ABRE a Manutenção (DB); nunca clica em restaurar/limpar.
"""
from nucleo import AgenteOmniTest, executar_cli


class AgenteAdministrador(AgenteOmniTest):
    chave_perfil = "administrador"
    exige_frequencia = False
    exige_onboarding = True
    ESCOPO_ALUNOS = "todos"

    # Regra 2: o Administrador acede ao Portal de Demandas, à Biblioteca e gere utilizadores
    ROTAS_PERMITIDAS = ["dashboard", "sessoes", "acompanhamento", "projetos", "biblioteca", "hub_educacional",
                        "frequencia", "notas", "usuarios", "grupos", "demandas", "banco", "banca", "esg_csv", "esg_pdf"]
    ROTAS_BLOQUEADAS = ["solicitacoes"]
    MENU_VISIVEL = ["dashboard", "hub_educacional", "sessoes", "acompanhamento", "projetos", "frequencia", "notas",
                    "usuarios", "demandas", "biblioteca", "banco"]
    MENU_OCULTO = ["solicitacoes"]

    ROTEIRO = [
        "Cadastros & Usuários: tabela carregada e busca pelo e-mail do próprio utilizador de teste (Regra 2)",
        "Painel Geral: KPIs recalculados com todos os alunos da plataforma",
        "Relógio de Voluntariado visível e modal de lançamento manual",
        "Portal de Demandas: abrir ticket e responder oficialmente como gestor",
        "Relatório ESG (CSV): uma linha por lançamento, com a empresa de cada colaborador; página de impressão aberta",
        "Manutenção (DB): só abre a página; nunca clica em restaurar ou limpar",
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


if __name__ == "__main__":
    executar_cli(AgenteAdministrador)
