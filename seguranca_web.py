# -*- coding: utf-8 -*-
"""
PROTEÇÕES WEB DA PLATAFORMA (corrigem os achados dos Agentes de Segurança)
==========================================================================
Ligadas no app.py por configurar_seguranca(app):

- SECRET_KEY fora do código: variável de ambiente SECRET_KEY ou, sem ela, uma chave aleatória
  guardada em instance/.secret_key (pasta fora do Git).
- Cookies de sessão: HttpOnly, SameSite=Lax e Secure quando o site roda em HTTPS (PythonAnywhere).
- Proteção CSRF: token por sessão (csrf_token) exigido em todo POST/PUT/PATCH/DELETE, no campo
  "csrf_token" do formulário ou no cabeçalho X-CSRFToken. O token entra sozinho em todos os
  <form method="post"> das páginas, e um script curto no <head> acrescenta o cabeçalho às chamadas
  fetch/XMLHttpRequest e aos formulários criados por JavaScript.
- Limite de requisições por IP (rate limiting) no login, na recuperação de senha e no chat com IA (HTTP 429).
- Cabeçalhos de segurança: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy e HSTS (em HTTPS); o cabeçalho Server deixa de expor versões.
- MAX_CONTENT_LENGTH: limite global de upload.
- Filtro Jinja |html_seguro: deixa passar só HTML de formatação (sem script, eventos on* nem javascript:).
- voltar(): redireciona para a página anterior só se ela for deste mesmo site (evita open redirect).
"""
import os
import re
import hmac
import time
import secrets
import threading
from collections import defaultdict, deque
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from flask import request, session, redirect, url_for, flash, jsonify, render_template_string
from markupsafe import Markup

EM_PRODUCAO = bool(os.environ.get("PYTHONANYWHERE_DOMAIN") or os.environ.get("MENTORIA_PRODUCAO") == "1")
LIMITE_UPLOAD_MB = 50  # maior arquivo aceito (backups, entregas de TCC e currículos)

# Limite de requisições POST por IP: endpoint -> (máximo, janela em segundos)
LIMITES = {"login": (30, 60), "recuperar_senha": (15, 60), "chat_ia": (20, 60), "convidado_reuniao": (30, 60)}

# Origens externas que as páginas usam (bibliotecas de CDN, fontes e ícones)
CDNS = "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com"
POLITICA_CSP = "; ".join([
    "default-src 'self'",
    f"script-src 'self' 'unsafe-inline' {CDNS} https://www.youtube.com",  # YouTube: API do player das aulas (progresso do vídeo)
    f"style-src 'self' 'unsafe-inline' {CDNS} https://fonts.googleapis.com",
    f"font-src 'self' data: {CDNS} https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    f"connect-src 'self' {CDNS}",
    "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com https://player.vimeo.com https://drive.google.com https://docs.google.com",
    "frame-ancestors 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self' https://accounts.google.com",
])

METODOS_PROTEGIDOS = {"POST", "PUT", "PATCH", "DELETE"}
_FORM_POST = re.compile(r"(<form\b[^>]*\bmethod\s*=\s*[\"']?post[\"']?[^>]*>)", re.IGNORECASE)

# Acrescenta o token às chamadas feitas por JavaScript (fetch, XMLHttpRequest e form.submit())
_SCRIPT_CSRF = """<meta name="csrf-token" content="{token}"><script>(function(){{
var t=document.querySelector('meta[name="csrf-token"]').content,m=/^(post|put|patch|delete)$/i;
function mesmo(u){{try{{return new URL(u,location.href).origin===location.origin}}catch(e){{return false}}}}
var f=window.fetch;if(f){{window.fetch=function(e,o){{o=o||{{}};var u=(typeof e==='string'||e instanceof URL)?String(e):e.url,
me=o.method||(e&&e.method)||'GET';if(m.test(me)&&mesmo(u)){{var h=new Headers(o.headers||(e instanceof Request?e.headers:{{}}));
h.set('X-CSRFToken',t);o.headers=h;}}return f.call(this,e,o)}}}}
var ab=XMLHttpRequest.prototype.open,en=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open=function(me,u){{this._m=me;this._u=u;return ab.apply(this,arguments)}};
XMLHttpRequest.prototype.send=function(){{if(m.test(this._m||'')&&mesmo(this._u)){{this.setRequestHeader('X-CSRFToken',t)}}return en.apply(this,arguments)}};
function por(fm){{if(fm&&m.test(fm.method||'')&&!fm.querySelector('input[name="csrf_token"]')){{var i=document.createElement('input');
i.type='hidden';i.name='csrf_token';i.value=t;fm.appendChild(i)}}}}
var su=HTMLFormElement.prototype.submit;HTMLFormElement.prototype.submit=function(){{por(this);return su.apply(this,arguments)}};
document.addEventListener('submit',function(ev){{por(ev.target)}},true);
}})();</script>"""


# ------------------------------------------------------------------------------ chave secreta
def carregar_chave_secreta(pasta_instance):
    chave = os.environ.get("SECRET_KEY", "").strip()
    if chave:
        return chave
    caminho = os.path.join(pasta_instance, ".secret_key")
    try:
        with open(caminho, encoding="utf-8") as f:
            chave = f.read().strip()
    except OSError:
        chave = ""
    if len(chave) < 32:
        os.makedirs(pasta_instance, exist_ok=True)
        chave = secrets.token_hex(32)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(chave)
    return chave


# ------------------------------------------------------------------------------ CSRF
def gerar_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def _pedido_de_script():
    return (request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in (request.headers.get("Accept") or ""))


def _csrf_valido():
    esperado = session.get("_csrf_token")
    enviado = request.headers.get("X-CSRFToken") or request.form.get("csrf_token") or ""
    return bool(esperado) and hmac.compare_digest(str(esperado), str(enviado))


# ------------------------------------------------------------------------------ rate limiting
class LimitadorRequisicoes:
    """Janela deslizante em memória, por IP e por rota (cada processo do servidor conta o seu)."""

    def __init__(self):
        self.trava = threading.Lock()
        self.marcas = defaultdict(deque)

    def permitir(self, chave, maximo, janela):
        agora = time.monotonic()
        with self.trava:
            fila = self.marcas[chave]
            while fila and agora - fila[0] > janela:
                fila.popleft()
            if len(fila) >= maximo:
                return False, int(janela - (agora - fila[0])) + 1
            fila.append(agora)
            if len(self.marcas) > 20000:  # não deixa a memória crescer sem fim
                self.marcas.clear()
            return True, 0


limitador = LimitadorRequisicoes()


def ip_do_cliente():
    # No PythonAnywhere ou atrás do nginx do próprio servidor (ATRAS_DE_PROXY=1) o IP real vem do proxy, que sobrescreve
    # o X-Real-IP; localmente não se confia em cabeçalhos do cliente
    if os.environ.get("PYTHONANYWHERE_DOMAIN") or os.environ.get("ATRAS_DE_PROXY") == "1":
        return request.headers.get("X-Real-IP") or request.remote_addr or "?"
    return request.remote_addr or "?"


# ------------------------------------------------------------------------------ HTML seguro (filtro |html_seguro)
TAGS_PERMITIDAS = {"a", "b", "strong", "i", "em", "u", "p", "br", "hr", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                   "blockquote", "code", "pre", "span", "div", "small", "mark", "table", "thead", "tbody", "tr", "th", "td", "img", "sub", "sup"}
ATRIBUTOS_PERMITIDOS = {"href", "title", "target", "rel", "class", "src", "alt", "width", "height", "colspan", "rowspan"}
TAGS_DESCARTADAS = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "svg", "math"}


class _Sanitizador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saida = []
        self.ignorando = 0

    def handle_starttag(self, tag, atributos):
        if tag in TAGS_DESCARTADAS:
            self.ignorando += 1
            return
        if self.ignorando or tag not in TAGS_PERMITIDAS:
            return
        partes = []
        for nome, valor in atributos:
            if nome not in ATRIBUTOS_PERMITIDOS or valor is None:
                continue
            if nome in ("href", "src"):
                esquema = urlparse(valor.strip()).scheme.lower()
                if esquema not in ("", "http", "https", "mailto"):
                    continue
            partes.append(f'{nome}="{escape(valor, quote=True)}"')
        if tag == "a" and any(p.startswith('target=') for p in partes):
            partes = [p for p in partes if not p.startswith("rel=")] + ['rel="noopener noreferrer"']
        self.saida.append(f"<{tag}{' ' if partes else ''}{' '.join(partes)}>")

    def handle_endtag(self, tag):
        if tag in TAGS_DESCARTADAS:
            self.ignorando = max(0, self.ignorando - 1)
            return
        if not self.ignorando and tag in TAGS_PERMITIDAS and tag not in ("br", "hr", "img"):
            self.saida.append(f"</{tag}>")

    def handle_data(self, dados):
        if not self.ignorando:
            self.saida.append(escape(dados, quote=False))


def html_seguro(valor):
    """HTML de formatação confiável (para conteúdo rico digitado pela gestão, como os módulos da Trilha do TCC)."""
    if not valor:
        return Markup("")  # nosec: texto vazio
    s = _Sanitizador()
    s.feed(str(valor))
    s.close()
    return Markup("".join(s.saida))  # nosec: saída do sanitizador (só tags/atributos da lista permitida, texto escapado)


# ------------------------------------------------------------------------------ redirecionamento seguro
def destino_interno(url, padrao):
    """Devolve 'url' só se for deste mesmo site; senão, 'padrao'."""
    if not url:
        return padrao
    alvo = urlparse(url)
    if alvo.scheme in ("", "http", "https") and (not alvo.netloc or alvo.netloc == request.host) and not url.startswith("//"):
        return url
    return padrao


def voltar(endpoint_padrao="dashboard", **valores):
    """Volta para a página anterior (cabeçalho Referer) se ela for da plataforma; senão vai para a tela padrão."""
    return redirect(destino_interno(request.referrer, url_for(endpoint_padrao, **valores)))  # nosec: destino_interno só aceita o próprio site


# ------------------------------------------------------------------------------ ligação com o app
def configurar_seguranca(app, traduzir=None):
    traduzir = traduzir or (lambda texto: texto)
    if EM_PRODUCAO:
        # No PythonAnywhere o HTTPS termina no proxy deles: sem isto, url_for(_external=True) gera http:// e o Google
        # recusa o endereço de retorno do login (Agenda e Gmail). Confia só no esquema e no host do proxy (1 salto).
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config["SECRET_KEY"] = carregar_chave_secreta(app.instance_path)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=EM_PRODUCAO,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=EM_PRODUCAO,
        MAX_CONTENT_LENGTH=LIMITE_UPLOAD_MB * 1024 * 1024,
    )
    app.jinja_env.filters["html_seguro"] = html_seguro

    @app.context_processor
    def _token_nos_templates():
        return {"csrf_token": gerar_csrf_token}

    @app.before_request
    def _limitar_requisicoes():
        regra = LIMITES.get(request.endpoint)
        if not regra or request.method != "POST":
            return None
        permitido, espera = limitador.permitir((request.endpoint, ip_do_cliente()), *regra)
        if permitido:
            return None
        mensagem = traduzir("Muitas tentativas seguidas. Aguarde um minuto e tente de novo.")
        if _pedido_de_script():
            resposta = jsonify({"erro": mensagem, "resposta": mensagem})
        else:
            resposta = app.response_class(render_template_string(
                "<!DOCTYPE html><html lang='pt'><head><meta charset='utf-8'><title>429</title></head>"
                "<body style='font-family:sans-serif;padding:40px'><h1>429</h1><p>{{ m }}</p><p><a href='{{ url_for(\"login\") }}'>&larr;</a></p></body></html>",
                m=mensagem), mimetype="text/html")
        resposta.status_code = 429
        resposta.headers["Retry-After"] = str(espera)
        return resposta

    @app.before_request
    def _limite_de_upload_da_rota():
        # Rotas com arquivo maior que o limite global (ex.: gravação da reunião): app.config["LIMITES_UPLOAD_ROTA"] =
        # {endpoint: função que devolve o limite em MB}. Precisa vir antes do CSRF, que é quem lê o formulário primeiro.
        limite = (app.config.get("LIMITES_UPLOAD_ROTA") or {}).get(request.endpoint)
        if limite and request.method in METODOS_PROTEGIDOS:
            try:
                request.max_content_length = int(limite()) * 1024 * 1024
            except Exception:
                pass
        return None

    @app.before_request
    def _verificar_csrf():
        if request.method not in METODOS_PROTEGIDOS or app.config.get("TESTING") or app.config.get("CSRF_DESLIGADO"):
            return None
        if _csrf_valido():
            return None
        mensagem = traduzir("A página expirou ou o pedido não veio da plataforma. Recarregue a página e tente de novo.")
        if _pedido_de_script():
            return jsonify({"erro": mensagem, "ok": False}), 400
        flash(mensagem, "warning")
        return redirect(url_for("login"))

    @app.after_request
    def _cabecalhos_e_token(resposta):
        resposta.headers.setdefault("Content-Security-Policy", POLITICA_CSP)
        resposta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.is_secure or EM_PRODUCAO:
            resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resposta.headers["Server"] = "Mentoria"
        # Token CSRF em todo formulário POST das páginas HTML
        if (resposta.mimetype == "text/html" and resposta.status_code == 200 and not resposta.direct_passthrough
                and not resposta.is_streamed):
            html = resposta.get_data(as_text=True)
            tem_form = _FORM_POST.search(html)
            tem_head = "<head>" in html
            if tem_form or tem_head:
                token = gerar_csrf_token()
                campo = f'<input type="hidden" name="csrf_token" value="{token}">'
                if tem_form:
                    html = _FORM_POST.sub(lambda m: m.group(1) + campo, html)
                if tem_head:
                    html = html.replace("<head>", "<head>" + _SCRIPT_CSRF.format(token=token), 1)
                resposta.set_data(html)
        return resposta

    return app
