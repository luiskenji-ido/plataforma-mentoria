"""
AGENTE OMNITEST — PERFIL AVALIADOR BANCA (executivo convidado para as bancas de TCC)
Uso: python agentes_omnitest/agente_avaliador.py [--pausar] [--headless] [--lento 0] [--escrita]

Este agente testa SOMENTE o perfil Avaliador Banca. Para rodar todos os perfis use executar_todos.py.
Antes de começar ele garante a massa de dados [OmniTest] (massa_dados.py): uma banca em andamento
em que este avaliador está escalado e uma banca já realizada com resultado publicado.

Foco de especialista: o avaliador externo só enxerga as bancas em que foi escalado (LGPD),
registra as horas de leitura ligadas ao TCC e lança notas com as regras oficiais.
"""
import re

from nucleo import AgenteOmniTest, executar_cli, consultar_banco, BASE_URL, APROVADO, FALHA, ALERTA, PULADO
from massa_dados import garantir_massa, PROJETO_ABERTO, PROJETO_CONCLUIDO


class AgenteAvaliador(AgenteOmniTest):
    chave_perfil = "avaliador"
    exige_frequencia = False
    exige_onboarding = True
    PAGINA_INICIAL = "/minhas-bancas"
    CHAVES_MENU_IDIOMA = ("menu_minhas_bancas", "menu_biblioteca")

    # O /dashboard só redireciona para Minhas bancas (não é bloqueio nem página própria), por isso fica fora da matriz
    ROTAS_PERMITIDAS = ["minhas_bancas", "banca", "biblioteca", "demandas", "certificados", "repositorio"]
    ROTAS_BLOQUEADAS = ["sessoes", "acompanhamento", "projetos", "hub_educacional", "frequencia", "notas", "usuarios", "grupos",
                        "solicitacoes", "banco", "esg_csv", "esg_pdf", "atividades_extras", "reunioes", "agenda_bancas",
                        "avaliadores_banca", "indicadores"]
    MENU_VISIVEL = ["minhas_bancas", "biblioteca", "demandas", "certificados"]
    MENU_OCULTO = ["sessoes", "acompanhamento", "projetos", "hub_educacional", "frequencia", "notas", "usuarios",
                   "atividades_extras", "reunioes", "agenda_bancas", "avaliadores_banca", "indicadores", "banco"]

    ROTEIRO = [
        "Massa de dados [OmniTest]: banca em andamento (daqui a 1 hora) e banca realizada com resultado publicado",
        "Login cai em Minhas bancas; páginas internas da equipe redirecionam com aviso",
        "Minhas bancas: banca escalada com data, local e prazos; download do escrito final do grupo",
        "Isolamento: Sala da Banca e arquivos de TCCs em que NÃO está escalado ficam bloqueados",
        "Sala da Banca: formulário de notas e telão do cronômetro",
        "Certificado de avaliador com horas e código; verificação pública do código",
        "[--escrita] Relógio de leitura ligado ao TCC (iniciar e encerrar) e regras das notas (< 7 exige justificativa)",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._massa_ok = False

    # --------------------------------------------------------------------------
    # Massa de dados e projeto usado na rota da Sala da Banca
    # --------------------------------------------------------------------------
    def testes_pre_login(self):
        try:
            resumo = garantir_massa()
            self._massa_ok = True
            self.registrar("Massa de dados", "Cenário [OmniTest] da banca", APROVADO, resumo, evidencia=False)
        except Exception as e:
            self.registrar("Massa de dados", "Cenário [OmniTest] da banca", FALHA, f"Não foi possível criar: {e}", evidencia=False,
                           arquivos="agentes_omnitest/massa_dados.py, models.py (Banca, EntregaTCC, AvaliacaoBanca)")
        super().testes_pre_login()

    def dados_da_massa(self):
        from models import Projeto, Usuario, EntregaTCC, Banca

        def consulta():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            aberto = Projeto.query.filter_by(nome=PROJETO_ABERTO).first()
            concluido = Projeto.query.filter_by(nome=PROJETO_CONCLUIDO).first()
            alheio = next((b.projeto_id for b in Banca.query.all() if eu not in b.avaliadores), None)
            if alheio is None:
                meus = {b.projeto_id for b in Banca.query.all() if eu in b.avaliadores}
                alheio = next((p.id for p in Projeto.query.all() if p.id not in meus), None)
            entrega_alheia = next((e.id for e in EntregaTCC.query.all()
                                   if not (e.projeto and e.projeto.banca and eu in e.projeto.banca.avaliadores)
                                   and not (e.projeto and e.projeto.grupo and eu in e.projeto.grupo.membros)), None)
            return {
                "eu": eu.id if eu else None,
                "aberto": aberto.id if aberto else None,
                "banca_aberta": aberto.banca.id if aberto and aberto.banca else None,
                "concluido": concluido.id if concluido else None,
                "projeto_alheio": alheio,
                "entrega_alheia": entrega_alheia,
            }
        return consultar_banco(consulta)

    def projeto_da_banca(self):
        return self.dados_da_massa()["aberto"]

    # --------------------------------------------------------------------------
    # Testes do perfil
    # --------------------------------------------------------------------------
    def testes_especificos(self):
        if not self._massa_ok and not self.dados_da_massa()["aberto"]:
            self.registrar("Minhas bancas", "Testes do avaliador", PULADO, "Sem a massa de dados [OmniTest] no banco.", evidencia=False)
            return
        self.etapa("Minhas bancas", "Banca escalada visível", self.verificar_minhas_bancas)
        self.etapa("Minhas bancas", "Download do escrito final", self.verificar_download_escrito)
        self.etapa("Sala da Banca", "Isolamento entre bancas", self.verificar_isolamento_bancas)
        self.etapa("Sala da Banca", "Formulário de notas e telão", self.verificar_sala_da_banca)
        self.etapa("Certificados", "Certificado de avaliador", self.verificar_certificado)
        if self.escrita:
            self.etapa("Minhas bancas", "Relógio de leitura (escrita)", self.verificar_relogio_leitura)
            self.etapa("Sala da Banca", "Regras das notas (escrita)", self.verificar_regras_das_notas)

    def verificar_minhas_bancas(self):
        self.visitar("/minhas-bancas")
        texto = self.texto_pagina()
        faltando = [n for n in (PROJETO_ABERTO, "Auditório Aon (teste)") if n not in texto]
        if faltando:
            self.registrar("Minhas bancas", "Banca escalada visível", FALHA, "Não aparece: " + ", ".join(faltando),
                           esperado="A banca em que o avaliador está escalado, com data, local e prazos",
                           arquivos="app.py (minhas_bancas, bancas_do_avaliador), templates/minhas_bancas.html")
        else:
            self.registrar("Minhas bancas", "Banca escalada visível", APROVADO, f"'{PROJETO_ABERTO}' listada com o local.", evidencia=False)

    def verificar_download_escrito(self):
        self.visitar("/minhas-bancas")
        links = self.page.eval_on_selector_all('a[href^="/entregas/"]', "els => els.map(e => e.getAttribute('href'))")
        if not links:
            self.registrar("Minhas bancas", "Download do escrito final", FALHA, "Nenhum link de entrega na página.",
                           esperado="Botão do escrito final do grupo para leitura")
            return
        resposta = self.context.request.get(BASE_URL + links[0], max_redirects=0)
        tipo = resposta.headers.get("content-type", "")
        if resposta.status == 200 and "pdf" in tipo:
            self.registrar("Minhas bancas", "Download do escrito final", APROVADO, f"PDF entregue ({len(resposta.body())} bytes).", evidencia=False)
        else:
            self.registrar("Minhas bancas", "Download do escrito final", FALHA, f"HTTP {resposta.status} ({tipo}).",
                           arquivos="app.py (baixar_entrega_tcc, pode_baixar_entrega)")

    def verificar_isolamento_bancas(self):
        dados = self.dados_da_massa()
        if dados["projeto_alheio"]:
            _, bloqueado = self.visitar(f"/projetos/banca/{dados['projeto_alheio']}")
            if bloqueado:
                self.registrar("Sala da Banca", "Banca de outro TCC bloqueada", APROVADO, f"Redirecionado para {self.caminho_atual()}.", evidencia=False)
            else:
                self.registrar("Sala da Banca", "Banca de outro TCC bloqueada", FALHA,
                               "🔓 FALHA DE SEGURANÇA: abriu a Sala da Banca de um TCC em que não está escalado.",
                               arquivos="app.py (painel_banca, eh_avaliador_da_banca)")
        else:
            self.registrar("Sala da Banca", "Banca de outro TCC bloqueada", PULADO, "Não há outro projeto no banco.", evidencia=False)

        if dados["entrega_alheia"]:
            resposta = self.context.request.get(BASE_URL + f"/entregas/{dados['entrega_alheia']}/arquivo", max_redirects=0)
            if resposta.status == 200 and "text/html" not in resposta.headers.get("content-type", ""):
                self.registrar("Sala da Banca", "Arquivo de outro TCC bloqueado", FALHA,
                               "🔓 FALHA DE SEGURANÇA: baixou o arquivo de um TCC em que não está escalado.",
                               arquivos="app.py (baixar_entrega_tcc, pode_baixar_entrega)")
            else:
                self.registrar("Sala da Banca", "Arquivo de outro TCC bloqueado", APROVADO, f"HTTP {resposta.status}.", evidencia=False)
        else:
            self.registrar("Sala da Banca", "Arquivo de outro TCC bloqueado", PULADO, "Não há entregas de outros TCCs no banco.", evidencia=False)

    def verificar_sala_da_banca(self):
        dados = self.dados_da_massa()
        self.visitar(f"/projetos/banca/{dados['aberto']}")
        faltando = [nome for nome, seletor in (("nota do escrito", "#notaEscrita"), ("nota da apresentação", "#notaApresentacao"),
                                               ("nota do visual", "#notaVisual"), ("feedback aos jovens", "#feedbackJovens"))
                    if not self.visivel(seletor)]
        if faltando:
            self.registrar("Sala da Banca", "Formulário de notas", FALHA, "Campos ausentes: " + ", ".join(faltando),
                           arquivos="templates/banca_avaliacao.html")
        else:
            self.registrar("Sala da Banca", "Formulário de notas", APROVADO, "Etapas escrita e oral com os campos oficiais.", evidencia=False)
        if self.page.locator('a:has-text("Notas da equipe"), a[href*="/admin/notas"]').count():
            self.registrar("Sala da Banca", "Sem áreas da gestão", ALERTA, "A sala mostra links da gestão para o avaliador externo.")

        resposta = self.context.request.get(BASE_URL + f"/bancas/{dados['banca_aberta']}/telao", max_redirects=0)
        if resposta.status == 200 and PROJETO_ABERTO in resposta.text():
            self.registrar("Sala da Banca", "Telão do cronômetro", APROVADO, "Telão abre com o nome do TCC.", evidencia=False)
        else:
            self.registrar("Sala da Banca", "Telão do cronômetro", FALHA, f"HTTP {resposta.status}.",
                           arquivos="app.py (telao_banca), templates/banca_telao.html")

    def verificar_certificado(self):
        self.visitar("/certificados")
        if PROJETO_CONCLUIDO not in self.texto_pagina():
            self.registrar("Certificados", "Certificado de avaliador", FALHA, f"'{PROJETO_CONCLUIDO}' não aparece em Meus certificados.",
                           esperado="Certificado da banca realizada e publicada em que avaliou",
                           arquivos="app.py (certificados_disponiveis, tipo_certificado), templates/meus_certificados.html")
            return
        link = self.page.locator('a[href^="/certificado/"]').first.get_attribute("href")
        self.visitar(link)
        texto = self.texto_pagina()
        codigo = re.search(r"verificação\s+([0-9A-F]{10})", texto)
        problemas = []
        if "avaliador" not in texto.lower():
            problemas.append("texto não cita a atuação como avaliador")
        if not re.search(r"\d+ h", texto):
            problemas.append("sem as horas dedicadas")
        if not codigo:
            problemas.append("sem código de verificação")
        if problemas:
            self.registrar("Certificados", "Certificado de avaliador", FALHA, "; ".join(problemas),
                           arquivos="app.py (emitir_certificado, minutos_certificado), templates/certificado.html")
            return
        self.registrar("Certificados", "Certificado de avaliador", APROVADO, f"Código {codigo.group(1)} com horas registradas.", evidencia=False)

        publico = self.context.browser.new_context()
        try:
            resposta = publico.request.get(BASE_URL + f"/certificado/verificar/{codigo.group(1)}")
            corpo = resposta.text()
            if resposta.status == 200 and PROJETO_CONCLUIDO in corpo and self.perfil["email"] not in corpo:
                self.registrar("Certificados", "Verificação pública do código", APROVADO, "Válido sem login e sem expor e-mail.", evidencia=False)
            else:
                self.registrar("Certificados", "Verificação pública do código", FALHA, f"HTTP {resposta.status}; dados do certificado não conferem.",
                               arquivos="app.py (verificar_certificado), templates/certificado_verificar.html")
        finally:
            publico.close()

    def verificar_relogio_leitura(self):
        from models import CheckinVoluntariado
        dados = self.dados_da_massa()

        def registro_aberto():
            r = CheckinVoluntariado.query.filter_by(usuario_id=dados["eu"], data_hora_fim=None).first()
            return (r.projeto_id, r.tipo_atividade) if r else None

        if consultar_banco(registro_aberto):
            self.registrar("Minhas bancas", "Relógio de leitura", PULADO, "Já havia um relógio aberto para este utilizador.", evidencia=False)
            return
        self.visitar("/minhas-bancas")
        self.page.locator(f'form[action="/bancas/{dados["banca_aberta"]}/relogio/iniciar_leitura"] button').click()
        self.page.wait_for_load_state("domcontentloaded")
        aberto = consultar_banco(registro_aberto)
        if aberto != (dados["aberto"], "Leitura Assíncrona de TCC"):
            self.registrar("Minhas bancas", "Relógio de leitura", FALHA, f"Registro aberto: {aberto}.",
                           esperado="Check-in de leitura ligado ao TCC da banca", arquivos="app.py (relogio_banca, ACOES_RELOGIO_BANCA)")
            return
        self.page.locator('form[action$="/relogio/encerrar"] button').first.click()
        self.page.wait_for_load_state("domcontentloaded")
        if consultar_banco(registro_aberto):
            self.registrar("Minhas bancas", "Relógio de leitura", FALHA, "O botão de encerrar não fechou o relógio.",
                           arquivos="app.py (relogio_banca), templates/minhas_bancas.html")
        else:
            self.registrar("Minhas bancas", "Relógio de leitura", APROVADO, "Leitura iniciada e encerrada, ligada ao TCC.", evidencia=False)

    def verificar_regras_das_notas(self):
        from models import AvaliacaoBanca
        dados = self.dados_da_massa()

        def minha_avaliacao():
            a = AvaliacaoBanca.query.filter_by(projeto_id=dados["aberto"], avaliador_id=dados["eu"]).first()
            return (a.nota_escrita, a.nota_apresentacao) if a else (None, None)

        def enviar_escrita(nota, justificativa):
            self.visitar(f"/projetos/banca/{dados['aberto']}")
            self.page.fill("#notaEscrita", nota)
            self.page.fill("#justEscrita", justificativa)
            self.page.locator('form:has(input[value="etapa_escrita"]) button[type="submit"]').click()
            self.page.wait_for_load_state("domcontentloaded")

        enviar_escrita("6", "")
        if consultar_banco(minha_avaliacao)[0] is not None:
            self.registrar("Sala da Banca", "Nota < 7 sem justificativa recusada", FALHA, "A nota 6 foi gravada sem justificativa.",
                           arquivos="app.py (registrar_etapa_avaliacao)")
        else:
            self.registrar("Sala da Banca", "Nota < 7 sem justificativa recusada", APROVADO, evidencia=False)

        enviar_escrita("8.5", "")
        if consultar_banco(minha_avaliacao)[0] == 8.5:
            self.registrar("Sala da Banca", "Nota do escrito gravada", APROVADO, "8,5 gravado na avaliação deste avaliador.", evidencia=False)
        else:
            self.registrar("Sala da Banca", "Nota do escrito gravada", FALHA, f"Valor no banco: {consultar_banco(minha_avaliacao)[0]}.",
                           arquivos="app.py (painel_banca, registrar_etapa_avaliacao)")

        # Etapa oral: só a recusa é testada; gravá-la encerraria a banca da massa (único avaliador escalado)
        self.visitar(f"/projetos/banca/{dados['aberto']}")
        self.page.fill("#notaApresentacao", "5")
        self.page.fill("#notaVisual", "9")
        self.page.locator('form:has(input[value="etapa_oral"]) button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        if consultar_banco(minha_avaliacao)[1] is not None:
            self.registrar("Sala da Banca", "Nota oral < 7 sem justificativa recusada", FALHA, "A nota 5 foi gravada sem justificativa.",
                           arquivos="app.py (registrar_etapa_avaliacao)")
        else:
            self.registrar("Sala da Banca", "Nota oral < 7 sem justificativa recusada", APROVADO, evidencia=False)

    # --------------------------------------------------------------------------
    # Tour: o avaliador não tem Painel Geral (o login leva a Minhas bancas)
    # --------------------------------------------------------------------------
    def teste_tour(self):
        self.tratar_tour = False
        try:
            self.etapa("Tour", "Botão de tour em cada página", self.tour_botao_manual)
        finally:
            self.tratar_tour = True
        self.registrar("Tour", "Convite do primeiro acesso", PULADO,
                       "O convite do tour fica no Painel Geral, que este perfil não usa.", evidencia=False)


if __name__ == "__main__":
    executar_cli(AgenteAvaliador)
