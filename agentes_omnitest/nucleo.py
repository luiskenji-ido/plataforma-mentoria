"""
NÚCLEO COMPARTILHADO DOS AGENTES OMNITEST
==========================================
Cada perfil da plataforma tem o seu próprio agente (agente_<perfil>.py).
Este ficheiro concentra o que é comum a todos eles:

  - Preparação do utilizador de teste no banco (senha, perguntas de segurança, desbloqueio)
  - Login, onboarding LGPD, registo de frequência e tour inicial
  - Catálogo de rotas da plataforma
  - Verificações de saúde de página (erro 500, chaves de tradução cruas, erros JS)
  - Matriz de acesso (o que o perfil DEVE abrir e o que DEVE ser bloqueado)
  - Relatório em Markdown + JSON com evidências (screenshots)
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime, date
from urllib.parse import urlparse

# O agente vive em agentes_omnitest/, mas o app Flask está na raiz do projeto
RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)
os.chdir(RAIZ_PROJETO)

# O terminal do Windows usa cp1252 por padrão e quebraria nos emojis do relatório
for _fluxo in (sys.stdout, sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000")
SENHA_PADRAO = "#Test-p0nt4-pOnt@"
PASTA_RELATORIOS = os.path.join(RAIZ_PROJETO, "Agent Reports", "OmniTest")

# Respostas das perguntas de segurança dos utilizadores de teste (o app guarda em minúsculas)
RESPOSTA_SEGURANCA = "teste"
PERGUNTAS_TESTE = (
    "Qual era o nome do seu primeiro animal de estimação?",
    "Qual é a sua cor favorita?",
    "Em qual cidade você nasceu?",
)

TEMAS = ["claro", "escuro", "futurista", "vintage"]
TEMAS_ESCUROS = ["escuro", "futurista"]
IDIOMAS = {"en": "English", "es": "Español"}

APROVADO = "✅ Aprovado"
FALHA = "❌ Falha"
ALERTA = "⚠️ Alerta"
PULADO = "⏭️ Pulado"

# ==============================================================================
# CADASTRO DOS PERFIS DE TESTE
# ==============================================================================
PERFIS = {
    "administrador": {"nome": "Admin OmniTest", "email": "administrador_ominitest@local.com", "tipo": "Administrador"},
    "aluno": {"nome": "Aluno OmniTest", "email": "aluno_ominitest@local.com", "tipo": "Aluno"},
    "professor": {"nome": "Professor OmniTest", "email": "professor_ominitest@local.com", "tipo": "Professor"},
    "mentor": {"nome": "Mentor OmniTest", "email": "mentor_ominitest@local.com", "tipo": "Mentor"},
    "mentor_administrador": {"nome": "Mentor Admin OmniTest", "email": "mentoradministrador_ominitest@local.com", "tipo": "Mentor Administrador"},
    "gestor_b2b": {"nome": "Gestor B2B OmniTest", "email": "gestorparceirob2b@local.com", "tipo": "Admin B2B"},
}

# ==============================================================================
# CATÁLOGO DE ROTAS (apenas GET) - espelha o app.py
# "download": a rota devolve um ficheiro (CSV/PDF) em vez de uma página
# ==============================================================================
ROTAS = {
    "dashboard": {"caminho": "/dashboard", "nome": "Painel Geral"},
    "sessoes": {"caminho": "/sessoes", "nome": "Sessões"},
    "acompanhamento": {"caminho": "/acompanhamento", "nome": "Acompanhamento"},
    "projetos": {"caminho": "/projetos", "nome": "Projetos"},
    "biblioteca": {"caminho": "/biblioteca", "nome": "Biblioteca de Projetos"},
    "hub_educacional": {"caminho": "/admin/turmas", "nome": "Hub Educacional"},
    "frequencia": {"caminho": "/admin/frequencia", "nome": "Diário › Frequência"},
    "notas": {"caminho": "/admin/notas", "nome": "Diário › Gestão de Notas"},
    "usuarios": {"caminho": "/admin/usuarios", "nome": "Cadastros & Usuários"},
    "grupos": {"caminho": "/admin/grupos", "nome": "Grupos"},
    "demandas": {"caminho": "/demandas", "nome": "Portal de Demandas"},
    "solicitacoes": {"caminho": "/admin/solicitacoes", "nome": "Solicitações de Mentoria"},
    "banco": {"caminho": "/admin/banco", "nome": "Manutenção (DB)"},
    "banca": {"caminho": "/projetos/banca/{projeto_id}", "nome": "Sala da Banca"},
    "atividades_extras": {"caminho": "/atividades-extras", "nome": "Atividades extras"},
    "reunioes": {"caminho": "/reunioes", "nome": "Reuniões ITM × Aon"},
    "agenda_bancas": {"caminho": "/bancas", "nome": "Agenda de bancas"},
    "avaliadores_banca": {"caminho": "/bancas/avaliadores", "nome": "Avaliadores da banca"},
    "minhas_bancas": {"caminho": "/minhas-bancas", "nome": "Minhas bancas"},
    "indicadores": {"caminho": "/indicadores-voluntariado", "nome": "Indicadores de voluntariado"},
    "certificados": {"caminho": "/certificados", "nome": "Certificados"},
    # Vitrine pública dos TCCs autorizados: página própria, sem login nem menu
    "repositorio": {"caminho": "/repositorio", "nome": "Repositório público", "independente": True},
    "esg_csv": {"caminho": "/admin/exportar-relatorio-esg", "nome": "Exportar ESG (CSV)", "download": True},
    # O "PDF" é uma página HTML pronta para imprimir (render_template_string), não um ficheiro
    # "independente": não estende base.html (sem menu, tema, idioma nem tour), por isso fica fora dessas varreduras
    "esg_pdf": {"caminho": "/admin/exportar-relatorio-esg-pdf", "nome": "Exportar ESG (PDF/Impressão)", "independente": True},
}

# Onde o Gemini deve procurar a causa de cada módulo (vai no prompt de correção)
ARQUIVOS_POR_MODULO = {
    "Painel Geral": "app.py (rota dashboard), templates/dashboard.html",
    "Sessões": "app.py (rota sessoes), templates/sessoes.html",
    "Acompanhamento": "app.py (rotas acompanhamento, conectar_agenda, oauth2callback, chat_ia), templates/acompanhamento.html",
    "Projetos": "app.py (rota projetos), templates/projetos.html",
    "Biblioteca de Projetos": "app.py (biblioteca_tccs, baixar_acervo, dados_acervo_do_formulario), templates/biblioteca.html",
    "Hub Educacional": "app.py (rota gerenciar_turmas), templates/admin_turmas.html",
    "Diário › Frequência": "app.py (rota gerenciar_frequencia), templates/admin_frequencia.html",
    "Diário › Gestão de Notas": "app.py (rota gerenciar_notas), templates/admin_notas.html",
    "Cadastros & Usuários": "app.py (rota gerenciar_usuarios), templates/admin_usuarios.html",
    "Grupos": "app.py (rota gerenciar_grupos), templates/admin_grupos.html",
    "Portal de Demandas": "app.py (rota portal_demandas), templates/demandas.html",
    "Solicitações de Mentoria": "app.py (rota gerenciar_solicitacoes), templates/admin_solicitacoes.html",
    "Manutenção (DB)": "app.py (rota manutencao_banco), templates/admin_banco.html",
    "Recuperação de Senha": "app.py (rotas recuperar_senha e trocar_senha_obrigatoria), templates/index.html, templates/perguntas_seguranca.html, templates/trocar_senha.html",
    "Autenticação": "app.py (rotas login e logout), templates/index.html",
    "Regras de Entrada": "app.py (verificar_onboarding, verificar_frequencia_diaria, registrar_frequencia), templates/base.html, templates/onboarding.html",
    "Menu Superior": "templates/base.html (navbar #menuPrincipal)",
    "Voluntariado ESG": "app.py (bater_ponto_voluntariado, lancamento_manual_voluntariado, validar_vinculos_voluntariado), templates/dashboard.html",
    "Atividades extras": "app.py (atividades_extras, nova_atividade_extra, acao_atividade_extra, fechar_presenca), templates/atividades_extras.html",
    "Agenda de bancas": "app.py (agenda_bancas, publicar_resultado_banca), templates/agenda_bancas.html",
    "Avaliadores da banca": "app.py (avaliadores_banca, curriculo_avaliador), templates/avaliadores_banca.html",
    "Minhas bancas": "app.py (minhas_bancas, relogio_banca), templates/minhas_bancas.html",
    "Indicadores de voluntariado": "app.py (indicadores_voluntariado, calcular_indicadores, registros_indicadores), templates/indicadores_voluntariado.html",
    "Certificados": "app.py (meus_certificados, emitir_certificado, registrar_certificado, verificar_certificado), templates/meus_certificados.html, certificado.html",
    "Repositório público": "app.py (repositorio_publico, baixar_repositorio_publico, aprovar_versao_final), templates/repositorio_publico.html",
    "Sala da Banca": "app.py (painel_banca, consolidar_banca, perguntas_banca, cronometro_banca), templates/banca_avaliacao.html, templates/banca_telao.html",
    "Reuniões ITM × Aon": "app.py (reunioes, editar_reuniao, detalhe_reuniao, sincronizar_voluntariado_reuniao), templates/reunioes.html, reuniao_form.html, reuniao_detalhe.html",
    "Tour": "templates/dashboard.html (modalTourInicial, iniciarTourDaPagina, desativarTourBackend), app.py (rota desativar_tour), "
            "templates/base.html (botão de tour manual) e a função iniciarTourDaPagina do template de cada página",
    "Tema": "templates/base.html (CSS por html[data-theme]) e o template da página citada",
    "Idioma": "traducoes.py (dicionário TEXTOS pt/en/es), templates/base.html (menu e textos comuns a todas as páginas) e o template da página citada",
}

MARCAS_BLOQUEIO = ["acesso negado", "acesso restrito"]
MARCAS_ERRO_SERVIDOR = ["Internal Server Error", "Traceback (most recent call last)", "jinja2.exceptions", "werkzeug.exceptions"]


def _celula(texto):
    """Deixa o texto seguro para uma célula de tabela Markdown (uma linha, sem pipes)."""
    texto = str(texto or "").strip().splitlines()[0] if str(texto or "").strip() else ""
    return texto.replace("|", "\\|")[:220]


# ==============================================================================
# PREPARAÇÃO DO BANCO (FIXTURE)
# ==============================================================================
def preparar_usuario(chave_perfil, primeiro_acesso=False):
    """
    Garante que o utilizador de teste consegue entrar na plataforma:
      - existe, está Ativo e com o tipo correto
      - senha em bcrypt (o login usa Flask-Bcrypt, não o werkzeug)
      - sem troca de senha obrigatória e com as 3 perguntas de segurança cadastradas
      - com primeiro_acesso=True, apaga o termo assinado e a frequência de hoje para
        repetir o fluxo de primeira entrada (onboarding + presença)
    Devolve uma lista de observações para o relatório.
    """
    from app import app, db, bcrypt
    from models import Usuario, SegurancaUsuario, Frequencia, TermoAceite

    dados = PERFIS[chave_perfil]
    notas = []
    with app.app_context():
        user = Usuario.query.filter_by(email=dados["email"]).first()
        if not user:
            user = Usuario(
                nome=dados["nome"],
                email=dados["email"],
                senha=bcrypt.generate_password_hash(SENHA_PADRAO).decode("utf-8"),
                tipo_usuario=dados["tipo"],
                criado_por="OmniTest",
            )
            db.session.add(user)
            db.session.flush()
            notas.append("Utilizador de teste criado.")
        else:
            try:
                senha_ok = bcrypt.check_password_hash(user.senha, SENHA_PADRAO)
            except ValueError:
                senha_ok = False
            if not senha_ok:
                user.senha = bcrypt.generate_password_hash(SENHA_PADRAO).decode("utf-8")
                notas.append("Senha do utilizador de teste redefinida para o padrão OmniTest.")

        if user.tipo_usuario != dados["tipo"]:
            notas.append(f"Tipo corrigido de '{user.tipo_usuario}' para '{dados['tipo']}'.")
            user.tipo_usuario = dados["tipo"]
        if user.status != "Ativo":
            notas.append(f"Conta estava '{user.status}' e foi reativada.")
            user.status = "Ativo"
        user.tentativas_login = 0
        user.forcar_troca_senha = False
        user.data_ultima_troca_senha = datetime.utcnow()

        # O app guarda as respostas em texto minúsculo (sem hash) e compara assim na recuperação
        seguranca = SegurancaUsuario.query.filter_by(usuario_id=user.id).first()
        if not seguranca:
            db.session.add(SegurancaUsuario(
                usuario_id=user.id,
                pergunta_1=PERGUNTAS_TESTE[0], resposta_1=RESPOSTA_SEGURANCA,
                pergunta_2=PERGUNTAS_TESTE[1], resposta_2=RESPOSTA_SEGURANCA,
                pergunta_3=PERGUNTAS_TESTE[2], resposta_3=RESPOSTA_SEGURANCA,
            ))
            notas.append("Perguntas de segurança de teste cadastradas.")
        elif {seguranca.resposta_1, seguranca.resposta_2, seguranca.resposta_3} != {RESPOSTA_SEGURANCA}:
            seguranca.resposta_1 = seguranca.resposta_2 = seguranca.resposta_3 = RESPOSTA_SEGURANCA
            if seguranca.pergunta_1.startswith("OmniTest"):
                seguranca.pergunta_1, seguranca.pergunta_2, seguranca.pergunta_3 = PERGUNTAS_TESTE
            notas.append(f"Respostas de segurança redefinidas para '{RESPOSTA_SEGURANCA}'.")

        if primeiro_acesso:
            from models import ConclusaoModuloTCC
            hoje = datetime.combine(datetime.utcnow().date(), datetime.min.time())
            TermoAceite.query.filter_by(usuario_id=user.id).delete()
            ConclusaoModuloTCC.query.filter_by(usuario_id=user.id).delete()
            Frequencia.query.filter(Frequencia.usuario_id == user.id, Frequencia.data_registro >= hoje).delete()
            user.exibir_tour = True
            notas.append("Modo primeiro acesso: termo, trilha do TCC, frequência de hoje e tour reiniciados.")

        db.session.commit()
    return notas


def consultar_banco(funcao):
    """Executa uma consulta ao banco dentro do contexto da aplicação."""
    from app import app
    with app.app_context():
        return funcao()


def limpar_dados_de_teste(chave_perfil):
    """Apaga o que o modo --escrita criou para este perfil (tudo marcado com [OmniTest]). Devolve o resumo."""
    from app import app, db
    from models import Usuario, DemandaInstitucional, CheckinVoluntariado

    with app.app_context():
        user = Usuario.query.filter_by(email=PERFIS[chave_perfil]["email"]).first()
        if not user:
            return "nada a limpar"
        tickets = DemandaInstitucional.query.filter(DemandaInstitucional.autor_id == user.id,
                                                    DemandaInstitucional.titulo.like("[OmniTest]%")).delete(synchronize_session=False)
        horas = CheckinVoluntariado.query.filter(CheckinVoluntariado.usuario_id == user.id,
                                                 CheckinVoluntariado.observacoes.like("[OmniTest]%")).delete(synchronize_session=False)
        # Avisos gerados pelos tickets de teste (no sino de quem os recebeu)
        from models import Notificacao
        Notificacao.query.filter(Notificacao.titulo.like("%[OmniTest]%")).delete(synchronize_session=False)
        db.session.commit()
        return f"{tickets} ticket(s) e {horas} lançamento(s) de voluntariado de teste apagados"


def cabecalho_prompt_gemini(titulo, quem, problemas, comando):
    """Instruções fixas do prompt de correção (usadas por cada agente e pelo consolidado do orquestrador)."""
    arquivos = sorted({a.strip() for r in problemas for a in re.split(r";|,(?![^()]*\))", r.get("arquivos", "")) if a.strip()})
    return [
        f"# 🤖 Prompt de Correção para o Gemini — {titulo}\n",
        f"> Gerado pelo OmniTest em {datetime.now().strftime('%d/%m/%Y às %H:%M')}. "
        "Copie tudo a partir da linha abaixo e cole no Gemini, anexando os arquivos citados.\n",
        "---\n",
        "Você é um engenheiro de software sênior especialista em Python, Flask, Flask-Login, SQLAlchemy, Jinja2 e Bootstrap 5.",
        "Trabalho numa plataforma de mentoria em Flask (app.py com todas as rotas, models.py, traducoes.py com o "
        "dicionário TEXTOS em pt/en/es usado via t('chave'), e templates/*.html que estendem base.html).",
        f"Um agente de testes de ponta a ponta (OmniTest, Playwright) navegou como {quem} "
        f"e encontrou os {len(problemas)} problemas abaixo.\n",
        "Para CADA problema:",
        "1. Explique a causa raiz em até 3 frases, citando arquivo e função/bloco.",
        "2. Entregue a correção como trechos completos ANTES → DEPOIS, prontos para colar.",
        "3. Não mude permissões de outros perfis (Administrador, Mentor Administrador, Mentor, Professor, Admin B2B, Aluno) além do necessário.",
        "4. Todo texto de interface novo ou corrigido vai para traducoes.py nos três idiomas (pt, en, es) e é usado com t('chave').",
        "5. Ajustes de tema usam seletores html[data-theme=\"claro|escuro|futurista|vintage\"], no mesmo padrão já usado em base.html.",
        "6. Mantenha o estilo do código e os comentários em português.",
        "7. Se faltar informação para corrigir com segurança, diga exatamente qual arquivo ou trecho precisa ver.\n",
        f"No fim, liste os testes manuais e lembre que a validação automática é: `{comando}`\n",
        f"**Arquivos envolvidos:** {'; '.join(arquivos) or 'app.py, templates/'}\n",
        "## Problemas encontrados\n",
    ]


# ==============================================================================
# AGENTE BASE
# ==============================================================================
class AgenteOmniTest:
    # --- Configuração que cada agente de perfil sobrescreve ---
    chave_perfil = ""
    ROTAS_PERMITIDAS = []
    ROTAS_BLOQUEADAS = []
    MENU_VISIVEL = []      # rotas que DEVEM aparecer no menu superior
    MENU_OCULTO = []       # rotas que NÃO podem aparecer no menu superior
    exige_frequencia = False   # Aluno, Mentor e Professor registam presença diária
    exige_onboarding = True    # Todos menos o Aluno assinam o termo LGPD/voluntariado
    TOUR_ESPERADO = None       # sequência de páginas do tour guiado, ex.: ["/dashboard", "/sessoes", ...]
    TESTAR_RECUPERACAO = True  # recuperação de senha antes do login (troca a senha e depois a restaura)

    def __init__(self, headless=False, lento=400, escrita=False, preparar=True, primeiro_acesso=False):
        self.perfil = PERFIS[self.chave_perfil]
        self.headless = headless
        self.lento = lento
        self.escrita = escrita
        self.preparar = preparar
        self.primeiro_acesso = primeiro_acesso
        self.resultados = []
        self.carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pasta_evidencias = os.path.join(PASTA_RELATORIOS, f"evidencias_{self.chave_perfil}_{self.carimbo}")
        self.modal_frequencia_visto = False
        self.onboarding_assinado = False
        self.trilha_lida_agora = False
        self._erros_js = []
        self._falhas_rede = []
        self._nomes_usuarios = None
        self._frequencia_tentada_no_onboarding = False
        self._dialogos = []
        self.tratar_tour = True   # o teste do Tour desliga o fechamento automático do convite
        self.pausar = False

    # --------------------------------------------------------------------------
    # Registo de resultados
    # --------------------------------------------------------------------------
    def registrar(self, modulo, acao, status, detalhe="", evidencia=True, esperado="", dica="", arquivos=""):
        """esperado/dica alimentam o prompt de correção para o Gemini."""
        arquivo = ""
        if evidencia and status in (FALHA, ALERTA) and getattr(self, "page", None):
            try:
                os.makedirs(self.pasta_evidencias, exist_ok=True)
                nome = re.sub(r"[^a-zA-Z0-9]+", "_", f"{modulo}_{acao}").strip("_")[:80]
                arquivo = os.path.join(self.pasta_evidencias, f"{len(self.resultados):02d}_{nome}.png")
                self.page.screenshot(path=arquivo, full_page=True)
            except Exception:
                arquivo = ""
        url = ""
        try:
            url = self.page.url if getattr(self, "page", None) else ""
        except Exception:
            pass
        self.resultados.append({"modulo": modulo, "acao": acao, "status": status, "detalhe": detalhe,
                                "evidencia": arquivo, "esperado": esperado, "dica": dica,
                                "arquivos": arquivos or ARQUIVOS_POR_MODULO.get(modulo, ""),
                                "url": url, "hora": datetime.now().strftime("%H:%M:%S"),
                                "erros_js": list(self._erros_js[:3]) if status in (FALHA, ALERTA) else []})
        print(f"   {status.split()[0]} [{modulo}] {acao}" + (f" — {_celula(detalhe)}" if detalhe else ""))

    def etapa(self, modulo, acao, funcao):
        """Executa um teste isolado: uma exceção vira ❌ no relatório sem parar o agente."""
        print(f"\n🔎 {modulo} › {acao}")
        self.anunciar(f"{modulo} › {acao}")
        try:
            funcao()
        except Exception as e:
            self.registrar(modulo, acao, FALHA, f"Exceção: {_celula(e)}")

    # --------------------------------------------------------------------------
    # Navegador
    # --------------------------------------------------------------------------
    def _ligar_sensores(self):
        def ao_console(msg):
            if msg.type == "error":
                self._erros_js.append(msg.text)

        def ao_responder(resp):
            if resp.status >= 400 and resp.url.startswith(BASE_URL) and "favicon" not in resp.url:
                self._falhas_rede.append(f"{resp.status} {urlparse(resp.url).path}")

        def ao_dialogo(dialogo):
            self._dialogos.append(dialogo.message)
            dialogo.accept()

        self.page.on("console", ao_console)
        self.page.on("pageerror", lambda erro: self._erros_js.append(str(erro)))
        self.page.on("response", ao_responder)
        self.page.on("dialog", ao_dialogo)
        self._navegacoes = []
        self.page.on("request", lambda r: r.is_navigation_request() and self._navegacoes.append(r.url))

    # Faixa no canto da tela com a regra em teste. Fica num Shadow DOM, por isso
    # não aparece no texto da página e não interfere nas verificações de tema e idioma.
    JS_FAIXA = r"""(() => {
        const desenhar = () => {
            let texto = null;
            try { texto = sessionStorage.getItem('omnitest_etapa'); } catch (e) {}
            if (!texto || !document.documentElement) return;
            let host = document.getElementById('omnitest-faixa');
            if (!host) {
                host = document.createElement('div');
                host.id = 'omnitest-faixa';
                host.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:2147483647;pointer-events:none';
                host.attachShadow({ mode: 'open' });
                document.documentElement.appendChild(host);
            }
            const caixa = document.createElement('div');
            caixa.style.cssText = 'font:600 13px system-ui,sans-serif;background:#111827;color:#fff;padding:8px 14px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.35);max-width:560px';
            caixa.textContent = '🤖 OmniTest · ' + texto;
            host.shadowRoot.replaceChildren(caixa);
        };
        window.__omnitestDesenhar = desenhar;
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', desenhar); else desenhar();
    })();"""

    def anunciar(self, texto):
        if self.headless or not getattr(self, "page", None):
            return
        try:
            self.page.evaluate("""(t) => { try { sessionStorage.setItem('omnitest_etapa', t); } catch (e) {}
                                           if (window.__omnitestDesenhar) window.__omnitestDesenhar(); }""",
                               f"{self.perfil['tipo']} — {texto}")
        except Exception:
            pass

    def caminho_atual(self):
        return urlparse(self.page.url).path.rstrip("/") or "/"

    def texto_pagina(self):
        try:
            return self.page.inner_text("body")
        except Exception:
            return ""

    def aguardar(self):
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

    def visivel(self, seletor, timeout=1500):
        # Os modais de frequência e tour só existem no HTML quando o Jinja os renderiza
        if self.page.locator(seletor).count() == 0 and not seletor.startswith("text="):
            return False
        try:
            self.page.locator(seletor).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # Regras de negócio que se colocam no caminho: onboarding, frequência e tour
    # --------------------------------------------------------------------------
    def lidar_com_bloqueios_de_fluxo(self):
        for _ in range(16):
            # A frequência vem primeiro: o modal também abre por cima da página de onboarding
            if self.visivel("#modalFrequenciaDiaria"):
                no_onboarding = self.caminho_atual() == "/onboarding"
                if no_onboarding and self._frequencia_tentada_no_onboarding:
                    # O before_request do onboarding barra o POST /registrar_frequencia,
                    # então o modal reaparece para sempre e o utilizador fica preso.
                    self.registrar("Regras de Entrada", "Frequência × Onboarding (primeiro acesso)", FALHA,
                                   "Modal de frequência abre sobre o /onboarding, mas /registrar_frequencia é "
                                   "redirecionado ao onboarding: o utilizador fica preso. Agente removeu o modal para prosseguir.")
                    self.page.evaluate("""() => {
                        document.querySelectorAll('#modalFrequenciaDiaria, .modal-backdrop').forEach(e => e.remove());
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                    }""")
                    continue
                self._frequencia_tentada_no_onboarding = no_onboarding
                self.modal_frequencia_visto = True
                self.page.locator('#modalFrequenciaDiaria button:has-text("Modalidade Online")').click()
                self.page.wait_for_load_state("domcontentloaded")
                self.aguardar()
                continue

            if self.caminho_atual() == "/onboarding":
                self.page.check("#checkAceite")
                self.page.locator("#btnAcessar").click()
                self.page.wait_for_load_state("domcontentloaded")
                self.aguardar()
                self.onboarding_assinado = True
                continue

            # Trilha obrigatória do TCC (Mentor, Professor, Mentor Administrador): lê módulo a módulo
            if self.caminho_atual() == "/onboarding/trilha-tcc":
                botao = self.page.locator('form[action*="/concluir"] button[type="submit"]').first
                if botao.count():
                    botao.click()
                    self.page.wait_for_load_state("domcontentloaded")
                    self.aguardar()
                    self.trilha_lida_agora = True
                    continue

            if self.tratar_tour and self.visivel("#modalTourInicial", timeout=800):
                self.page.locator('#modalTourInicial button:has-text("Não mostrar novamente")').click()
                self.page.wait_for_timeout(800)
                if self.visivel("#modalTourInicial", timeout=500):
                    self.page.keyboard.press("Escape")
                continue

            if self.tratar_tour and self.visivel(".introjs-overlay", timeout=300):
                self.page.keyboard.press("Escape")
                continue
            break

    # --------------------------------------------------------------------------
    # Visita a uma rota com verificações de saúde
    # --------------------------------------------------------------------------
    def resolver_caminho(self, chave):
        caminho = ROTAS[chave]["caminho"]
        if "{projeto_id}" in caminho:
            from models import Projeto
            projeto_id = consultar_banco(lambda: (Projeto.query.with_entities(Projeto.id).first() or [None])[0])
            if projeto_id is None:
                return None
            caminho = caminho.format(projeto_id=projeto_id)
        return caminho

    def visitar(self, caminho):
        """Abre a página e devolve (resposta_http, bloqueado)."""
        self._erros_js.clear()
        self._falhas_rede.clear()
        resposta = self.page.goto(BASE_URL + caminho, wait_until="domcontentloaded")
        self.aguardar()
        self.lidar_com_bloqueios_de_fluxo()
        destino = self.caminho_atual()
        redirecionado = destino != (caminho.split("?")[0].rstrip("/") or "/")
        negado_no_texto = any(m in self.texto_pagina().lower() for m in MARCAS_BLOQUEIO)
        return resposta, (redirecionado or negado_no_texto)

    def checar_saude(self, nome_pagina, resposta):
        """Erros de servidor, templates não renderizados, chaves de tradução e erros JS."""
        texto = self.texto_pagina()
        html = self.page.content()

        if (resposta and resposta.status >= 500) or any(m in html for m in MARCAS_ERRO_SERVIDOR):
            codigo = resposta.status if resposta else "?"
            self.registrar(nome_pagina, "Saúde do servidor", FALHA, f"Erro {codigo} ao renderizar a página.")
            return

        problemas = []
        if "{{" in texto or "{%" in texto:
            problemas.append("marcação Jinja visível ({{ ou {%)")
        # Nomes e logins como "aluno_ominitest" aparecem nas telas e não são chaves de tradução
        if self._nomes_usuarios is None:
            from models import Usuario
            self._nomes_usuarios = set(consultar_banco(lambda: [
                v for u in Usuario.query.all() for v in (u.nome, u.email.split("@")[0])]))
        ignorar = self._nomes_usuarios | set(re.findall(r"([\w.+-]+)@", html))
        chaves_cruas = {
            c for c in re.findall(r"(?<![\w@./-])[a-z]+(?:_[a-z0-9]+){1,}(?![\w@./-])", texto)
            if c not in ignorar
        }
        if chaves_cruas:
            problemas.append("chaves de tradução cruas: " + ", ".join(sorted(chaves_cruas)[:6]))
        if problemas:
            self.registrar(nome_pagina, "Tradução / Renderização", ALERTA, "; ".join(problemas))

        if self._erros_js:
            self.registrar(nome_pagina, "Erros de JavaScript", ALERTA, f"{len(self._erros_js)} erro(s): {self._erros_js[0]}")
        if self._falhas_rede:
            self.registrar(nome_pagina, "Recursos da página", ALERTA, ", ".join(sorted(set(self._falhas_rede))[:5]))

    # --------------------------------------------------------------------------
    # TESTES COMUNS A TODOS OS PERFIS
    # --------------------------------------------------------------------------
    def teste_login(self):
        self.page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        self.page.fill('input[name="email"]', self.perfil["email"])
        self.page.fill('input[name="senha"]', SENHA_PADRAO)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()

        destino = self.caminho_atual()
        if destino == "/trocar-senha":
            raise RuntimeError("Login parou na troca de senha obrigatória.")
        if destino == "/cadastrar-perguntas":
            raise RuntimeError("Login parou no cadastro de perguntas de segurança.")
        if destino == "/":
            alerta = self.page.locator(".alert").first
            msg = alerta.inner_text() if alerta.count() else "sem mensagem"
            raise RuntimeError(f"Login recusado: {msg}")

        self.lidar_com_bloqueios_de_fluxo()
        self.registrar("Autenticação", "Login com e-mail e senha", APROVADO, f"Redirecionado para {self.caminho_atual()}.", evidencia=False)

    def teste_regras_de_entrada(self):
        """Onboarding LGPD (todos menos Aluno) e frequência diária (Aluno, Mentor, Professor)."""
        from models import Usuario, Frequencia, TermoAceite

        def estado():
            user = Usuario.query.filter_by(email=self.perfil["email"]).first()
            # O app grava a frequência com utcnow(), então o "hoje" também é em UTC
            hoje = datetime.combine(datetime.utcnow().date(), datetime.min.time())
            freq = Frequencia.query.filter(Frequencia.usuario_id == user.id, Frequencia.data_registro >= hoje).first()
            termo = TermoAceite.query.filter_by(usuario_id=user.id).first()
            return bool(freq), bool(termo)

        tem_frequencia, tem_termo = consultar_banco(estado)

        # --- Onboarding ---
        if self.exige_onboarding:
            if tem_termo:
                detalhe = "Assinado agora pelo agente." if self.onboarding_assinado else "Termo já assinado anteriormente."
                self.registrar("Regras de Entrada", "Onboarding LGPD / Voluntariado", APROVADO, detalhe, evidencia=False)
            else:
                self.registrar("Regras de Entrada", "Onboarding LGPD / Voluntariado", FALHA, "Sem registo de TermoAceite após o login.")
        elif self.onboarding_assinado:
            self.registrar("Regras de Entrada", "Onboarding LGPD / Voluntariado", FALHA, "O perfil não deveria passar pelo onboarding corporativo.")
        else:
            self.registrar("Regras de Entrada", "Onboarding LGPD / Voluntariado", APROVADO, "Perfil corretamente dispensado do onboarding.", evidencia=False)

        # --- Trilha obrigatória do TCC ---
        if self.perfil["tipo"] in ("Mentor", "Professor", "Mentor Administrador"):
            from models import Usuario as _Usuario
            from app import progresso_trilha_tcc
            feitos, total = consultar_banco(lambda: progresso_trilha_tcc(_Usuario.query.filter_by(email=self.perfil["email"]).first()))
            if feitos >= total:
                detalhe = "Concluída agora pelo agente." if self.trilha_lida_agora else "Já concluída anteriormente."
                self.registrar("Regras de Entrada", "Trilha de orientação do TCC", APROVADO, f"{feitos}/{total} módulos. {detalhe}", evidencia=False)
            else:
                self.registrar("Regras de Entrada", "Trilha de orientação do TCC", FALHA, f"Só {feitos}/{total} módulos concluídos após o login.",
                               esperado="Trilha concluída antes de liberar a plataforma")

        # --- Frequência diária ---
        if self.exige_frequencia:
            if self.modal_frequencia_visto and tem_frequencia:
                self.registrar("Regras de Entrada", "Registo de presença diária", APROVADO, "Modal exibido e presença Online registada.", evidencia=False)
            elif tem_frequencia:
                self.registrar("Regras de Entrada", "Registo de presença diária", APROVADO, "Presença de hoje já estava registada.", evidencia=False)
            else:
                self.registrar("Regras de Entrada", "Registo de presença diária", FALHA, "Modal não apareceu e não há presença registada hoje.")
        elif self.modal_frequencia_visto:
            self.registrar("Regras de Entrada", "Registo de presença diária", FALHA, "Modal de frequência exibido para um perfil que não deveria registar presença.")
        else:
            self.registrar("Regras de Entrada", "Registo de presença diária", APROVADO, "Perfil corretamente dispensado da frequência.", evidencia=False)

    def links_do_menu(self):
        hrefs = self.page.eval_on_selector_all(
            "#menuPrincipal a[href^='/']",
            "els => els.map(e => e.getAttribute('href').split('?')[0])",
        )
        return {h.rstrip("/") for h in hrefs}

    def teste_menu(self):
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        self.lidar_com_bloqueios_de_fluxo()
        links = self.links_do_menu()

        faltando = [ROTAS[r]["nome"] for r in self.MENU_VISIVEL if ROTAS[r]["caminho"] not in links]
        indevidos = [ROTAS[r]["nome"] for r in self.MENU_OCULTO if ROTAS[r]["caminho"] in links]

        if faltando:
            self.registrar("Menu Superior", "Itens obrigatórios visíveis", FALHA, "Ausentes: " + ", ".join(faltando))
        else:
            self.registrar("Menu Superior", "Itens obrigatórios visíveis", APROVADO, f"{len(self.MENU_VISIVEL)} itens conferidos.", evidencia=False)

        if indevidos:
            self.registrar("Menu Superior", "Itens restritos ocultos", FALHA, "Exibidos indevidamente: " + ", ".join(indevidos))
        else:
            self.registrar("Menu Superior", "Itens restritos ocultos", APROVADO, f"{len(self.MENU_OCULTO)} itens conferidos.", evidencia=False)

        if self.visivel('a[href="/logout"]', timeout=1500):
            self.registrar("Menu Superior", "Botão Sair visível", APROVADO, evidencia=False)
        else:
            self.registrar("Menu Superior", "Botão Sair visível", ALERTA, "O link /logout existe mas não está visível na largura 1280px.")

    def teste_matriz_de_acesso(self):
        links_menu = self.links_do_menu() if self.page.url.startswith(BASE_URL) else set()

        for chave in self.ROTAS_PERMITIDAS:
            self.etapa(ROTAS[chave]["nome"], "Acesso permitido", lambda c=chave: self._checar_rota(c, deve_abrir=True, links_menu=links_menu))
        self._bloqueios_sem_aviso = []
        for chave in self.ROTAS_BLOQUEADAS:
            self.etapa(ROTAS[chave]["nome"], "Acesso bloqueado", lambda c=chave: self._checar_rota(c, deve_abrir=False, links_menu=links_menu))
        if self._bloqueios_sem_aviso:
            self.registrar("Menu Superior", "Aviso ao bloquear acesso", ALERTA,
                           "Bloqueio feito sem nenhuma mensagem na tela em: " + ", ".join(self._bloqueios_sem_aviso),
                           esperado="Ao negar uma página, mostrar o aviso 'Acesso negado' que a rota já envia com flash()",
                           dica="As rotas fazem flash('Acesso negado...') e redirecionam para o Painel, mas dashboard.html/base.html "
                                "não renderizam get_flashed_messages().",
                           arquivos="templates/base.html, templates/dashboard.html", evidencia=False)

    def _checar_rota(self, chave, deve_abrir, links_menu):
        rota = ROTAS[chave]
        nome = rota["nome"]
        acao = "Acesso permitido" if deve_abrir else "Acesso bloqueado"
        caminho = self.resolver_caminho(chave)
        if caminho is None:
            self.registrar(nome, acao, PULADO, "Não há dados no banco para montar esta rota (ex.: nenhum projeto).", evidencia=False)
            return

        if rota.get("download"):
            resposta = self.context.request.get(BASE_URL + caminho, max_redirects=0)
            tipo = resposta.headers.get("content-type", "")
            abriu = resposta.status == 200 and "text/html" not in tipo
            if resposta.status >= 500:
                self.registrar(nome, acao, FALHA, f"Erro {resposta.status} ao gerar o ficheiro.")
            elif abriu == deve_abrir:
                detalhe = f"Ficheiro {tipo} ({len(resposta.body())} bytes)." if abriu else f"Bloqueado (HTTP {resposta.status})."
                self.registrar(nome, acao, APROVADO, detalhe, evidencia=False)
            elif deve_abrir:
                self.registrar(nome, acao, FALHA, f"Download não entregue (HTTP {resposta.status}, {tipo}).")
            else:
                self.registrar(nome, acao, FALHA, "🔓 FALHA DE SEGURANÇA: o perfil conseguiu baixar o ficheiro.")
            return

        resposta, bloqueado = self.visitar(caminho)
        if deve_abrir:
            if bloqueado:
                self.registrar(nome, acao, FALHA, f"Acesso negado; redirecionado para {self.caminho_atual()}.")
            else:
                self.registrar(nome, acao, APROVADO, f"HTTP {resposta.status if resposta else '?'}.", evidencia=False)
                self.checar_saude(nome, resposta)
        else:
            if bloqueado:
                self.registrar(nome, acao, APROVADO, f"Bloqueado; destino {self.caminho_atual()}.", evidencia=False)
                redirecionou = self.caminho_atual() != caminho.split("?")[0].rstrip("/")
                if redirecionou and not self.page.locator(".alert:visible").count():
                    self._bloqueios_sem_aviso.append(nome)
            else:
                self.registrar(nome, acao, FALHA, "🔓 FALHA DE SEGURANÇA: a página abriu para um perfil sem permissão.")
            if caminho.rstrip("/") in links_menu:
                self.registrar(nome, "Coerência menu × permissão", ALERTA,
                               "O link aparece no menu, mas a rota nega o acesso a este perfil.", evidencia=False)

    # --------------------------------------------------------------------------
    # Tema e idioma em TODAS as páginas que o perfil pode abrir
    # --------------------------------------------------------------------------
    def paginas_navegaveis(self):
        """(nome, caminho) das páginas permitidas que usam o layout do site (sem downloads nem páginas de impressão)."""
        paginas = []
        for chave in self.ROTAS_PERMITIDAS:
            if ROTAS[chave].get("download") or ROTAS[chave].get("independente"):
                continue
            caminho = self.resolver_caminho(chave)
            if caminho:
                paginas.append((ROTAS[chave]["nome"], caminho))
        return paginas

    def preferencias_atuais(self):
        from models import Usuario

        def ler():
            user = Usuario.query.filter_by(email=self.perfil["email"]).first()
            return user.tema or "claro", user.idioma or "pt"
        return consultar_banco(ler)

    def trocar_preferencia(self, rota, valor):
        self.page.goto(BASE_URL + f"/{rota}/{valor}", wait_until="domcontentloaded")
        self.lidar_com_bloqueios_de_fluxo()

    # Mede o tema aplicado: atributo data-theme, fundo, textos sem contraste e blocos claros
    JS_AUDITORIA_TEMA = r"""() => {
        const lum = (c) => {
            const m = (c || '').match(/[\d.]+/g); if (!m) return null;
            const [r, g, b, a] = m.map(Number); if (a === 0) return null;
            const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
        };
        const fundo = (el) => {
            while (el && el !== document.documentElement) {
                const c = getComputedStyle(el).backgroundColor; const m = c.match(/[\d.]+/g);
                if (m && (m.length < 4 || Number(m[3]) > 0.5)) return lum(c);
                el = el.parentElement;
            }
            return lum(getComputedStyle(document.body).backgroundColor) ?? 1;
        };
        const visivel = (el) => {
            const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.1
                && !el.closest('.modal:not(.show), .dropdown-menu:not(.show), .collapse:not(.show)');
        };
        const ilegiveis = [];
        for (const el of document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,small,td,th,label,a,li,strong,button,div')) {
            if (!visivel(el)) continue;
            const proprio = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ').trim();
            if (proprio.length < 2) continue;
            const lt = lum(getComputedStyle(el).color); if (lt === null) continue;
            const lf = fundo(el);
            const contraste = (Math.max(lt, lf) + 0.05) / (Math.min(lt, lf) + 0.05);
            if (contraste < 3) ilegiveis.push('"' + proprio.slice(0, 35) + '" (' + contraste.toFixed(1) + ':1)');
        }
        const claros = {};
        for (const el of document.querySelectorAll('.card, .card-body, .card-header, .list-group-item, .bg-white, .bg-light, .form-control, .form-select, .table > tbody > tr > td, .modal.show .modal-content')) {
            if (!visivel(el)) continue;
            const r = el.getBoundingClientRect(); if (r.width * r.height < 1500) continue;
            const l = lum(getComputedStyle(el).backgroundColor);
            if (l !== null && l > 0.8) {
                const nome = (typeof el.className === 'string' && el.className.trim()) ? el.className.trim().split(/\s+/)[0] : el.tagName.toLowerCase();
                claros[nome] = (claros[nome] || 0) + 1;
            }
        }
        return { tema: document.documentElement.getAttribute('data-theme'), fundo: getComputedStyle(document.body).backgroundColor,
                 ilegiveis: [...new Set(ilegiveis)], claros };
    }"""

    def teste_temas_todas_paginas(self):
        paginas = self.paginas_navegaveis()
        tema_original, _ = self.preferencias_atuais()
        fundos = {}
        try:
            for tema in TEMAS:
                self.trocar_preferencia("alterar-tema", tema)
                problemas_no_tema = 0
                fundos[tema] = {}
                for nome, caminho in paginas:
                    self.visitar(caminho)
                    dados = self.page.evaluate(self.JS_AUDITORIA_TEMA)
                    fundos[tema][nome] = dados["fundo"]
                    acao = f"{nome} › tema {tema}"
                    arquivos = f"{ARQUIVOS_POR_MODULO['Tema']}; {ARQUIVOS_POR_MODULO.get(nome, '')}"
                    if dados["tema"] != tema:
                        problemas_no_tema += 1
                        self.registrar("Tema", acao, FALHA, f"html[data-theme] ficou '{dados['tema']}'.",
                                       esperado=f"data-theme='{tema}' em todas as páginas", arquivos=arquivos)
                        continue
                    if tema in TEMAS_ESCUROS and dados["claros"]:
                        problemas_no_tema += 1
                        blocos = ", ".join(f"{k} ×{v}" for k, v in dados["claros"].items())
                        self.registrar("Tema", acao, FALHA, f"Blocos com fundo branco/claro no tema {tema}: {blocos}.",
                                       esperado=f"Cards, tabelas, campos e modais com fundo escuro no tema '{tema}'",
                                       dica="Faltam regras html[data-theme=...] para estas classes (o Bootstrap as pinta de branco por padrão).",
                                       arquivos=arquivos)
                    if dados["ilegiveis"]:
                        problemas_no_tema += 1
                        self.registrar("Tema", acao, ALERTA,
                                       f"{len(dados['ilegiveis'])} texto(s) com contraste < 3:1, ex.: " + "; ".join(dados["ilegiveis"][:4]),
                                       esperado="Contraste mínimo de 3:1 entre texto e fundo (WCAG)", arquivos=arquivos)
                base = fundos[tema].get(paginas[0][0]) if paginas else None
                destoantes = [n for n, f in fundos[tema].items() if f != base]
                if destoantes:
                    problemas_no_tema += 1
                    self.registrar("Tema", f"Consistência do tema {tema}", ALERTA,
                                   f"Fundo diferente do {paginas[0][0]} ({base}) em: " + ", ".join(destoantes),
                                   esperado="Mesmo fundo em todas as páginas do mesmo tema", arquivos=ARQUIVOS_POR_MODULO["Tema"])
                if not problemas_no_tema:
                    self.registrar("Tema", f"Tema {tema} em {len(paginas)} página(s)", APROVADO, f"Fundo {base}.", evidencia=False)

            painel = paginas[0][0] if paginas else None
            iguais = [t for t in TEMAS if t != "claro" and painel and fundos[t].get(painel) == fundos["claro"].get(painel)]
            if iguais:
                self.registrar("Tema", "Temas visualmente distintos", FALHA,
                               f"Tema(s) {', '.join(iguais)} com o mesmo fundo do tema claro no {painel}.",
                               esperado="Cada tema altera a aparência da página", arquivos=ARQUIVOS_POR_MODULO["Tema"])
        finally:
            self.trocar_preferencia("alterar-tema", tema_original)

    # Texto visível da interface, sem os dados do banco (tabelas, seletores, campos e chat)
    # escopo 'menu': só a barra de navegação (comum a todas as páginas, inclusive itens dos dropdowns)
    # escopo 'pagina': o conteúdo próprio da página, sem a barra de navegação
    JS_TEXTO_INTERFACE = r"""(escopo) => {
        const raiz = escopo === 'menu' ? document.querySelector('nav') : document.body;
        if (!raiz) return '';
        let ignorar = 'tbody, select, option, textarea, input, script, style, #chat-box, .modal:not(.show)';
        if (escopo !== 'menu') ignorar += ', nav, .dropdown-menu:not(.show)';
        const partes = [];
        const caminhar = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
        while (caminhar.nextNode()) {
            const n = caminhar.currentNode; const pai = n.parentElement;
            if (!pai || pai.closest(ignorar) || !n.textContent.trim()) continue;
            if (escopo !== 'menu' && !pai.getClientRects().length) continue;
            partes.push(n.textContent.trim());
        }
        return partes.join(' | ');
    }"""

    def textos_em_portugues(self, texto, termos_pt, palavras_pt, dados_banco):
        sobras = {t for t in termos_pt if t in texto}
        sobras |= {p for p in palavras_pt if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", texto)}
        sobras |= set(re.findall(r"\w*[çãõâêô]\w*", texto, flags=re.IGNORECASE))
        return {s for s in sobras if s.lower() not in dados_banco}

    PALAVRAS_PT = ["Projetos", "Andamento", "Concluídos", "Nenhum", "Nenhuma", "Fechar", "Voltar", "Tarefa", "Tarefas",
                   "Prazo", "Aluno", "Alunos", "Você", "Não", "Sim", "Painel", "Acompanhamento", "Sessões", "Detalhes",
                   "Novo", "Nova", "Salvar", "Excluir", "Responsável", "Atribuído"]
    PALAVRAS_VALIDAS_ES = {"Salvar", "Excluir"}

    def vocabulario_do_banco(self):
        """Palavras que vêm dos dados (nomes de cursos, projetos, pessoas...) e não da interface."""
        import models

        def coletar():
            palavras = set()
            for nome in ("Usuario", "Curso", "Projeto", "Tarefa", "Grupo", "Empresa", "Turma", "SessaoMentoria", "Acompanhamento"):
                modelo = getattr(models, nome, None)
                if modelo is None:
                    continue
                colunas = [c for c in modelo.__table__.columns
                           if getattr(c.type, "length", None) or c.type.__class__.__name__ == "Text"]
                for linha in modelo.query.with_entities(*colunas).all():
                    for valor in linha:
                        if isinstance(valor, str):
                            palavras.update(re.findall(r"\w+", valor.lower()))
            return palavras
        return consultar_banco(coletar)

    def teste_idiomas_todas_paginas(self):
        from traducoes import TEXTOS

        paginas = self.paginas_navegaveis()
        _, idioma_original = self.preferencias_atuais()
        dados_banco = self.vocabulario_do_banco()
        try:
            for sigla, nome_idioma in IDIOMAS.items():
                alvo = TEXTOS[sigla]
                # Textos PT do dicionário com tradução diferente: se aparecerem, ficaram sem traduzir
                termos_pt = {v for k, v in TEXTOS["pt"].items()
                             if len(v) >= 5 and alvo.get(k) and alvo[k] != v and v not in alvo.values()}
                palavras_pt = [p for p in self.PALAVRAS_PT if not (sigla == "es" and p in self.PALAVRAS_VALIDAS_ES)]
                self.trocar_preferencia("alterar-idioma", sigla)
                paginas_ok = 0
                menu_conferido = False
                for nome, caminho in paginas:
                    self.visitar(caminho)
                    problemas = []
                    lang = self.page.get_attribute("html", "lang")
                    if lang != sigla:
                        problemas.append(f"<html lang='{lang}'>")

                    # O menu é igual em todas as páginas (base.html): conferido uma vez por idioma
                    if not menu_conferido:
                        menu_conferido = True
                        menu = self.page.inner_text("#menuPrincipal") if self.page.locator("#menuPrincipal").count() else ""
                        faltando = [alvo[k] for k in ("painel_geral", "sessoes", "acompanhamento") if alvo.get(k) and alvo[k] not in menu]
                        sobras_menu = self.textos_em_portugues(self.page.evaluate(self.JS_TEXTO_INTERFACE, "menu"),
                                                               termos_pt, palavras_pt, dados_banco)
                        if faltando or sobras_menu:
                            self.registrar("Idioma", f"Menu superior (todas as páginas) › {nome_idioma}", FALHA,
                                           ("menu sem: " + ", ".join(faltando) + "; " if faltando else "")
                                           + f"{len(sobras_menu)} texto(s) em português: " + ", ".join(f"'{s}'" for s in sorted(sobras_menu)[:12]),
                                           esperado=f"Barra de navegação e menus suspensos em {nome_idioma}",
                                           dica="Os itens fixos da navbar em base.html (ex.: Projetos, Diário de Classe, Administração e os itens do dropdown) precisam usar t('chave').",
                                           arquivos=f"templates/base.html (navbar #menuPrincipal); {ARQUIVOS_POR_MODULO['Idioma']}")
                        else:
                            self.registrar("Idioma", f"Menu superior › {nome_idioma}", APROVADO, evidencia=False)

                    sobras = self.textos_em_portugues(self.page.evaluate(self.JS_TEXTO_INTERFACE, "pagina"),
                                                      termos_pt, palavras_pt, dados_banco)
                    if sobras:
                        problemas.append(f"{len(sobras)} texto(s) em português: " + ", ".join(f"'{s}'" for s in sorted(sobras)[:10]))

                    if problemas:
                        self.registrar("Idioma", f"{nome} › {nome_idioma}", FALHA, "; ".join(problemas),
                                       esperado=f"Página inteira em {nome_idioma}, com <html lang='{sigla}'>",
                                       dica="Trocar textos fixos do template/flash por t('chave') e criar a chave em pt, en e es.",
                                       arquivos=f"{ARQUIVOS_POR_MODULO['Idioma']}; {ARQUIVOS_POR_MODULO.get(nome, '')}")
                    else:
                        paginas_ok += 1
                if paginas_ok == len(paginas):
                    self.registrar("Idioma", f"{nome_idioma} em {len(paginas)} página(s)", APROVADO, evidencia=False)
        finally:
            self.trocar_preferencia("alterar-idioma", idioma_original)

    def teste_logout(self):
        self.page.goto(BASE_URL + "/logout", wait_until="domcontentloaded")
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        if self.caminho_atual() == "/":
            self.registrar("Autenticação", "Logout encerra a sessão", APROVADO, "Após sair, /dashboard volta ao login.", evidencia=False)
        else:
            self.registrar("Autenticação", "Logout encerra a sessão", FALHA, f"Após sair, /dashboard abriu {self.caminho_atual()}.")

    # --------------------------------------------------------------------------
    # Utilitários para os testes específicos de cada perfil
    # --------------------------------------------------------------------------
    def verificar_relogio_voluntariado(self, deve_existir):
        self.visitar("/dashboard")
        existe = self.visivel("text=Relógio de Voluntariado Corporativo")
        acao = "Relógio de Voluntariado " + ("visível" if deve_existir else "oculto")
        if existe == deve_existir:
            self.registrar("Voluntariado ESG", acao, APROVADO, evidencia=False)
        else:
            self.registrar("Voluntariado ESG", acao, FALHA, "Visibilidade do relógio diverge da regra de negócio.")
            return
        if not deve_existir:
            return

        self.page.locator('button[data-bs-target="#modalVoluntariadoManual"]').click()
        if not self.visivel("#modalVoluntariadoManual"):
            self.registrar("Voluntariado ESG", "Abrir lançamento manual", FALHA, "O modal de lançamento manual não abriu.")
            return
        campos = ["tipo_atividade", "data", "hora_inicio", "hora_fim"]
        ausentes = [c for c in campos if self.page.locator(f'#modalVoluntariadoManual [name="{c}"]').count() == 0]
        if ausentes:
            self.registrar("Voluntariado ESG", "Abrir lançamento manual", FALHA, "Campos ausentes: " + ", ".join(ausentes))
            return
        self.registrar("Voluntariado ESG", "Abrir lançamento manual", APROVADO, "Modal com todos os campos obrigatórios.", evidencia=False)

        if not self.escrita:
            self.page.keyboard.press("Escape")
            return
        modal = self.page.locator("#modalVoluntariadoManual")
        modal.locator('select[name="tipo_atividade"]').select_option(value="Apoio Institucional")
        modal.locator('input[name="data"]').fill(date.today().isoformat())
        modal.locator('input[name="hora_inicio"]').fill("09:00")
        modal.locator('input[name="hora_fim"]').fill("10:00")
        # O perfil no texto evita confundir com os lançamentos dos outros agentes que rodam em paralelo
        observacao = f"[OmniTest] Lançamento automático {self.chave_perfil} {self.carimbo}"
        modal.locator('textarea[name="observacoes"]').fill(observacao)
        modal.locator('button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()

        from models import CheckinVoluntariado
        minutos = consultar_banco(lambda: [c.total_minutos for c in CheckinVoluntariado.query.filter_by(observacoes=observacao).all()])
        if minutos == [60]:
            self.registrar("Voluntariado ESG", "Gravar horas manuais (escrita)", APROVADO, "Registo de 60 minutos gravado no banco.", evidencia=False)
        else:
            self.registrar("Voluntariado ESG", "Gravar horas manuais (escrita)", FALHA,
                           f"Esperado 1 registo de 60 min no banco; encontrado: {minutos or 'nenhum'}.",
                           esperado="Lançamento manual 09:00–10:00 gravado com 60 minutos",
                           arquivos="app.py (rota lancamento_manual_voluntariado), templates/dashboard.html (modalVoluntariadoManual)")
        if not self.visivel(".alert", timeout=2000):
            self.registrar("Voluntariado ESG", "Confirmação ao utilizador", FALHA,
                           "Depois de gravar, o Painel não mostra nenhuma mensagem: o utilizador não sabe se deu certo.",
                           esperado="Aviso 'Lançamento manual gravado!' visível após o envio",
                           dica="lancamento_manual_voluntariado() chama flash(), mas nem base.html nem dashboard.html renderizam "
                                "get_flashed_messages(). Colocar o bloco de mensagens flash em base.html resolve para todas as páginas.",
                           arquivos="templates/base.html, templates/dashboard.html")

    def abrir_ticket_demanda(self):
        """Abre um ticket no Portal de Demandas (apenas com --escrita). Devolve o título criado."""
        titulo = f"[OmniTest] Ticket automático {self.chave_perfil} {self.carimbo}"
        self.visitar("/demandas")
        self.page.locator('button[data-bs-target="#modalNovaDemanda"]').click()
        modal = self.page.locator("#modalNovaDemanda")
        modal.wait_for(state="visible")
        modal.locator('input[name="titulo"]').fill(titulo)
        modal.locator('select[name="tipo_demanda"]').select_option(index=0)
        modal.locator('select[name="prioridade"]').select_option(index=0)
        modal.locator('textarea[name="descricao"]').fill("Ticket criado automaticamente pelo agente OmniTest. Pode ser encerrado.")
        modal.locator('button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()
        if titulo in self.texto_pagina():
            self.registrar("Portal de Demandas", "Abrir ticket (escrita)", APROVADO, titulo, evidencia=False)
        else:
            self.registrar("Portal de Demandas", "Abrir ticket (escrita)", FALHA, "O ticket não apareceu na lista após o envio.")
        return titulo

    def verificar_isolamento_alunos(self, caminho, nome_pagina):
        """Mentor/Professor só podem ver nos seletores os alunos vinculados a eles."""
        from models import Usuario

        def alunos_alheios():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            return [a.email for a in Usuario.query.filter(
                Usuario.tipo_usuario == "Aluno", ~Usuario.mentores.any(id=eu.id)).all()]

        alheios = consultar_banco(alunos_alheios)
        if not alheios:
            self.registrar(nome_pagina, "Isolamento de alunos", PULADO, "Todos os alunos estão vinculados a este perfil.", evidencia=False)
            return
        self.visitar(caminho)
        opcoes = " ".join(self.page.eval_on_selector_all("select option", "els => els.map(e => e.textContent)"))
        vazados = [e for e in alheios if e in opcoes]
        if vazados:
            self.registrar(nome_pagina, "Isolamento de alunos", FALHA,
                           f"{len(vazados)} aluno(s) não vinculados aparecem nos seletores (ex.: {vazados[0]}).")
        else:
            self.registrar(nome_pagina, "Isolamento de alunos", APROVADO, "Somente alunos vinculados aparecem.", evidencia=False)

    # --------------------------------------------------------------------------
    # KPIs do Painel Geral para perfis de equipa, recalculados no banco
    # --------------------------------------------------------------------------
    ESCOPO_ALUNOS = None  # 'vinculados' (Mentor/Professor), 'todos' (Admins) ou 'empresas' (Gestor B2B)

    def ler_card(self, rotulo):
        """Valor (h3) do card do Painel Geral cujo rótulo (small) é exatamente este texto."""
        rotulo_el = self.page.locator(f'small:text-is("{rotulo}")').first
        if not rotulo_el.count():
            return None
        return rotulo_el.locator("xpath=..").locator("h3").inner_text().strip()

    def kpis_esperados_equipe(self):
        from app import db
        from models import Usuario, Acompanhamento, Curso, Turma, Empresa, turma_aluno

        def calcular():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            consulta = Usuario.query.filter(Usuario.tipo_usuario == "Aluno")
            if self.ESCOPO_ALUNOS == "vinculados":
                consulta = consulta.filter(Usuario.mentores.any(id=eu.id))
            elif self.ESCOPO_ALUNOS == "empresas":
                ids = [linha[0] for linha in db.session.query(turma_aluno.c.aluno_id)
                       .join(Turma, Turma.id == turma_aluno.c.turma_id)
                       .join(Empresa, Empresa.id == Turma.empresa_id)
                       .filter(Empresa.gestor_id == eu.id).distinct()]
                consulta = consulta.filter(Usuario.id.in_(ids or [-1]))
            alunos = consulta.all()
            ids_alunos = [a.id for a in alunos] or [-1]
            matriculas = [a for a in Acompanhamento.query.filter(Acompanhamento.aluno_id.in_(ids_alunos)).all()
                          if db.session.get(Curso, a.curso_id)]
            finalizados = [a for a in matriculas if a.status == "Finalizado"]
            return {
                "total_alunos": len(alunos),
                "finalizados": len(finalizados),
                "com_certificado": sum(1 for a in finalizados if a.certificado_anexado),
                "sem_certificado": sum(1 for a in finalizados if not a.certificado_anexado),
                "cursos_risco": sum(1 for a in matriculas if a.status == "Parado"),
            }
        return consultar_banco(calcular)

    def verificar_kpis_equipe(self):
        from traducoes import TEXTOS

        descricao_escopo = {"vinculados": "alunos vinculados a este perfil", "todos": "todos os alunos da plataforma",
                            "empresas": "alunos das turmas das empresas deste gestor"}[self.ESCOPO_ALUNOS]
        esperado = self.kpis_esperados_equipe()
        textos = TEXTOS.get(self.preferencias_atuais()[1], TEXTOS["pt"])
        self.visitar("/dashboard")

        divergencias, conferidos = [], []
        for chave, valor in esperado.items():
            lido = self.ler_card(textos[chave])
            if lido is None:
                divergencias.append(f"card '{textos[chave]}' não encontrado")
            elif lido != str(valor):
                divergencias.append(f"{textos[chave]}: tela {lido} × banco {valor}")
            else:
                conferidos.append(f"{textos[chave]}={valor}")

        if not divergencias:
            self.registrar("Painel Geral", "KPIs no escopo do perfil", APROVADO, f"{', '.join(conferidos)} ({descricao_escopo}).", evidencia=False)
            return
        dica = {
            "vinculados": "Em dashboard() de app.py a condição `current_user.tipo_usuario == ['Mentor','Professor']` compara texto com lista e "
                          "nunca é verdadeira, então Mentor/Professor caem no ramo do administrador. Usar `in ['Mentor', 'Professor']`.",
            "todos": "Conferir os contadores do ramo do administrador em dashboard() de app.py.",
            "empresas": "dashboard() não tem ramo para 'Admin B2B': o gestor cai no ramo do administrador e vê a plataforma inteira.",
        }[self.ESCOPO_ALUNOS]
        # Para o Gestor B2B o escopo certo é decisão de negócio, por isso vira alerta
        status = ALERTA if self.ESCOPO_ALUNOS == "empresas" else FALHA
        self.registrar("Painel Geral", "KPIs no escopo do perfil", status, "; ".join(divergencias),
                       esperado=f"Cards calculados só com {descricao_escopo}", dica=dica)

    # --------------------------------------------------------------------------
    # Relatório ESG (CSV): linhas certas para o perfil e empresa de cada colaborador
    # --------------------------------------------------------------------------
    def verificar_relatorio_esg(self):
        import csv
        import io
        from models import Usuario, Empresa, CheckinVoluntariado

        def esperado():
            eu = Usuario.query.filter_by(email=self.perfil["email"]).first()
            consulta = CheckinVoluntariado.query
            if self.ESCOPO_ALUNOS == "empresas":
                ids = [m.id for e in Empresa.query.filter_by(gestor_id=eu.id).all() for m in e.mentores]
                consulta = consulta.filter(CheckinVoluntariado.usuario_id.in_(ids or [-1]))
            empresas = {}
            for registro in consulta.all():
                user = Usuario.query.get(registro.usuario_id)
                if user:
                    empresas[user.nome] = sorted(e.nome for e in getattr(user, "empresas_vinculadas", []) or [])
            return consulta.count(), empresas

        total, empresas_por_pessoa = consultar_banco(esperado)
        resposta = self.context.request.get(BASE_URL + ROTAS["esg_csv"]["caminho"])
        if resposta.status != 200:
            self.registrar("Exportar ESG (CSV)", "Conteúdo do relatório", FALHA, f"HTTP {resposta.status} ao baixar o CSV.")
            return
        linhas = list(csv.reader(io.StringIO(resposta.body().decode("utf-8-sig")), delimiter=";"))
        cabecalho, dados = (linhas[0], linhas[1:]) if linhas else ([], [])

        # Guarda o próprio CSV como evidência
        os.makedirs(self.pasta_evidencias, exist_ok=True)
        with open(os.path.join(self.pasta_evidencias, "relatorio_esg.csv"), "wb") as f:
            f.write(resposta.body())

        if total == 0:
            self.registrar("Exportar ESG (CSV)", "Conteúdo do relatório", PULADO,
                           "Não há lançamentos de voluntariado no escopo deste perfil (use --escrita para criar um).", evidencia=False)
            return
        problemas = []
        if len(dados) != total:
            problemas.append(f"{len(dados)} linha(s) no CSV × {total} lançamento(s) no escopo do perfil")
        if "Empresa Associada" in cabecalho:
            col_nome, col_emp = cabecalho.index("Nome do Colaborador"), cabecalho.index("Empresa Associada")
            erradas = sorted({l[col_nome] for l in dados
                              if empresas_por_pessoa.get(l[col_nome]) and not all(e in l[col_emp] for e in empresas_por_pessoa[l[col_nome]])})
            if erradas:
                problemas.append(f"'Empresa Associada' sem a empresa real de: {', '.join(erradas[:5])} (saiu como '{dados[0][col_emp]}')")
        if problemas:
            self.registrar("Exportar ESG (CSV)", "Conteúdo do relatório", FALHA, "; ".join(problemas),
                           esperado="Uma linha por lançamento do escopo do perfil, com a empresa de cada colaborador",
                           dica="Em exportar_relatorio_esg() de app.py o código lê usuario.empresas, mas o relacionamento em "
                                "models.py chama-se empresas_vinculadas; por isso a coluna sai sempre 'Institucional (Hub)'.",
                           arquivos="app.py (rotas exportar_relatorio_esg e exportar_relatorio_esg_pdf), models.py (Empresa.mentores / empresas_vinculadas)")
        else:
            self.registrar("Exportar ESG (CSV)", "Conteúdo do relatório", APROVADO, f"{len(dados)} linha(s) conferidas com o banco.", evidencia=False)

    def verificar_portal_demandas(self, eh_gestor):
        """Todos os perfis com acesso abrem tickets; só gestores respondem oficialmente."""
        self.visitar("/demandas")
        if self.page.locator('button[data-bs-target="#modalNovaDemanda"]').count():
            self.registrar("Portal de Demandas", "Botão de novo ticket", APROVADO, evidencia=False)
        else:
            self.registrar("Portal de Demandas", "Botão de novo ticket", FALHA, "Botão 'Nova Demanda' não encontrado.")

        formularios_resposta = self.page.locator('textarea[name="resposta_oficial"]').count()
        tickets = self.page.locator('button[data-bs-target^="#modalDemanda"]').count()
        if eh_gestor:
            if tickets == 0:
                self.registrar("Portal de Demandas", "Gestor pode responder tickets", PULADO, "Nenhum ticket na lista.", evidencia=False)
            elif formularios_resposta:
                self.registrar("Portal de Demandas", "Gestor pode responder tickets", APROVADO, f"{tickets} ticket(s) com formulário de resposta.", evidencia=False)
            else:
                self.registrar("Portal de Demandas", "Gestor pode responder tickets", FALHA, "Tickets listados sem formulário de resposta oficial.")
        elif formularios_resposta:
            self.registrar("Portal de Demandas", "Resposta oficial restrita a gestores", FALHA,
                           "Formulário de resposta oficial exibido para um perfil que não é gestor.")
        else:
            self.registrar("Portal de Demandas", "Resposta oficial restrita a gestores", APROVADO, evidencia=False)

    def responder_ticket_demanda(self, titulo):
        """Gestores respondem ao ticket aberto pelo próprio agente (apenas com --escrita)."""
        modal = self.page.locator('div[id^="modalDemanda"]', has_text=titulo).first
        if modal.count() == 0:
            self.registrar("Portal de Demandas", "Responder ticket (escrita)", FALHA, "Modal do ticket criado não encontrado.")
            return
        id_modal = modal.get_attribute("id")
        self.page.locator(f'button[data-bs-target="#{id_modal}"]').first.click()
        modal.wait_for(state="visible")
        modal.locator('textarea[name="resposta_oficial"]').fill("[OmniTest] Resposta automática do gestor.")
        modal.locator('select[name="status"]').select_option(index=modal.locator('select[name="status"] option').count() - 1)
        modal.locator('button:has-text("Gravar Resposta")').click()
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()
        if "[OmniTest] Resposta automática do gestor." in self.page.content():
            self.registrar("Portal de Demandas", "Responder ticket (escrita)", APROVADO, evidencia=False)
        else:
            self.registrar("Portal de Demandas", "Responder ticket (escrita)", FALHA, "A resposta oficial não foi gravada.")

    def verificar_cadastros(self):
        """Tabela de utilizadores carrega e a busca encontra o próprio utilizador de teste."""
        self.visitar("/admin/usuarios")
        linhas = self.page.locator("table tbody tr").count()
        if linhas == 0:
            self.registrar("Cadastros & Usuários", "Tabela de utilizadores", FALHA, "Nenhuma linha na tabela.")
            return
        self.registrar("Cadastros & Usuários", "Tabela de utilizadores", APROVADO, f"{linhas} linha(s) carregadas.", evidencia=False)

        busca = self.page.locator('input[type="search"], input[placeholder*="usca"], input[placeholder*="esquis"], input[placeholder*="iltr"]').first
        if busca.count() == 0:
            self.registrar("Cadastros & Usuários", "Busca de utilizadores", PULADO, "Campo de busca não identificado.", evidencia=False)
            return
        busca.fill(self.perfil["email"])
        self.page.wait_for_timeout(800)
        visiveis = [t for t in self.page.locator("table tbody tr:visible").all_inner_texts() if t.strip()]
        if visiveis and all(self.perfil["email"] in t for t in visiveis):
            self.registrar("Cadastros & Usuários", "Busca de utilizadores", APROVADO, f"Filtro devolveu {len(visiveis)} linha(s) corretas.", evidencia=False)
        elif visiveis and any(self.perfil["email"] in t for t in visiveis):
            self.registrar("Cadastros & Usuários", "Busca de utilizadores", ALERTA, f"Encontrou o utilizador, mas manteve {len(visiveis)} linhas visíveis.")
        else:
            self.registrar("Cadastros & Usuários", "Busca de utilizadores", FALHA, "A busca pelo e-mail não devolveu o utilizador.")
        busca.fill("")

    # --------------------------------------------------------------------------
    # TOUR GUIADO: convite do primeiro acesso, tour encadeado e botão manual
    # --------------------------------------------------------------------------
    def exibir_tour_no_banco(self, valor=None):
        """Lê (e, se valor for dado, grava) a flag Usuario.exibir_tour do utilizador de teste."""
        from models import Usuario

        def acao():
            from app import db
            user = Usuario.query.filter_by(email=self.perfil["email"]).first()
            if valor is not None:
                user.exibir_tour = valor
                db.session.commit()
            return bool(user.exibir_tour)
        return consultar_banco(acao)

    def percorrer_passos_do_tour(self, espera=4000):
        """Clica 'Próximo' até o fim do tour da página. Devolve os textos dos passos (ou None se não abriu)."""
        if not self.visivel(".introjs-tooltip", timeout=espera) and not self._esperar_tooltip(espera):
            return None
        passos = []
        for _ in range(40):
            self.page.wait_for_timeout(300)
            texto = self.page.locator(".introjs-tooltiptext").first.inner_text().strip()
            passos.append(texto)
            self.anunciar(f"Tour › {self.caminho_atual()} › passo {len(passos)}")
            botao = self.page.locator(".introjs-nextbutton").first
            ultimo = "introjs-donebutton" in (botao.get_attribute("class") or "")
            botao.click()
            if ultimo:
                break
            try:
                self.page.locator(".introjs-tooltiptext", has_not_text=texto).first.wait_for(state="visible", timeout=1500)
            except Exception:
                break
        return passos

    def _esperar_tooltip(self, espera):
        try:
            self.page.locator(".introjs-tooltip").first.wait_for(state="visible", timeout=espera)
            return True
        except Exception:
            return False

    def problemas_nos_passos(self, passos):
        problemas = []
        for i, texto in enumerate(passos, 1):
            if not texto:
                problemas.append(f"passo {i} vazio")
            elif re.search(r"\btour_\w+", texto) or "{{" in texto:
                problemas.append(f"passo {i} com chave crua: '{texto[:40]}'")
        return problemas

    def teste_tour(self):
        valor_original = self.exibir_tour_no_banco()
        self.tratar_tour = False
        try:
            self.etapa("Tour", "Convite do primeiro acesso", self.tour_convite)
            self.etapa("Tour", "Lembrar Depois", self.tour_lembrar_depois)
            self.etapa("Tour", "Fazer o Tour Agora (encadeado)", self.tour_completo)
            self.etapa("Tour", "Não mostrar novamente", self.tour_nao_mostrar)
            self.etapa("Tour", "Botão de tour em cada página", self.tour_botao_manual)
            self.etapa("Tour", "Textos do tour em en/es", self.tour_traducoes)
        finally:
            self.tratar_tour = True
            self.exibir_tour_no_banco(valor_original)
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass

    def abrir_convite_do_tour(self):
        self.exibir_tour_no_banco(True)
        self.visitar("/dashboard")
        return self.visivel("#modalTourInicial", timeout=3000)

    def tour_convite(self):
        from models import Usuario

        nome = consultar_banco(lambda: Usuario.query.filter_by(email=self.perfil["email"]).first().nome)
        if not self.abrir_convite_do_tour():
            self.registrar("Tour", "Convite do primeiro acesso", FALHA, "Com exibir_tour=True o convite do tour não abriu no Painel Geral.",
                           esperado="Modal 'Olá, <nome>!' com as opções Fazer o Tour, Lembrar Depois e Não mostrar novamente")
            return
        modal = self.page.locator("#modalTourInicial")
        titulo = modal.locator(".modal-title").inner_text().strip()
        corpo = modal.locator(".modal-body").inner_text()
        botoes = [b for b in ("Fazer o Tour Agora", "Lembrar Depois", "Não mostrar novamente")
                  if modal.locator(f'button:has-text("{b}")').count() == 0]
        problemas = []
        if titulo != f"Olá, {nome.split()[0]}!":
            problemas.append(f"saudação '{titulo}' (esperado 'Olá, {nome.split()[0]}!')")
        if self.perfil["tipo"] not in corpo:
            problemas.append(f"o texto não cita o perfil {self.perfil['tipo']}")
        if botoes:
            problemas.append("botões ausentes: " + ", ".join(botoes))
        if problemas:
            self.registrar("Tour", "Convite do primeiro acesso", FALHA, "; ".join(problemas))
        else:
            self.registrar("Tour", "Convite do primeiro acesso", APROVADO, f"'{titulo}' com as 3 opções.", evidencia=False)

    def tour_lembrar_depois(self):
        if not self.abrir_convite_do_tour():
            self.registrar("Tour", "Lembrar Depois", PULADO, "O convite não abriu.", evidencia=False)
            return
        self.page.locator('#modalTourInicial button:has-text("Lembrar Depois")').click()
        self.page.wait_for_timeout(1000)
        fechou = not self.page.locator("#modalTourInicial").is_visible()
        continua_ativo = self.exibir_tour_no_banco()
        self.visitar("/dashboard")
        voltou = self.visivel("#modalTourInicial", timeout=3000)
        if fechou and continua_ativo and voltou:
            self.registrar("Tour", "Lembrar Depois", APROVADO, "O convite fecha e volta no próximo acesso.", evidencia=False)
        else:
            self.registrar("Tour", "Lembrar Depois", FALHA,
                           f"fechou={fechou}, exibir_tour continua ligado={continua_ativo}, convite voltou={voltou}.",
                           esperado="Fechar o convite agora e mostrá-lo de novo no próximo acesso")

    def tour_completo(self):
        if not self.abrir_convite_do_tour():
            self.registrar("Tour", "Fazer o Tour Agora", PULADO, "O convite não abriu.", evidencia=False)
            return
        self.page.locator('#modalTourInicial button:has-text("Fazer o Tour Agora")').click()

        percurso, resumo, problemas = ["/dashboard"], [], []
        for _ in range(10):
            pagina = self.caminho_atual()
            # Guardada ANTES dos cliques: o último passo já pode disparar a navegação
            url_antes = self.page.url
            self._navegacoes.clear()
            passos = self.percorrer_passos_do_tour()
            if passos is None:
                if "tour_continuo=1" in self.page.url:
                    problemas.append(f"o tour parou em {pagina}: a página foi aberta com tour_continuo=1 mas não continua o tour")
                elif len(percurso) == 1:
                    problemas.append("o tour não começou após 'Fazer o Tour Agora'")
                break
            resumo.append(f"{pagina} ({len(passos)} passos)")
            problemas += [f"{pagina}: {p}" for p in self.problemas_nos_passos(passos)]

            # Espera o último passo navegar (a URL final pode ser igual à de partida, se houver redirecionamento)
            for _ in range(20):
                if self._navegacoes or self.page.url != url_antes:
                    break
                self.page.wait_for_timeout(250)
            if not self._navegacoes and self.page.url == url_antes:
                break  # o último passo não leva a outra página: fim do tour
            self.page.wait_for_load_state("domcontentloaded")
            self.aguardar()
            destino = self.caminho_atual()
            # O tour pediu uma página com ?tour_continuo=1, mas o servidor redirecionou para outra
            pedidas = [urlparse(u).path for u in self._navegacoes if "tour_continuo=1" in u]
            if pedidas and "tour_continuo=1" not in self.page.url:
                percurso.append(f"{pedidas[-1]} ✗")
                problemas.append(f"o tour mandou para {pedidas[-1]}, mas a página redirecionou para {destino}: "
                                 "este perfil não tem acesso a ela e o tour termina ali")
                break
            percurso.append(destino)
            if any(m in self.texto_pagina().lower() for m in MARCAS_BLOQUEIO):
                problemas.append(f"o tour levou a uma página sem permissão para este perfil (acabou em {destino} com 'Acesso negado')")
                break
            if "tour_continuo=1" not in self.page.url:
                break

        if self.TOUR_ESPERADO and percurso != self.TOUR_ESPERADO:
            problemas.append(f"percurso {' → '.join(percurso)} (esperado {' → '.join(self.TOUR_ESPERADO)})")
        self.page.wait_for_timeout(800)
        if self.exibir_tour_no_banco():
            problemas.append("exibir_tour continua ligado depois do tour (o convite voltaria a aparecer)")

        if problemas:
            self.registrar("Tour", "Fazer o Tour Agora (encadeado)", FALHA, "; ".join(problemas),
                           esperado="Tour percorre as páginas do perfil sem parar, sem chaves cruas e desliga o convite no fim",
                           dica="Cada página do percurso precisa de iniciarTourDaPagina() que arranque com ?tour_continuo=1 e aponte para a próxima página que o perfil pode abrir.")
        else:
            self.registrar("Tour", "Fazer o Tour Agora (encadeado)", APROVADO, " → ".join(resumo) + f" → fim em {percurso[-1]}.", evidencia=False)

    def tour_nao_mostrar(self):
        if not self.abrir_convite_do_tour():
            self.registrar("Tour", "Não mostrar novamente", PULADO, "O convite não abriu.", evidencia=False)
            return
        self.page.locator('#modalTourInicial button:has-text("Não mostrar novamente")').click()
        self.page.wait_for_timeout(1200)
        fechou = not self.page.locator("#modalTourInicial").is_visible()
        desligado = not self.exibir_tour_no_banco()
        self.visitar("/dashboard")
        sumiu = not self.visivel("#modalTourInicial", timeout=2000)
        if fechou and desligado and sumiu:
            self.registrar("Tour", "Não mostrar novamente", APROVADO, "Convite fechado e desligado de vez.", evidencia=False)
        else:
            self.registrar("Tour", "Não mostrar novamente", FALHA,
                           f"fechou={fechou}, exibir_tour desligado={desligado}, convite sumiu no próximo acesso={sumiu}.",
                           esperado="Fechar o convite e nunca mais exibi-lo")

    def tour_botao_manual(self):
        com_tour, sem_tour, falhas = [], [], []
        for nome, caminho in self.paginas_navegaveis():
            self.visitar(caminho)
            botao = self.page.locator('button[onclick="iniciarTourDaPagina()"]').first
            if botao.count() == 0 or not botao.is_visible():
                falhas.append(f"{nome}: botão de tour não visível")
                continue
            self._dialogos.clear()
            botao.click()
            if self._esperar_tooltip(2500):
                passos = 0
                while passos < 40 and self.page.locator(".introjs-nextbutton").count():
                    passos += 1
                    if "introjs-donebutton" in (self.page.locator(".introjs-nextbutton").first.get_attribute("class") or ""):
                        break
                    self.page.locator(".introjs-nextbutton").first.click()
                    self.page.wait_for_timeout(250)
                self.page.keyboard.press("Escape")  # sai sem disparar o redirecionamento do último passo
                self.page.wait_for_timeout(300)
                com_tour.append(f"{nome} ({passos})")
            elif any("construído" in d for d in self._dialogos):
                sem_tour.append(nome)
            else:
                falhas.append(f"{nome}: o botão não abriu tour nem aviso")

        if falhas:
            self.registrar("Tour", "Botão de tour em cada página", FALHA, "; ".join(falhas))
        if sem_tour:
            self.registrar("Tour", "Páginas sem tour", ALERTA, "Mostram o aviso 'tour sendo construído': " + ", ".join(sem_tour),
                           esperado="Tour disponível em todas as páginas que o perfil acessa",
                           dica="Criar window.iniciarTourDaPagina() no template de cada página listada, no mesmo padrão de sessoes.html.")
        if com_tour:
            self.registrar("Tour", "Botão de tour em cada página", APROVADO, "Tour aberto em: " + ", ".join(com_tour), evidencia=False)

    def tour_traducoes(self):
        from traducoes import TEXTOS

        chaves = [k for k in TEXTOS["pt"] if k.startswith("tour_")]
        faltando = [f"{k} ({sigla})" for k in chaves for sigla in IDIOMAS if k not in TEXTOS[sigla]]
        iguais = [k for k in chaves if all(TEXTOS[s].get(k) == TEXTOS["pt"][k] for s in IDIOMAS) and len(TEXTOS["pt"][k]) > 12]
        if faltando or iguais:
            self.registrar("Tour", "Textos do tour em en/es", FALHA,
                           (f"chaves ausentes: {', '.join(faltando[:8])}. " if faltando else "")
                           + (f"sem tradução (igual ao pt): {', '.join(iguais[:8])}." if iguais else ""),
                           esperado="Todas as chaves tour_* traduzidas em en e es", arquivos=ARQUIVOS_POR_MODULO["Idioma"], evidencia=False)
        else:
            self.registrar("Tour", "Textos do tour em en/es", APROVADO, f"{len(chaves)} chaves tour_* traduzidas.", evidencia=False)

    # --------------------------------------------------------------------------
    # RECUPERAÇÃO DE SENHA (antes do login) — vale para todos os perfis
    # --------------------------------------------------------------------------
    def teste_recuperacao_senha(self):
        try:
            self.etapa("Recuperação de Senha", "E-mail inexistente", self.recuperacao_email_inexistente)
            self.etapa("Recuperação de Senha", "Perguntas do utilizador", self.recuperacao_mostra_perguntas)
            self.etapa("Recuperação de Senha", "Respostas erradas", self.recuperacao_respostas_erradas)
            self.etapa("Recuperação de Senha", "Fluxo completo com 2 de 3 acertos", self.recuperacao_fluxo_completo)
        finally:
            # Devolve a conta ao estado padrão: senha OmniTest, sem troca obrigatória e sem tentativas falhas
            self.page.goto(BASE_URL + "/logout", wait_until="domcontentloaded")
            preparar_usuario(self.chave_perfil)

    def perguntas_do_banco(self):
        from models import Usuario, SegurancaUsuario

        def ler():
            user = Usuario.query.filter_by(email=self.perfil["email"]).first()
            s = SegurancaUsuario.query.filter_by(usuario_id=user.id).first()
            return [s.pergunta_1, s.pergunta_2, s.pergunta_3]
        return consultar_banco(ler)

    def abrir_recuperacao(self, email):
        self.page.goto(BASE_URL + "/logout", wait_until="domcontentloaded")
        self.page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        self.page.locator('a[data-bs-target="#modalRecuperarSenha"]').click()
        modal = self.page.locator("#modalRecuperarSenha")
        modal.wait_for(state="visible")
        modal.locator('input[name="email_recuperacao"]').fill(email)
        modal.locator('button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")

    def mensagem_flash(self):
        alertas = self.page.locator(".alert").all_inner_texts()
        return " ".join(a.strip() for a in alertas)

    def responder_perguntas(self, respostas):
        for i, resposta in enumerate(respostas, 1):
            self.page.fill(f'input[name="resposta_{i}"]', resposta)
        self.page.locator('button:has-text("Validar Respostas")').click()
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()

    def recuperacao_email_inexistente(self):
        self.abrir_recuperacao("naoexiste_omnitest@local.com")
        msg = self.mensagem_flash()
        if "não encontrado" in msg.lower():
            self.registrar("Recuperação de Senha", "E-mail inexistente", APROVADO, msg, evidencia=False)
        else:
            self.registrar("Recuperação de Senha", "E-mail inexistente", FALHA, f"Mensagem recebida: '{msg or 'nenhuma'}'.",
                           esperado="Aviso 'E-mail não encontrado no sistema.' na tela de login")

    def recuperacao_mostra_perguntas(self):
        perguntas = self.perguntas_do_banco()
        self.abrir_recuperacao(self.perfil["email"])
        texto = self.texto_pagina()
        faltando = [p for p in perguntas if p not in texto]
        if self.page.locator('input[name="resposta_1"]').count() == 0:
            self.registrar("Recuperação de Senha", "Perguntas do utilizador", FALHA,
                           f"A tela de perguntas não abriu (rota {self.caminho_atual()}; mensagem: '{self.mensagem_flash()}').",
                           esperado="Tela perguntas_seguranca.html com as 3 perguntas cadastradas")
        elif faltando:
            self.registrar("Recuperação de Senha", "Perguntas do utilizador", FALHA, "Perguntas ausentes: " + " | ".join(faltando),
                           esperado="As 3 perguntas cadastradas pelo utilizador")
        else:
            self.registrar("Recuperação de Senha", "Perguntas do utilizador", APROVADO, "As 3 perguntas cadastradas foram exibidas.", evidencia=False)

    def recuperacao_respostas_erradas(self):
        self.abrir_recuperacao(self.perfil["email"])
        self.responder_perguntas(["errada-1", "errada-2", "errada-3"])
        msg = self.mensagem_flash()
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        ainda_deslogado = self.caminho_atual() == "/"
        if "2 acertos" in msg and ainda_deslogado:
            self.registrar("Recuperação de Senha", "Respostas erradas", APROVADO, "Acesso negado com 0 de 3 acertos.", evidencia=False)
        else:
            self.registrar("Recuperação de Senha", "Respostas erradas", FALHA,
                           f"Mensagem: '{msg or 'nenhuma'}'; sessão aberta: {not ainda_deslogado}.",
                           esperado="Aviso de mínimo de 2 acertos e nenhuma sessão aberta")

    def recuperacao_fluxo_completo(self):
        # 2 de 3 corretas, uma delas em maiúsculas e com espaços: o app normaliza com strip().lower()
        self.abrir_recuperacao(self.perfil["email"])
        self.responder_perguntas([f"  {RESPOSTA_SEGURANCA.upper()} ", RESPOSTA_SEGURANCA, "errada"])
        if self.caminho_atual() != "/trocar-senha":
            self.registrar("Recuperação de Senha", "2 de 3 acertos liberam a troca", FALHA,
                           f"Ficou em {self.caminho_atual()} — mensagem: '{self.mensagem_flash()}'.",
                           esperado="Redirecionar para /trocar-senha com 2 ou mais acertos")
            return
        self.registrar("Recuperação de Senha", "2 de 3 acertos liberam a troca", APROVADO, "Redirecionado para /trocar-senha.", evidencia=False)

        self.page.fill('input[name="nova_senha"]', "fraca123")
        self.page.locator('form[action$="/trocar-senha"] button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        if self.caminho_atual() == "/trocar-senha" and self.page.locator(".alert-danger").count():
            self.registrar("Recuperação de Senha", "Senha fraca recusada", APROVADO, evidencia=False)
        else:
            self.registrar("Recuperação de Senha", "Senha fraca recusada", FALHA, "A senha 'fraca123' foi aceita.",
                           esperado="Recusar senhas sem 10 caracteres, maiúscula, minúscula, número e especial")

        senha_temporaria = f"Omni#{self.carimbo}Aa"
        self.page.fill('input[name="nova_senha"]', senha_temporaria)
        self.page.locator('form[action$="/trocar-senha"] button[type="submit"]').click()
        self.page.wait_for_load_state("domcontentloaded")
        self.lidar_com_bloqueios_de_fluxo()
        if self.caminho_atual() == "/dashboard":
            self.registrar("Recuperação de Senha", "Nova senha forte aceita", APROVADO, "Entrou no Painel Geral.", evidencia=False)
        else:
            self.registrar("Recuperação de Senha", "Nova senha forte aceita", FALHA, f"Ficou em {self.caminho_atual()}.",
                           esperado="Gravar a nova senha e abrir o /dashboard")
            return

        # A senha antiga deixa de funcionar: primeiro a verdade do banco, depois o comportamento da tela
        from app import bcrypt as _bcrypt
        from models import Usuario as _Usuario
        trocou_no_banco = consultar_banco(lambda: not _bcrypt.check_password_hash(
            _Usuario.query.filter_by(email=self.perfil["email"]).first().senha, SENHA_PADRAO))
        self.page.goto(BASE_URL + "/logout", wait_until="domcontentloaded")
        self.page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        self.page.fill('input[name="email"]', self.perfil["email"])
        self.page.fill('input[name="senha"]', SENHA_PADRAO)
        self.page.locator('form:has(input[name="senha"]) button[type="submit"]').first.click()
        self.page.wait_for_load_state("domcontentloaded")
        self.aguardar()
        recusada_na_tela = self.caminho_atual() == "/" and "incorretos" in self.texto_pagina()
        if not trocou_no_banco:
            self.registrar("Recuperação de Senha", "Senha antiga invalidada", FALHA, "A nova senha não foi gravada no banco.",
                           esperado="trocar_senha_obrigatoria grava o novo hash da senha")
        elif recusada_na_tela:
            self.registrar("Recuperação de Senha", "Senha antiga invalidada", APROVADO, evidencia=False)
        else:
            self.registrar("Recuperação de Senha", "Senha antiga invalidada", FALHA, "A senha anterior ainda permite entrar.",
                           esperado="Apenas a nova senha autentica após a recuperação")

    # --------------------------------------------------------------------------
    # Ponto de extensão: cada agente de perfil implementa os seus testes
    # --------------------------------------------------------------------------
    def testes_pre_login(self):
        """Testes feitos ainda deslogado. Padrão: recuperação de senha pelas perguntas de segurança."""
        if self.TESTAR_RECUPERACAO:
            self.teste_recuperacao_senha()

    def testes_especificos(self):
        pass

    # --------------------------------------------------------------------------
    # Execução completa
    # --------------------------------------------------------------------------
    def executar(self):
        print("\n==================================================")
        print(f"  🤖 [OMNITEST] Agente do perfil: {self.perfil['tipo']}")
        print(f"     {self.perfil['email']}  →  {BASE_URL}")
        print("==================================================")
        print("🧭 Roteiro deste agente:")
        for i, passo in enumerate(self.roteiro(), 1):
            print(f"   {i:>2}. {passo}")
        print()

        if self.preparar:
            try:
                for nota in preparar_usuario(self.chave_perfil, self.primeiro_acesso):
                    self.registrar("Preparação", "Utilizador de teste", ALERTA, nota, evidencia=False)
            except Exception as e:
                self.registrar("Preparação", "Utilizador de teste", FALHA, f"Exceção: {_celula(e)}", evidencia=False)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=self.lento)
            # Contexto próprio = cookies próprios: nenhum agente herda a sessão de outro
            self.context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="pt-BR")
            self.page = self.context.new_page()
            self.page.set_default_timeout(10000)
            if not self.headless:
                self.context.add_init_script(self.JS_FAIXA)
            self._ligar_sensores()

            self.etapa("Pré-login", "Testes antes do login", self.testes_pre_login)
            print("\n🔎 Autenticação › Login com e-mail e senha")
            try:
                self.teste_login()
            except Exception as e:
                self.registrar("Autenticação", "Login com e-mail e senha", FALHA, _celula(e))
                browser.close()
                return self.gerar_relatorio()

            self.etapa("Regras de Entrada", "Onboarding e frequência", self.teste_regras_de_entrada)
            self.etapa("Menu Superior", "Conferência do menu", self.teste_menu)
            self.teste_matriz_de_acesso()
            self.etapa(self.perfil["tipo"], "Testes específicos do perfil", self.testes_especificos)
            self.etapa("Tour", "Tour guiado", self.teste_tour)
            self.etapa("Tema", "Temas em todas as páginas", self.teste_temas_todas_paginas)
            self.etapa("Idioma", "Idiomas em todas as páginas", self.teste_idiomas_todas_paginas)
            self.etapa("Autenticação", "Logout encerra a sessão", self.teste_logout)

            if self.pausar and not self.headless:
                self.anunciar("Fim dos testes — pressione Enter no terminal para fechar")
                input("\n⏸️  Testes concluídos. Pressione Enter para fechar o navegador...")
            browser.close()

        if self.escrita:
            try:
                print(f"\n🧹 Limpeza do modo escrita: {limpar_dados_de_teste(self.chave_perfil)}")
            except Exception as e:
                self.registrar("Limpeza", "Apagar dados [OmniTest]", ALERTA, f"Não foi possível limpar: {_celula(e)}", evidencia=False)

        return self.gerar_relatorio()

    # --------------------------------------------------------------------------
    # Relatório
    # --------------------------------------------------------------------------
    def gerar_relatorio(self):
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        contagem = {s: sum(1 for r in self.resultados if r["status"] == s) for s in (APROVADO, FALHA, ALERTA, PULADO)}
        base_nome = f"Relatorio_OmniTest_{self.chave_perfil}_{self.carimbo}"
        caminho_md = os.path.join(PASTA_RELATORIOS, base_nome + ".md")

        linhas = [
            f"# 📊 Relatório OmniTest — Perfil {self.perfil['tipo']}\n",
            f"**Data da Execução:** {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}  ",
            f"**Utilizador:** `{self.perfil['email']}`  ",
            f"**Ambiente:** {BASE_URL}  ",
            f"**Modo escrita:** {'Ligado' if self.escrita else 'Desligado (somente leitura)'}\n",
            f"**Resumo:** {contagem[APROVADO]} aprovados · {contagem[FALHA]} falhas · {contagem[ALERTA]} alertas · {contagem[PULADO]} pulados\n",
            "---\n",
            "## 🔍 Checklist de Homologação\n",
            "| Módulo | Ação Testada | Status | Observações / Evidências |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for r in self.resultados:
            obs = _celula(r["detalhe"])
            if r["evidencia"]:
                obs += f" [📷]({os.path.relpath(r['evidencia'], PASTA_RELATORIOS).replace(os.sep, '/')})"
            linhas.append(f"| {_celula(r['modulo'])} | {_celula(r['acao'])} | {r['status']} | {obs} |")

        def secao(titulo, status, detalhado=False):
            itens = [r for r in self.resultados if r["status"] == status]
            linhas.append(f"\n## {titulo}\n")
            if not itens:
                linhas.append("- Nenhum item.")
            for i, r in enumerate(itens, 1):
                if not detalhado:
                    linhas.append(f"- **{r['modulo']} › {r['acao']}**" + (f": {_celula(r['detalhe'])}" if r["detalhe"] else ""))
                    continue
                linhas.append(f"### {i}. {r['modulo']} › {r['acao']}")
                linhas.extend(f"- {linha}" for linha in self.detalhes_do_problema(r))
                linhas.append("")

        linhas.append("\n---")
        linhas.append("\n## 🧭 Roteiro deste agente\n")
        linhas += [f"{i}. {passo}" for i, passo in enumerate(self.roteiro(), 1)]
        secao("🔴 Falha Encontrada (O que precisa corrigir)", FALHA, detalhado=True)
        secao("💡 Sugestão de Melhoria de UX/UI (Alertas)", ALERTA, detalhado=True)
        secao("🟢 Aprovado (O que funcionou)", APROVADO)
        secao("⏭️ Não testado (falta de dados ou pré-requisito)", PULADO)

        caminho_prompt = self.gerar_prompt_gemini()
        if caminho_prompt:
            linhas.append(f"\n---\n\n## 🤖 Prompt de correção para o Gemini\n\n[{os.path.basename(caminho_prompt)}]({os.path.basename(caminho_prompt)})")

        with open(caminho_md, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        # Detalhes prontos de cada ❌/⚠️: o orquestrador usa-os no prompt consolidado
        for r in self.resultados:
            if r["status"] in (FALHA, ALERTA):
                r["detalhes"] = self.detalhes_do_problema(r)
        with open(os.path.join(PASTA_RELATORIOS, base_nome + ".json"), "w", encoding="utf-8") as f:
            json.dump({"perfil": self.perfil["tipo"], "chave": self.chave_perfil, "contagem": contagem,
                       "relatorio": caminho_md, "prompt_gemini": caminho_prompt, "resultados": self.resultados},
                      f, ensure_ascii=False, indent=2)

        print("\n==================================================")
        print(f"✅ Agente {self.perfil['tipo']} concluído: {contagem[APROVADO]} ✅  {contagem[FALHA]} ❌  {contagem[ALERTA]} ⚠️")
        print(f"   Relatório: {caminho_md}")
        if caminho_prompt:
            print(f"   Prompt para o Gemini: {caminho_prompt}")
        print("==================================================\n")
        return contagem[FALHA] == 0

    def detalhes_do_problema(self, r):
        """Linhas de detalhe de um ❌/⚠️: usadas no relatório e no prompt do Gemini."""
        caminho = urlparse(r.get("url") or "").path or "—"
        linhas = [f"**Observado:** {r['detalhe'] or 'sem detalhe'}"]
        if r.get("esperado"):
            linhas.append(f"**Esperado:** {r['esperado']}")
        linhas.append(f"**Como reproduzir:** entrar como `{self.perfil['email']}` (senha de teste), abrir `{caminho}` "
                      f"e executar «{r['acao']}» — registado às {r.get('hora', '?')}")
        if r.get("erros_js"):
            linhas.append("**Erros de JavaScript no momento:** " + " | ".join(_celula(e) for e in r["erros_js"]))
        if r.get("dica"):
            linhas.append(f"**Diagnóstico do agente:** {r['dica']}")
        if r.get("arquivos"):
            linhas.append(f"**Onde olhar:** {r['arquivos']}")
        if r.get("evidencia"):
            rel = os.path.relpath(r["evidencia"], PASTA_RELATORIOS).replace(os.sep, "/")
            linhas.append(f"**Evidência:** [{os.path.basename(rel)}]({rel})")
        return linhas

    # Passos comuns a todos os perfis; cada agente acrescenta os seus em ROTEIRO
    ROTEIRO_COMUM_INICIO = [
        "Recuperação de senha: e-mail inexistente, perguntas do utilizador, respostas erradas, 2 de 3 acertos, senha fraca, nova senha e senha antiga invalidada",
        "Login com e-mail e senha",
        "Regras de entrada: onboarding LGPD e presença diária, conforme o perfil",
        "Menu superior: itens obrigatórios visíveis, itens restritos ocultos e botão Sair",
        "Matriz de acesso: cada rota permitida abre sem erro (500, Jinja cru, chaves de tradução, erros JS) e cada rota restrita é bloqueada",
    ]
    ROTEIRO_COMUM_FIM = [
        "Tour: convite, Lembrar Depois, tour encadeado, Não mostrar novamente, botão de tour em cada página e textos em en/es",
        "Tema: claro, escuro, futurista e vintage em todas as páginas (data-theme, blocos claros, contraste e consistência)",
        "Idioma: inglês e espanhol no menu e em todas as páginas (<html lang> e textos que ficaram em português)",
        "Logout encerra a sessão",
    ]
    ROTEIRO = []

    def roteiro(self):
        inicio = self.ROTEIRO_COMUM_INICIO if self.TESTAR_RECUPERACAO else self.ROTEIRO_COMUM_INICIO[1:]
        return inicio + self.ROTEIRO + self.ROTEIRO_COMUM_FIM

    def gerar_prompt_gemini(self):
        """Transforma cada ❌ e ⚠️ num pedido de correção pronto para colar no Gemini."""
        problemas = [r for r in self.resultados if r["status"] in (FALHA, ALERTA) and r["modulo"] != "Preparação"]
        if not problemas:
            return None
        problemas.sort(key=lambda r: r["status"] != FALHA)
        linhas = cabecalho_prompt_gemini(f"Perfil {self.perfil['tipo']}", f"o perfil **{self.perfil['tipo']}**",
                                         problemas, f"python agentes_omnitest/agente_{self.chave_perfil}.py")
        for i, r in enumerate(problemas, 1):
            tipo = "FALHA" if r["status"] == FALHA else "ALERTA (melhoria)"
            linhas.append(f"### {i}. {tipo} — {r['modulo']} › {r['acao']}")
            linhas += [f"- {linha}" for linha in self.detalhes_do_problema(r)]
            linhas.append("")

        caminho = os.path.join(PASTA_RELATORIOS, f"Prompt_Gemini_{self.chave_perfil}_{self.carimbo}.md")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        return caminho


def executar_cli(classe_agente):
    """Ponto de entrada comum: python agentes_omnitest/agente_<perfil>.py [opções]"""
    parser = argparse.ArgumentParser(description=f"OmniTest — agente do perfil {PERFIS[classe_agente.chave_perfil]['tipo']}")
    parser.add_argument("--headless", action="store_true", help="Executa sem abrir a janela do navegador.")
    parser.add_argument("--lento", type=int, default=400, help="Pausa entre ações em ms (padrão 400; use 0 para máxima velocidade).")
    parser.add_argument("--escrita", action="store_true",
                        help="Liga os testes que gravam dados (tickets, horas de voluntariado); o que for criado é apagado no fim.")
    parser.add_argument("--primeiro-acesso", action="store_true", help="Reinicia termo, frequência de hoje e tour para testar a primeira entrada.")
    parser.add_argument("--sem-preparo", action="store_true", help="Não ajusta o utilizador de teste no banco antes de começar.")
    parser.add_argument("--pausar", action="store_true", help="Mantém o navegador aberto no fim até você pressionar Enter.")
    args = parser.parse_args()

    agente = classe_agente(headless=args.headless, lento=args.lento, escrita=args.escrita, preparar=not args.sem_preparo,
                           primeiro_acesso=args.primeiro_acesso)
    agente.pausar = args.pausar
    sys.exit(0 if agente.executar() else 1)
