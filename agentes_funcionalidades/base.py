# -*- coding: utf-8 -*-
"""
BASE DOS AGENTES DE FUNCIONALIDADES
===================================
Cada agente representa um perfil e segue o fluxo real da plataforma (abordagem híbrida):
  - executa as funções enviando os MESMOS formulários das telas, com login real, CSRF e as permissões do perfil;
  - confere o resultado no banco de dados e nas páginas;
  - tira um print da tela de cada etapa (evidência para o PDF e para o monitor ao vivo);
  - registra cada teste como Aprovado / Falha / Alerta, com a regra de negócio validada;
  - passa ao próximo agente o que criou (contexto.json: usuários, senhas, ids), como numa corrida de revezamento.
Tudo o que é criado leva a marca [Funcional] e e-mails *_funcional@local.com; o Gerente remove ao final.
"""
import os
import re
import sys
import json
import time
import uuid
import secrets
import string
import mimetypes
from datetime import datetime
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler
from urllib.error import HTTPError

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)
for _fluxo in (sys.stdout, sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.environ.get("OMNITEST_URL", "http://127.0.0.1:5000").rstrip("/")
PASTA_RELATORIOS = os.path.join(RAIZ_PROJETO, "Agent Reports", "Funcionalidades")
PASTA_AO_VIVO = os.environ.get("FUNC_AO_VIVO", "")
ARQUIVO_CONTEXTO = os.environ.get("FUNC_CONTEXTO", os.path.join(PASTA_RELATORIOS, "contexto.json"))
MARCA = "[Funcional]"
DOMINIO = "funcional@local.com"
APROVADO, FALHA, ALERTA = "Aprovado", "Falha", "Alerta"
SEVERIDADES = ["Crítica", "Alta", "Média", "Baixa", "Informativa"]
CATEGORIAS = {"FLX": "Fluxo de negócio", "REG": "Regra de negócio", "PER": "Permissão do perfil", "VAL": "Validação de dados",
              "INT": "Integridade dos dados", "ACE": "Primeiro acesso e onboarding",
              "UX": "Telas traduzidas e acessíveis"}
# Layout medido no navegador: largura do computador e do celular, e quantas páginas cada perfil mede (as já medidas por
# um agente anterior da cadeia ficam de fora, para a cadeia não repetir o mesmo trabalho)
LARGURA_COMPUTADOR, LARGURA_CELULAR = 1366, 375
LIMITE_PAGINAS_LAYOUT = 30
LIMITE_PAGINAS_CONTRASTE = 15  # por perfil, em cada um dos 4 temas (as páginas já medidas por outro perfil ficam de fora)
# Abre cada modal da página e mede: topo, miolo e rodapé dentro da caixa (.modal-content / .card); página sem rolagem lateral
JS_LAYOUT = """() => {
  const fora = (el, caixa) => { const a = el.getBoundingClientRect(), b = caixa.getBoundingClientRect();
    return a.width > 0 && b.width > 0 && (a.left < b.left - 1 || a.right > b.right + 1); };
  const nome = el => { const c = el.closest('[id]'); return (c ? '#' + c.id.replace(/\\d+/g, 'N') : '') + ' .' + [...el.classList].filter(x => /^(modal|card)-/.test(x))[0]; };
  const achados = new Set();
  document.querySelectorAll('.card-header, .card-body, .card-footer').forEach(el => {
    const caixa = el.closest('.card'); if (caixa && fora(el, caixa)) achados.add(nome(el)); });
  const vistos = new Set();
  document.querySelectorAll('.modal').forEach(m => {
    const tipo = (m.id || '').replace(/\\d+/g, 'N'); if (vistos.has(tipo) || vistos.size >= 12) return; vistos.add(tipo);
    const antes = [m.style.display, m.className];
    m.style.display = 'block'; m.classList.add('show');
    m.querySelectorAll('.modal-header, .modal-body, .modal-footer').forEach(el => {
      const caixa = el.closest('.modal-content'); if (caixa && fora(el, caixa)) achados.add(nome(el)); });
    m.style.display = antes[0]; m.className = antes[1];
  });
  const raiz = document.documentElement;
  return {caixas: [...achados], rolagem_lateral: raiz.scrollWidth > raiz.clientWidth + 1, largura: raiz.scrollWidth};
}"""


def regra_da_plataforma(chave):
    """Valor atual de uma regra parametrizada (Sistema › Parâmetros de regras), lido como a plataforma lê."""
    from app import app
    from regras_negocio import regra
    with app.app_context():
        return regra(chave)


def senha_forte():
    """Senha aleatória que atende à política da plataforma (tamanho mínimo parametrizado, maiúscula, minúscula, número e especial)."""
    base = [secrets.choice(string.ascii_uppercase), secrets.choice(string.ascii_lowercase), secrets.choice(string.digits), secrets.choice("#@!%&*")]
    base += [secrets.choice(string.ascii_letters + string.digits) for _ in range(max(10, int(regra_da_plataforma("senha_min_caracteres"))))]
    secrets.SystemRandom().shuffle(base)
    return "".join(base)


def ler_contexto():
    try:
        with open(ARQUIVO_CONTEXTO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"usuarios": {}, "ids": {}}


def gravar_contexto(contexto):
    os.makedirs(os.path.dirname(ARQUIVO_CONTEXTO), exist_ok=True)
    temporario = ARQUIVO_CONTEXTO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(contexto, f, ensure_ascii=False, indent=1)
    os.replace(temporario, ARQUIVO_CONTEXTO)


class _SemRedirecionar(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Cliente:
    """Navegador HTTP com cookies próprios. Envia o token CSRF como a página faria e não segue redirecionamentos
    (para ler para onde a plataforma mandou o usuário)."""

    def __init__(self):
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar), _SemRedirecionar)
        self._token = ""

    def token(self):
        if not self._token:
            self.pedir("GET", "/")
        return self._token

    def pedir(self, metodo, caminho, form=None, arquivos=None, seguir=False, json_corpo=None):
        """json_corpo: envia JSON (como o fetch das telas), com o token CSRF no cabeçalho X-CSRFToken."""
        url = caminho if caminho.startswith("http") else BASE_URL + caminho
        cab, dados = {"User-Agent": "MentoriaAgenteFuncional/1.0"}, None
        if json_corpo is not None:
            cab["Content-Type"] = "application/json"
            cab["X-CSRFToken"] = self.token()
            dados = json.dumps(json_corpo).encode()
        elif metodo != "GET":
            form = dict(form or {})
            form.setdefault("csrf_token", self.token())
            if arquivos:
                limite = uuid.uuid4().hex
                partes = []
                for chave, valor in form.items():
                    for v in (valor if isinstance(valor, (list, tuple)) else [valor]):
                        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{chave}"\r\n\r\n{v}\r\n'.encode())
                for chave, (nome, conteudo) in arquivos.items():
                    tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
                    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{chave}"; filename="{nome}"\r\n'
                                  f'Content-Type: {tipo}\r\n\r\n'.encode() + conteudo + b"\r\n")
                dados = b"".join(partes) + f"--{limite}--\r\n".encode()
                cab["Content-Type"] = f"multipart/form-data; boundary={limite}"
            else:
                dados = urlencode(form, doseq=True).encode()
                cab["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            resposta = self.opener.open(Request(url, data=dados, headers=cab, method=metodo), timeout=60)
            status, headers, corpo = resposta.status, resposta.headers, resposta.read(5_000_000)
        except HTTPError as e:
            status, headers, corpo = e.code, e.headers, e.read(5_000_000)
        texto = corpo.decode("utf-8", errors="replace")
        achado = re.search(r'name="csrf-token" content="([^"]+)"', texto)
        if achado:
            self._token = achado.group(1)
        destino = urlparse(headers.get("Location") or "").path if status in (301, 302, 303) else None
        if seguir and destino:
            return self.pedir("GET", headers["Location"], seguir=True)
        return status, destino, texto

    def cookie_sessao(self):
        return next((c.value for c in self.jar if c.name == "session"), None)


def mensagens(html):
    """Textos dos avisos flash da página (alertas com botão de fechar; caixas fixas de conteúdo não contam)."""
    blocos = re.findall(r'<div class="alert alert-\w+ alert-dismissible[^"]*"[^>]*>(.*?)<button', html, re.S)
    return [" ".join(re.sub(r"<[^>]+>", " ", b).split()) for b in blocos]


class AgenteFuncional:
    chave = ""
    nome = ""
    perfil = ""
    ROTEIRO = []
    PAGINA_SONDA = "/projetos"  # página usada para conferir os portões do onboarding (termo e trilha)

    def __init__(self):
        self.testes = []
        self.feed = []
        self.etapa_atual = ""
        self.carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.inicio = time.time()
        self.contexto = ler_contexto()
        self.aprendizados = []
        self.regras = {}
        self.pasta_evidencias = os.path.join(PASTA_RELATORIOS, "evidencias", f"{self.contexto.get('execucao', self.carimbo)}_{self.chave}")
        os.makedirs(self.pasta_evidencias, exist_ok=True)
        self._pw = self._navegador = self._pagina = None
        self.cliente = None

    # ------------------------------------------------------------------ registro
    def etapa(self, texto):
        self.etapa_atual = texto
        self.log(f"▶ {texto}")

    def log(self, texto):
        linha = f"{datetime.now().strftime('%H:%M:%S')}  {texto}"
        print(linha, flush=True)
        self.feed = (self.feed + [linha])[-40:]
        self.publicar()

    def registrar(self, titulo, resultado, categoria, detalhe, esperado="", severidade="Média", recomendacao="", evidencia=None):
        item = {"id": f"{self.chave.upper()[:3]}-{len(self.testes) + 1:03d}", "etapa": self.etapa_atual, "titulo": titulo, "resultado": resultado,
                "categoria": CATEGORIAS.get(categoria, categoria), "detalhe": str(detalhe)[:1200], "esperado": esperado,
                "severidade": severidade if resultado != APROVADO else "", "recomendacao": recomendacao, "evidencia": evidencia,
                "hora": datetime.now().strftime("%H:%M:%S")}
        self.testes.append(item)
        simbolo = {"Aprovado": "✓", "Falha": "✗", "Alerta": "⚠"}[resultado]
        self.log(f"{simbolo} [{resultado}{' · ' + severidade if resultado != APROVADO else ''}] {titulo}")
        return item

    def confere(self, condicao, titulo, categoria, detalhe_ok, detalhe_falha, esperado, severidade="Média", recomendacao="", print_de=None, alerta=False):
        """Valida uma regra: Aprovado se 'condicao'; senão Falha (ou Alerta). Tira o print da página 'print_de' se informada."""
        evidencia = self.print(print_de, titulo) if print_de else None
        if condicao:
            return self.registrar(titulo, APROVADO, categoria, detalhe_ok, esperado, evidencia=evidencia)
        return self.registrar(titulo, ALERTA if alerta else FALHA, categoria, detalhe_falha, esperado, severidade, recomendacao, evidencia)

    def contagem(self):
        return {r: sum(1 for t in self.testes if t["resultado"] == r) for r in (APROVADO, FALHA, ALERTA)}

    def publicar(self):
        if not PASTA_AO_VIVO:
            return
        os.makedirs(PASTA_AO_VIVO, exist_ok=True)
        dados = {"chave": self.chave, "nome": self.nome, "etapa": self.etapa_atual, "contagem": self.contagem(),
                 "verificacoes": len(self.testes), "feed": self.feed[-30:], "atualizado": datetime.now().isoformat(timespec="seconds")}
        temporario = os.path.join(PASTA_AO_VIVO, "agente.json.tmp")
        try:
            with open(temporario, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
            os.replace(temporario, os.path.join(PASTA_AO_VIVO, "agente.json"))
        except OSError:
            pass

    # ------------------------------------------------------------------ banco (só para conferir resultados)
    def banco(self, funcao):
        from app import app
        with app.app_context():
            return funcao()

    # ------------------------------------------------------------------ evidências (prints)
    def _navegador_com_sessao(self):
        """Página do Chromium com a mesma sessão (cookie) do agente."""
        if self._pagina is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            from navegador import abrir_chromium
            self._navegador = abrir_chromium(self._pw)
            self._contexto_nav = self._navegador.new_context(viewport={"width": LARGURA_COMPUTADOR, "height": 860})
            self._pagina = self._contexto_nav.new_page()
        sessao = self.cliente.cookie_sessao() if self.cliente else None
        if sessao:
            self._contexto_nav.clear_cookies()
            self._contexto_nav.add_cookies([{"name": "session", "value": sessao, "url": BASE_URL}])
        return self._pagina

    def layout_no_navegador(self, caminhos, base):
        """Mede o layout de verdade: cada página aberta pelo perfil, no computador e no celular; abre cada modal e confere se
        topo, miolo e rodapé ficam dentro da caixa (o miolo mais largo que o topo é o layout estourado)."""
        vistas = set(self.contexto.get("layout_paginas_medidas") or [])
        caminhos = [c for c in dict.fromkeys(caminhos) if c not in vistas][:LIMITE_PAGINAS_LAYOUT]
        if not caminhos:
            return
        self.etapa(f"Layout no navegador ({base}): modais, cartões e rolagem lateral")
        caixas, lateral_pc, lateral_celular, medidas = [], [], [], 0
        try:
            pagina = self._navegador_com_sessao()
            for largura, lista in ((LARGURA_COMPUTADOR, lateral_pc), (LARGURA_CELULAR, lateral_celular)):
                pagina.set_viewport_size({"width": largura, "height": 860 if largura == LARGURA_COMPUTADOR else 812})
                for caminho in caminhos:
                    try:
                        pagina.goto(BASE_URL + caminho, wait_until="domcontentloaded", timeout=30000)
                        pagina.wait_for_timeout(150)
                        r = pagina.evaluate(JS_LAYOUT)
                    except Exception as e:
                        self.log(f"(layout de {caminho} não medido: {e.__class__.__name__})")
                        continue
                    medidas += 1
                    if r["rolagem_lateral"]:
                        lista.append(f"{caminho} ({r['largura']}px)")
                    if largura == LARGURA_COMPUTADOR:
                        caixas += [f"{caminho} {c}" for c in r["caixas"]]
            pagina.set_viewport_size({"width": LARGURA_COMPUTADOR, "height": 860})
        except Exception as e:
            self.log(f"(navegador indisponível para medir o layout: {e.__class__.__name__})")
            return
        self.contexto["layout_paginas_medidas"] = sorted(vistas | set(caminhos))
        self.confere(not caixas, f"Modais e cartões sem layout estourado ({len(caminhos)} página(s) de {base})", "UX",
                     "Topo, miolo e rodapé de cada modal e cartão ficam dentro da caixa.",
                     "Parte mais larga que a caixa: " + "; ".join(caixas[:12]),
                     "Miolo, topo e rodapé com a mesma largura da caixa", "Média",
                     "Tirar a grade 'row' da própria parte (modal-body/card-body) e pôr numa div dentro dela.", alerta=True)
        self.confere(not lateral_pc, f"Páginas sem rolagem lateral no computador ({LARGURA_COMPUTADOR}px)", "UX",
                     f"{len(caminhos)} página(s) cabem na largura da tela.", "Rolagem lateral em: " + "; ".join(lateral_pc[:12]),
                     "Nada passa da largura da tela", "Média", "Procurar a grade 'row' sem container ou elemento com largura fixa.",
                     alerta=True)
        self.confere(not lateral_celular, f"Páginas sem rolagem lateral no celular ({LARGURA_CELULAR}px)", "UX",
                     f"{len(caminhos)} página(s) cabem no celular.", "Rolagem lateral em: " + "; ".join(lateral_celular[:12]),
                     "A plataforma funciona no celular", "Baixa",
                     "Tabelas dentro de .table-responsive; grupos de botões com flex-wrap; larguras fixas trocadas por max-width.",
                     alerta=True)
        self.contraste_no_navegador(caminhos, base)

    def contraste_no_navegador(self, caminhos, base):
        """Contraste do texto (WCAG 2.2: 4,5:1, ou 3:1 no texto grande) nas mesmas páginas, em CADA tema da plataforma
        (claro, escuro, futurista, vintage), com as janelas abertas também: a cor da letra tem de combinar com o fundo do
        tema que a pessoa escolheu, não só com o tema em que a tela foi desenhada."""
        import contraste
        self.etapa(f"Contraste do texto em todos os temas ({base})")
        try:
            pagina = self._navegador_com_sessao()
            pagina.set_viewport_size({"width": LARGURA_COMPUTADOR, "height": 860})
            pagina.goto(BASE_URL + caminhos[0], wait_until="domcontentloaded", timeout=30000)
            saida = contraste.auditar(pagina, BASE_URL, caminhos[:LIMITE_PAGINAS_CONTRASTE])
        except Exception as e:
            self.log(f"(navegador indisponível para medir o contraste: {e.__class__.__name__})")
            return
        for tema, (medidos, ruins) in contraste.resumo(saida).items():
            piores = sorted(((f["razao"], c, f) for c, r in saida[tema].items() for f in r["falhas"]), key=lambda x: x[0])
            exemplos = "; ".join(f"{c}{' ' + f['janela'] if f.get('janela') else ''} “{f['texto'][:40]}” {f['razao']}:1 "
                                 f"({f['letra']} em {f['fundo']})" for _, c, f in piores[:10])
            self.confere(not ruins, f"Texto legível no tema {tema} ({len(saida[tema])} página(s) de {base})", "UX",
                         f"{medidos} textos com contraste de pelo menos {contraste.CONTRASTE_MINIMO_TEXTO}:1 "
                         f"({contraste.CONTRASTE_MINIMO_TEXTO_GRANDE}:1 no texto grande).",
                         f"{ruins} de {medidos} textos abaixo do mínimo: {exemplos}",
                         "A cor de cada texto vem de um papel do tema (texto, texto secundário, ação, estado) e passa no "
                         "contraste WCAG em todos os temas", "Média",
                         "Trocar a cor fixa (text-dark, text-white, bg-white, style=\"color:…\") pelo papel do tema; conferir "
                         "a paleta com tema_plataforma.py.", alerta=True)

    def print(self, caminho, titulo):
        """Abre a página com a mesma sessão do agente e salva o print (também vira o quadro ao vivo do hub)."""
        try:
            self._navegador_com_sessao()
            if self._pagina.url.split("#")[0] == (BASE_URL + caminho).split("#")[0]:
                # Mesma página com outra âncora (#card...): o navegador só rolaria a tela; força o carregamento de novo
                self._pagina.goto("about:blank")
            self._pagina.goto(BASE_URL + caminho, wait_until="domcontentloaded", timeout=30000)
            self._pagina.wait_for_timeout(400)
            nome = f"{len(os.listdir(self.pasta_evidencias)) + 1:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', titulo)[:50]}.png"
            destino = os.path.join(self.pasta_evidencias, nome)
            self._pagina.screenshot(path=destino)
            if PASTA_AO_VIVO:
                import shutil
                shutil.copyfile(destino, os.path.join(PASTA_AO_VIVO, "frame.png"))
                with open(os.path.join(PASTA_AO_VIVO, "frame.json"), "w", encoding="utf-8") as f:
                    json.dump({"url": caminho, "titulo": titulo, "agente": self.nome}, f, ensure_ascii=False)
            return os.path.relpath(destino, PASTA_RELATORIOS)
        except Exception as e:
            self.log(f"(print não gerado: {e.__class__.__name__})")
            return None

    def fechar_navegador(self):
        try:
            if self._navegador:
                self._navegador.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ login e primeiro acesso
    def entrar(self, email, senha):
        self.email_logado = email
        self.cliente = Cliente()
        status, destino, _ = self.cliente.pedir("POST", "/", {"email": email, "senha": senha})
        return status, destino

    def primeiro_acesso(self, email, senha, nova_senha=None):
        """Login + fluxo obrigatório do primeiro acesso: troca de senha, perguntas de segurança, termo e trilha do TCC.
        Valida cada portão (a plataforma não deixa pular etapas). Devolve a senha final."""
        self.etapa("Primeiro acesso e onboarding")
        status, destino = self.entrar(email, senha)
        self.confere(status in (302, 303) and destino != "/", "Login com as credenciais criadas", "ACE",
                     f"Login aceito; a plataforma levou para {destino}.", f"Login recusado (HTTP {status}, destino {destino}).",
                     "Usuário criado pelo perfil anterior entra na plataforma", "Crítica")
        if destino == "/trocar-senha":
            _, desvio, _ = self.cliente.pedir("GET", "/dashboard")
            self.confere(desvio == "/trocar-senha", "Troca de senha obrigatória bloqueia o painel", "ACE",
                         "Antes de trocar a senha, o painel redireciona para a troca.",
                         f"Com a troca pendente, o painel levou para {desvio} em vez da troca de senha: a troca obrigatória só é cobrada na tela de login.",
                         "Usuário com troca obrigatória não usa a plataforma antes de trocar a senha", "Alta",
                         "Criar um @app.before_request que, com current_user.forcar_troca_senha, redirecione tudo (menos trocar_senha_obrigatoria, "
                         "logout e static) para a troca de senha — vale também para a recuperação de senha.")
            fraca_status, _, fraca_html = self.cliente.pedir("POST", "/trocar-senha", {"nova_senha": "abc123"})
            minimo = regra_da_plataforma("senha_min_caracteres")
            self.confere(fraca_status == 200 and f"{minimo} caracteres" in fraca_html, "Política de senha na troca obrigatória", "VAL",
                         "Senha fraca recusada com a orientação da política.", f"Senha fraca não foi recusada (HTTP {fraca_status}).",
                         f"Senha com {minimo}+ caracteres, maiúsculas, minúsculas, números e especiais (Parâmetros de regras)", "Alta")
            senha = nova_senha or senha_forte()
            _, destino, _ = self.cliente.pedir("POST", "/trocar-senha", {"nova_senha": senha})
        if destino == "/cadastrar-perguntas" or self.cliente.pedir("GET", "/dashboard")[1] == "/cadastrar-perguntas":
            perguntas = {"pergunta_1": "Qual é a sua cor favorita?", "resposta_1": "azul", "pergunta_2": "Em qual cidade você nasceu?",
                         "resposta_2": "santos", "pergunta_3": "Qual é o seu prato favorito?", "resposta_3": "feijoada"}
            repetidas = dict(perguntas, pergunta_2=perguntas["pergunta_1"])
            _, _, html = self.cliente.pedir("POST", "/cadastrar-perguntas", repetidas)
            self.confere("perguntas diferentes" in html, "Perguntas de segurança repetidas são recusadas", "VAL",
                         "A plataforma exige 3 perguntas diferentes.", "Aceitou a mesma pergunta duas vezes.", "3 perguntas diferentes", "Baixa")
            _, destino, _ = self.cliente.pedir("POST", "/cadastrar-perguntas", perguntas)
            gravado = self.banco(lambda: __import__("models").SegurancaUsuario.query.join(__import__("models").Usuario,
                                 __import__("models").SegurancaUsuario.usuario_id == __import__("models").Usuario.id)
                                 .filter(__import__("models").Usuario.email == email).first())
            self.confere(gravado is not None and str(gravado.resposta_1).startswith("$2"), "Perguntas de segurança gravadas com hash", "INT",
                         "Respostas guardadas com bcrypt.", "Respostas não gravadas ou sem hash.", "Respostas protegidas por hash", "Alta")
        _, desvio, _ = self.cliente.pedir("GET", self.PAGINA_SONDA)
        if desvio == "/onboarding":
            self.registrar("Termo de voluntariado exigido antes de usar a plataforma", APROVADO, "ACE",
                           "Sem o termo, as páginas redirecionam para o onboarding.", "Termo obrigatório (Lei 9.608/98)")
            self.cliente.pedir("POST", "/onboarding/aceitar")
            _, desvio, _ = self.cliente.pedir("GET", self.PAGINA_SONDA)
        if desvio == "/onboarding/trilha-tcc":
            self.registrar("Trilha do TCC obrigatória antes de orientar", APROVADO, "ACE",
                           "Sem concluir a trilha, as páginas redirecionam para ela.", "Mentor/Professor/Mentor Administrador concluem a trilha antes")
            m = __import__("models")
            email_atual = email

            def pendentes():
                usuario = m.Usuario.query.filter_by(email=email_atual).first()
                lidos = {c.modulo_id: c.versao_lida for c in m.ConclusaoModuloTCC.query.filter_by(usuario_id=usuario.id).all()}
                return [x.id for x in m.ModuloOnboardingTCC.query.filter_by(ativo=True).order_by(m.ModuloOnboardingTCC.ordem).all()
                        if (lidos.get(x.id) or 0) < (x.versao or 1)]
            destinos = []
            for _tentativa in range(2):  # uma nova tentativa só para os módulos que ficaram pendentes
                for modulo_id in self.banco(pendentes):
                    destinos.append(self.cliente.pedir("POST", f"/onboarding/trilha-tcc/{modulo_id}/concluir")[1])
                _, desvio, _ = self.cliente.pedir("GET", self.PAGINA_SONDA)
                if desvio != "/onboarding/trilha-tcc":
                    break
            restantes = self.banco(pendentes)
            if desvio == "/onboarding/trilha-tcc":
                self.diagnostico_trilha = f"Módulos ainda pendentes: {restantes}; destinos das conclusões: {sorted(set(map(str, destinos)))}."
        self.confere(desvio is None, "Onboarding concluído: a plataforma libera o uso", "ACE",
                     "Depois das etapas obrigatórias, as páginas abrem normalmente.",
                     f"Ainda redireciona para {desvio}. {getattr(self, 'diagnostico_trilha', '')}",
                     "Fluxo de primeiro acesso completo", "Alta", print_de="/dashboard")
        return senha

    # ------------------------------------------------------------------ matriz de acesso (aprendida)
    def matriz_de_acesso(self, base):
        """Expectativa vem das regras aprendidas (módulos de cada perfil): o que o perfil tem abre; o que não tem é barrado."""
        self.etapa(f"Matriz de acesso do perfil {base}")
        regras = self.regras.get("modulos_por_base") or {}
        modulos = self.regras.get("modulos") or {}
        if not regras:
            self.log("Regras de acesso não aprendidas ainda")
            return
        meus = set(regras.get(base, []))
        rotas = self.regras.get("rotas_get", {})
        abertas, bloqueadas_errado, liberadas_errado, paginas_abertas = 0, [], [], []
        # Exceção da plataforma: quem PARTICIPOU de uma reunião instituição × B2B vê a lista e a ata, mesmo sem o módulo de gestão
        por_participacao = self._modulos_por_participacao()
        if por_participacao:
            self.log(f"Acesso por participação (permitido): {', '.join(sorted(por_participacao))}")
        for modulo, endpoints in sorted(modulos.items()):
            if modulo in por_participacao and modulo not in meus:
                continue
            for endpoint in endpoints:
                caminho = rotas.get(endpoint)
                if not caminho:
                    continue
                status, destino, html = self.cliente.pedir("GET", caminho)
                if status in (301, 302, 303) and destino:
                    # Abre o destino para consumir o aviso (flash): senão ele aparece na próxima página e parece outro bloqueio
                    _, _, html_destino = self.cliente.pedir("GET", destino)
                    html = html + html_destino
                avisos = " ".join(mensagens(html)).lower()
                negacao_explicita = status in (403, 404) or destino == "/" or any(p in avisos for p in ("acesso negado", "acesso restrito")) \
                    or html.lstrip().lower().startswith("<h1>acesso negado")
                if modulo in meus:
                    # Página do próprio perfil: um redirecionamento com aviso informativo (ex.: "nenhuma banca") não é bloqueio
                    negado = negacao_explicita
                else:
                    negado = negacao_explicita or (status in (302, 303) and destino not in ("/onboarding", "/onboarding/trilha-tcc"))
                if modulo in meus and negado:
                    bloqueadas_errado.append(f"{caminho} ({modulo})")
                elif modulo not in meus and not negado:
                    liberadas_errado.append(f"{caminho} ({modulo})")
                elif modulo in meus:
                    abertas += 1
                    if status == 200:
                        paginas_abertas.append(caminho)
        self.confere(not liberadas_errado, f"{base} barrado nos módulos que o perfil não tem", "PER",
                     "Nenhuma página de módulo fora do perfil abriu.", "Abriram: " + "; ".join(liberadas_errado[:10]),
                     "Perfil só acessa os módulos definidos para ele", "Alta",
                     "Conferir o perfil no início das rotas listadas (ou ajustar MODULOS_POR_BASE se a regra mudou).")
        self.confere(not bloqueadas_errado, f"{base} acessa os módulos do seu perfil ({abertas} página(s))", "PER",
                     f"{abertas} página(s) dos módulos do perfil abriram.", "Bloqueadas por engano: " + "; ".join(bloqueadas_errado[:10]),
                     "Perfil usa todos os módulos definidos para ele", "Média", alerta=True)
        self.layout_no_navegador(paginas_abertas, base)

    def _modulos_por_participacao(self):
        """Módulos liberados por participação, não pelo perfil (regra de pode_ver_reuniao no app.py)."""
        email = getattr(self, "email_logado", None)
        if not email:
            return set()
        try:
            def consulta():
                import models
                u = models.Usuario.query.filter_by(email=email).first()
                return bool(u) and models.ReuniaoInstitucional.query.filter(models.ReuniaoInstitucional.participantes.any(id=u.id)).count() > 0
            return {"reunioes"} if self.banco(consulta) else set()
        except Exception:
            return set()

    # ------------------------------------------------------------------ aprendizados
    def carregar_aprendizados(self):
        try:
            from app import app
            import conhecimento_funcional as cf
            with app.app_context():
                itens = cf.para_agente(self.chave)
                cf.consumir(self.chave, itens)
                self.aprendizados = [{"codigo": a.codigo, "tipo": a.tipo, "titulo": a.titulo, "conteudo": json.loads(a.conteudo)} for a in itens]
                self.regras = cf.regras_aprendidas(itens)
        except Exception as e:
            self.log(f"Aprendizados indisponíveis: {e}")
        self.log(f"📚 {len(self.aprendizados)} aprendizado(s) do Gerente de Funcionalidades"
                 + (f" (regras de {len(self.regras.get('modulos_por_base', {}))} perfis)" if self.regras else ""))

    # ------------------------------------------------------------------ execução
    def rodar(self):
        raise NotImplementedError

    def executar(self):
        print(f"\n🧩 {self.nome} — perfil {self.perfil}", flush=True)
        for i, passo in enumerate(self.ROTEIRO, 1):
            print(f"   {i:>2}. {passo}", flush=True)
        self.carregar_aprendizados()
        try:
            self.rodar()
        except Exception as e:
            import traceback
            self.registrar(f"O agente parou por erro: {e.__class__.__name__}", FALHA, "FLX", f"{e} — {traceback.format_exc()[-600:]}",
                           "Fluxo completo sem erros", "Alta", "Ver o log do agente; a etapa em que parou indica a função com problema.")
        finally:
            self.fechar_navegador()
            gravar_contexto(self.contexto)
        return self.gerar_relatorio()

    def nota_de_saude(self):
        c = self.contagem()
        total = sum(c.values())
        return round(100 * (c[APROVADO] + 0.5 * c[ALERTA]) / total) if total else 100

    def gerar_prompt(self, caminho):
        problemas = [t for t in self.testes if t["resultado"] != APROVADO]
        problemas.sort(key=lambda t: (SEVERIDADES.index(t["severidade"]) if t["severidade"] in SEVERIDADES else 9))
        linhas = [f"# 🧩 Prompt de Correção de Funcionalidades para LLM — {self.nome}\n",
                  f"> Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelos Agentes de Funcionalidades. Cole no assistente de IA da sua "
                  "preferência (ChatGPT, Claude, Gemini, Copilot ou outro), anexando app.py, models.py e os templates citados.\n", "---\n"]
        if not problemas:
            linhas.append(f"✅ O {self.nome} validou todas as funções e regras do perfil {self.perfil} ({len(self.testes)} testes).")
        else:
            linhas += ["Você é um desenvolvedor sênior de Python/Flask (Flask-Login, Flask-SQLAlchemy, Jinja2) desta plataforma de mentoria.",
                       f"O teste funcional do perfil {self.perfil} encontrou {len(problemas)} ponto(s) em que a função ou a regra de negócio não se comportou "
                       "como esperado. Para CADA item: explique a causa provável, entregue a correção ANTES → DEPOIS (rota, template ou modelo), "
                       "sem quebrar as permissões dos outros perfis, e diga como confirmar com o Agente de Funcionalidades.\n"]
            for i, t in enumerate(problemas, 1):
                linhas += [f"### {i}. [{t['resultado']} · {t['severidade']}] {t['titulo']}", f"- **Etapa:** {t['etapa']} · **Categoria:** {t['categoria']}",
                           f"- **Esperado (regra):** {t['esperado']}", f"- **Obtido:** {t['detalhe']}"]
                if t["recomendacao"]:
                    linhas.append(f"- **Sugestão:** {t['recomendacao']}")
                linhas.append("")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    def gerar_relatorio(self):
        os.makedirs(PASTA_RELATORIOS, exist_ok=True)
        base = os.path.join(PASTA_RELATORIOS, f"Funcional_{self.chave}_{self.carimbo}")
        self.gerar_prompt(base + "_prompt.md")
        dados = {"chave": self.chave, "nome": self.nome, "perfil": self.perfil, "roteiro": self.ROTEIRO, "testes": self.testes,
                 "contagem": self.contagem(), "saude": self.nota_de_saude(), "aprendizados": [{k: a[k] for k in ("codigo", "tipo", "titulo")} for a in self.aprendizados],
                 "duracao_seg": int(time.time() - self.inicio), "carimbo": self.carimbo, "prompt": base + "_prompt.md", "evidencias": self.pasta_evidencias}
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
        c = self.contagem()
        print(f"\n✅ {self.nome}: {len(self.testes)} testes · {c[APROVADO]} aprovados · {c[FALHA]} falhas · {c[ALERTA]} alertas · saúde {self.nota_de_saude()}/100", flush=True)
        return dados
