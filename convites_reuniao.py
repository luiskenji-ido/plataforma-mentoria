# -*- coding: utf-8 -*-
"""
CONVITES DAS REUNIÕES instituição × B2B
===============================
- Arquivo de agenda (.ics, padrão iCalendar RFC 5545): abre no Outlook, Apple Calendar, Thunderbird e outros.
- Links "adicionar à agenda" para Google Agenda, Outlook.com, Microsoft 365 (Outlook corporativo) e Yahoo Agenda.
- E-mail de convite (METHOD:REQUEST) com o .ics anexo: Gmail, Outlook e Yahoo mostram os botões Sim/Não/Talvez
  e salvam o evento na agenda de quem recebe. Envio pelo Gmail conectado (API do Gmail, OAuth) ou pelo SMTP da plataforma.

As datas das reuniões são gravadas em hora local de Brasília (UTC−3, sem horário de verão desde 2019).
"""
import os
import re
import base64
import logging
import email_smtp
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import urlencode

log = logging.getLogger("convites_reuniao")

FUSO = timezone(timedelta(hours=-3), "America/Sao_Paulo")
PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Contas de teste dos agentes e domínios reservados nunca recebem convite (evita e-mails devolvidos)
DOMINIOS_DE_TESTE = re.compile(r"@(local\.com|example\.(com|org|net)|[^@]*\.(test|local|invalid|localhost))$", re.I)
SCOPES_GMAIL = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/gmail.send']

PROVEDORES = [  # (chave, nome exibido, ícone Bootstrap)
    ('google', 'Google Agenda (Gmail)', 'bi-google'),
    ('outlook', 'Outlook.com / Hotmail', 'bi-microsoft'),
    ('office365', 'Microsoft 365 (Outlook corporativo)', 'bi-microsoft-teams'),
    ('yahoo', 'Yahoo Agenda', 'bi-envelope-at'),
    ('ics', 'Apple, Thunderbird e outros (.ics)', 'bi-calendar-plus'),
]


# ------------------------------------------------------------------------------ datas
def _marca():
    """Identidade da instituição (apelido e plataforma) usada no texto do convite e no remetente."""
    import identidade
    return identidade.obter()


def inicio_fim(reuniao):
    inicio = reuniao.data_hora.replace(tzinfo=FUSO)
    return inicio, inicio + timedelta(minutes=reuniao.duracao_minutos or 60)


def _utc(dt):
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


# ------------------------------------------------------------------------------ participantes
def externos_com_email(reuniao):
    """Linhas "Nome – Instituição – email" dos participantes externos: devolve [(nome, email)] de quem tem e-mail."""
    pessoas = []
    for linha in (reuniao.participantes_externos or '').splitlines():
        achado = PADRAO_EMAIL.search(linha)
        if achado:
            nome = re.split(r"\s+[–—-]\s+", linha.replace(achado.group(0), '').strip(' –—-<>()'))[0].strip() or achado.group(0)
            pessoas.append((nome, achado.group(0).lower()))
    return pessoas


def ler_externos(texto):
    """Lista "Participantes externos" (uma pessoa por linha: "Nome – Instituição – email", em qualquer ordem depois do nome)
    → [{'nome', 'instituicao', 'email'}]. Linhas repetidas (mesmo e-mail ou mesmo nome sem e-mail) contam uma vez."""
    pessoas, vistos = [], set()
    for linha in (texto or '').splitlines():
        linha = linha.strip()
        if not linha:
            continue
        achado = PADRAO_EMAIL.search(linha)
        email = achado.group(0).lower() if achado else None
        resto = linha.replace(achado.group(0), '') if achado else linha
        partes = [p.strip(' <>()') for p in re.split(r"\s+[–—-]\s+|\s*[;|]\s*", resto.strip(' –—-<>()')) if p.strip(' <>()–—-')]
        nome = (partes[0] if partes else '') or email or linha
        chave = email or nome.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        pessoas.append({'nome': nome[:150], 'instituicao': (partes[1] if len(partes) > 1 else '')[:150] or None, 'email': email})
    return pessoas


def destinatarios(reuniao, remetente=None):
    """Quem recebe o convite: participantes da plataforma + externos com e-mail, sem repetir e sem o próprio remetente.
    Devolve (validos, ignorados) — ignorados são contas de teste ou sem e-mail."""
    vistos, validos, ignorados = {(remetente or '').lower()}, [], []
    candidatos = [(p.nome, (p.email or '').strip().lower()) for p in reuniao.participantes] + externos_com_email(reuniao)
    for nome, email in candidatos:
        if not email or email in vistos:
            continue
        vistos.add(email)
        (ignorados if DOMINIOS_DE_TESTE.search(email) or not PADRAO_EMAIL.fullmatch(email) else validos).append((nome, email))
    return validos, ignorados


# ------------------------------------------------------------------------------ iCalendar (.ics)
def _texto_ics(valor):
    return (valor or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r\n', '\\n').replace('\n', '\\n')


def _dobrar(linha):
    """Linhas de no máximo 75 bytes (RFC 5545 §3.1), sem cortar caracteres UTF-8 ao meio."""
    partes, atual = [], ''
    for caractere in linha:
        if len((atual + caractere).encode('utf-8')) > (75 if not partes else 74):
            partes.append(atual)
            atual = caractere
        else:
            atual += caractere
    partes.append(atual)
    return '\r\n '.join(partes)


def descricao(reuniao, link=None):
    partes = []
    if getattr(reuniao, 'empresa', None):
        partes.append(f"Parceiro B2B: {reuniao.empresa.nome}")
    if reuniao.local_ou_link:
        partes.append(f"{'Link' if reuniao.local_ou_link.startswith('http') else 'Local'}: {reuniao.local_ou_link}")
    if reuniao.pauta:
        partes.append(f"Pauta:\n{reuniao.pauta}")
    if link:
        partes.append(f"Ata e encaminhamentos na plataforma: {link}")
    return '\n\n'.join(partes)


def gerar_ics(reuniao, link=None, metodo='PUBLISH', organizador=None, convidados=()):
    """metodo PUBLISH = arquivo para salvar na agenda; REQUEST = convite por e-mail (com organizador e convidados)."""
    inicio, fim = inicio_fim(reuniao)
    dominio = re.sub(r'^https?://', '', os.environ.get('APP_BASE_URL', '') or 'mentoria').split('/')[0] or 'mentoria'
    linhas = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Plataforma de Mentoria//Reunioes//PT', 'CALSCALE:GREGORIAN',
              f'METHOD:{metodo}', 'BEGIN:VEVENT',
              f'UID:reuniao-{reuniao.id}@{dominio}',
              f'DTSTAMP:{_utc(datetime.now(timezone.utc))}',
              f'DTSTART:{_utc(inicio)}', f'DTEND:{_utc(fim)}',
              f'SEQUENCE:{reuniao.convite_sequencia or 0}',
              f'SUMMARY:{_texto_ics(reuniao.titulo)}',
              f'DESCRIPTION:{_texto_ics(descricao(reuniao, link))}']
    if reuniao.local_ou_link:
        linhas.append(f'LOCATION:{_texto_ics(reuniao.local_ou_link)}')
    if link:
        linhas.append(f'URL:{link}')
    if metodo == 'REQUEST' and organizador:
        nome, email = organizador
        linhas.append(f'ORGANIZER;CN="{_texto_ics(nome)}":mailto:{email}')
        for nome_c, email_c in convidados:
            linhas.append(f'ATTENDEE;CN="{_texto_ics(nome_c)}";ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{email_c}')
    linhas += ['STATUS:CONFIRMED', 'TRANSP:OPAQUE',
               'BEGIN:VALARM', 'ACTION:DISPLAY', 'TRIGGER:-PT15M', f'DESCRIPTION:{_texto_ics(reuniao.titulo)}', 'END:VALARM',
               'END:VEVENT', 'END:VCALENDAR']
    return '\r\n'.join(_dobrar(linha) for linha in linhas) + '\r\n'


# ------------------------------------------------------------------------------ links "adicionar à agenda"
def links_agenda(reuniao, link=None, url_ics=None):
    inicio, fim = inicio_fim(reuniao)
    texto = descricao(reuniao, link)
    local = reuniao.local_ou_link or ''
    outlook = {'path': '/calendar/action/compose', 'rru': 'addevent', 'subject': reuniao.titulo,
               'startdt': inicio.isoformat(), 'enddt': fim.isoformat(), 'body': texto, 'location': local}
    links = {
        'google': 'https://calendar.google.com/calendar/render?' + urlencode(
            {'action': 'TEMPLATE', 'text': reuniao.titulo, 'dates': f'{_utc(inicio)}/{_utc(fim)}', 'details': texto,
             'location': local, 'ctz': 'America/Sao_Paulo'}),
        'outlook': 'https://outlook.live.com/calendar/0/action/compose?' + urlencode(outlook),
        'office365': 'https://outlook.office.com/calendar/0/action/compose?' + urlencode(outlook),
        'yahoo': 'https://calendar.yahoo.com/?' + urlencode(
            {'v': 60, 'title': reuniao.titulo, 'st': _utc(inicio), 'et': _utc(fim), 'desc': texto, 'in_loc': local}),
    }
    if url_ics:
        links['ics'] = url_ics
    return links


# ------------------------------------------------------------------------------ e-mail do convite
def montar_email(reuniao, remetente, convidados, link=None, url_ics=None, atualizacao=False, para=None, link_pessoal=None):
    """remetente = (nome, email). Corpo em texto e HTML + text/calendar (METHOD:REQUEST) + anexo convite.ics.
    convidados = todos os convidados (lista de participantes do .ics); para = quem recebe esta mensagem (padrão: todos).
    link_pessoal = página do convidado externo (sem login) para check-in, check-out e avaliação; substitui o link da ata."""
    inicio, fim = inicio_fim(reuniao)
    quando = f"{inicio.strftime('%d/%m/%Y %H:%M')}–{fim.strftime('%H:%M')} (horário de Brasília)"
    assunto = f"{'Atualização' if atualizacao else 'Convite'}: {reuniao.titulo} · {inicio.strftime('%d/%m/%Y %H:%M')}"
    links = links_agenda(reuniao, link, url_ics)
    rotulos = {chave: nome for chave, nome, _ in PROVEDORES}

    texto = [f"Você foi convidado(a) para a reunião {_marca()['apelido']} × B2B \"{reuniao.titulo}\".", '', f"Quando: {quando}",
             f"Modalidade: {reuniao.modalidade or 'Online'}"]
    if reuniao.local_ou_link:
        texto.append(f"Local ou link: {reuniao.local_ou_link}")
    if reuniao.pauta:
        texto += ['', 'Pauta:', reuniao.pauta]
    texto += ['', 'Salvar na sua agenda:'] + [f"- {rotulos[c]}: {u}" for c, u in links.items()]
    if link_pessoal:
        texto += ['', "Seu link pessoal para registrar a presença (check-in ao chegar e check-out ao sair) e avaliar a reunião:",
                  link_pessoal, "Não precisa de login. Não repasse este link: ele é só seu."]
    elif link:
        texto += ['', f"Ata e encaminhamentos: {link}"]
    texto += ['', f"Convite enviado por {remetente[0]} pela plataforma {_marca()['plataforma']}."]

    botoes = ''.join(f'<a href="{escape(u)}" style="display:inline-block;margin:0 6px 6px 0;padding:7px 12px;border-radius:6px;'
                     f'background:#0d6efd;color:#fff;text-decoration:none;font-size:13px">{escape(rotulos[c])}</a>' for c, u in links.items())
    local_html = ''
    if reuniao.local_ou_link:
        valor = escape(reuniao.local_ou_link)
        local_html = '<p><b>Local ou link:</b> ' + (f'<a href="{valor}">{valor}</a>' if reuniao.local_ou_link.startswith('http') else valor) + '</p>'
    html = (f'<div style="font-family:Arial,sans-serif;font-size:14px;color:#1f2937">'
            f'<h2 style="color:#0d6efd;margin:0 0 8px">{escape(reuniao.titulo)}</h2>'
            f'<p><b>Quando:</b> {escape(quando)}<br><b>Modalidade:</b> {escape(reuniao.modalidade or "Online")}</p>{local_html}'
            + (f'<p><b>Pauta:</b><br>{escape(reuniao.pauta).replace(chr(10), "<br>")}</p>' if reuniao.pauta else '')
            + f'<p style="margin-bottom:4px"><b>Salvar na sua agenda:</b></p><div>{botoes}</div>'
            + (f'<p style="margin:14px 0 4px"><b>Sua presença e sua avaliação</b></p>'
               f'<p style="margin:0 0 6px">Use o seu link pessoal para fazer o check-in ao chegar, o check-out ao sair e avaliar a reunião '
               f'(não precisa de login; não repasse, ele é só seu).</p>'
               f'<a href="{escape(link_pessoal)}" style="display:inline-block;padding:8px 14px;border-radius:6px;background:#198754;'
               f'color:#fff;text-decoration:none;font-weight:bold">Registrar presença e avaliar</a>' if link_pessoal else
               (f'<p><a href="{escape(link)}">Abrir a ata e os encaminhamentos na plataforma</a></p>' if link else ''))
            + f'<p style="color:#6b7280;font-size:12px">Convite enviado por {escape(remetente[0])} pela plataforma {escape(_marca().get("plataforma", ""))}.</p></div>')

    ics = gerar_ics(reuniao, None if link_pessoal else link, 'REQUEST', remetente, convidados)
    mensagem = EmailMessage()
    mensagem['Subject'] = assunto
    mensagem['From'] = formataddr(remetente)
    mensagem['To'] = ', '.join(formataddr(c) for c in (para or convidados))
    mensagem.set_content('\n'.join(texto))
    mensagem.add_alternative(html, subtype='html')
    mensagem.add_alternative(ics, subtype='calendar', params={'method': 'REQUEST'})
    mensagem.add_attachment(ics.encode('utf-8'), maintype='application', subtype='ics', filename='convite.ics')
    return mensagem


def montar_email_link_pessoal(reuniao, remetente, convidado_nome, convidado_email, link_pessoal):
    """Aviso curto só com o link pessoal (quando o convite saiu pelo Outlook, que manda o mesmo texto para todos)."""
    inicio, _ = inicio_fim(reuniao)
    mensagem = EmailMessage()
    mensagem['Subject'] = f"Seu link de presença: {reuniao.titulo} · {inicio.strftime('%d/%m/%Y %H:%M')}"
    mensagem['From'] = formataddr(remetente)
    mensagem['To'] = formataddr((convidado_nome, convidado_email))
    mensagem.set_content('\n'.join([
        f"Olá, {convidado_nome}.", '',
        f"Na reunião \"{reuniao.titulo}\" ({inicio.strftime('%d/%m/%Y %H:%M')}), registre a sua presença pelo link abaixo: "
        "check-in ao chegar, check-out ao sair e, no fim, a sua avaliação da reunião.", '', link_pessoal, '',
        "Não precisa de login. Não repasse este link: ele é só seu.", '',
        f"Plataforma {_marca()['plataforma']}."]))
    mensagem.add_alternative(
        f'<div style="font-family:Arial,sans-serif;font-size:14px;color:#1f2937"><p>Olá, {escape(convidado_nome)}.</p>'
        f'<p>Na reunião <b>{escape(reuniao.titulo)}</b> ({inicio.strftime("%d/%m/%Y %H:%M")}), registre a sua presença pelo link abaixo: '
        f'check-in ao chegar, check-out ao sair e, no fim, a sua avaliação da reunião.</p>'
        f'<a href="{escape(link_pessoal)}" style="display:inline-block;padding:8px 14px;border-radius:6px;background:#198754;color:#fff;'
        f'text-decoration:none;font-weight:bold">Registrar presença e avaliar</a>'
        f'<p style="color:#6b7280;font-size:12px">Não precisa de login. Não repasse este link: ele é só seu.</p></div>', subtype='html')
    return mensagem


# ------------------------------------------------------------------------------ envio
def smtp_configurado():
    return email_smtp.configurado()


def remetente_smtp():
    return (os.environ.get('MAIL_NOME_REMETENTE') or _marca()['plataforma'], os.environ.get('MAIL_REMETENTE', ''))


def enviar_smtp(mensagem):
    email_smtp.enviar(mensagem)


def credenciais_gmail(token, refresh_token, caminho_client_secret):
    import json
    import google.oauth2.credentials
    with open(caminho_client_secret, encoding='utf-8') as f:
        cliente = json.load(f)['web']
    return google.oauth2.credentials.Credentials(token=token, refresh_token=refresh_token, token_uri=cliente['token_uri'],
                                                 client_id=cliente['client_id'], client_secret=cliente['client_secret'],
                                                 scopes=SCOPES_GMAIL)


def enviar_gmail(mensagem, credenciais):
    """Envia pela API do Gmail como a pessoa conectada. No PythonAnywhere a saída passa pelo proxy deles."""
    from googleapiclient.discovery import build
    if os.environ.get('PYTHONANYWHERE_DOMAIN'):
        import httplib2
        import google_auth_httplib2
        http = httplib2.Http(proxy_info=httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, 'proxy.server', 3128))
        servico = build('gmail', 'v1', http=google_auth_httplib2.AuthorizedHttp(credenciais, http=http), cache_discovery=False)
    else:
        servico = build('gmail', 'v1', credentials=credenciais, cache_discovery=False)
    bruto = base64.urlsafe_b64encode(mensagem.as_bytes()).decode('ascii')
    servico.users().messages().send(userId='me', body={'raw': bruto}).execute()


def email_do_id_token(id_token):
    """E-mail da conta Google a partir do id_token recebido direto do Google (canal TLS do próprio OAuth)."""
    import json
    try:
        carga = id_token.split('.')[1]
        return json.loads(base64.urlsafe_b64decode(carga + '=' * (-len(carga) % 4))).get('email')
    except Exception:
        return None
