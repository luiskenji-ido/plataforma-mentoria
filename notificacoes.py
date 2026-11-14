"""
NOTIFICAÇÕES DA PLATAFORMA (sino + e-mail)
==========================================
Toda comunicação do projeto passa pela plataforma: cada aviso vira uma Notificacao
(aparece no sino) e, se o SMTP estiver configurado no .env e a pessoa aceitar,
também um e-mail. Sem SMTP nada quebra: fica só o aviso interno.

Variáveis do .env (todas opcionais):
    MAIL_SERVER, MAIL_PORT (padrão 587), MAIL_USERNAME, MAIL_PASSWORD,
    MAIL_REMETENTE, MAIL_USE_TLS (padrão 1) e APP_BASE_URL (ex.: https://meuapp.pythonanywhere.com)
"""
import os
import smtplib
import logging
from email.message import EmailMessage

from flask import has_request_context, request

from models import db, Notificacao, Usuario
from traducoes import t

log = logging.getLogger("notificacoes")

PERFIS_GESTAO = ['Administrador', 'Mentor Administrador', 'Admin B2B']
ASSINATURA = "Equipe Jovem Seguro 2026"


def email_configurado():
    return bool(os.environ.get('MAIL_SERVER') and os.environ.get('MAIL_REMETENTE'))


def link_absoluto(link):
    """Links internos ('/demandas') viram absolutos para funcionar no e-mail."""
    if not link or link.startswith('http'):
        return link
    base = os.environ.get('APP_BASE_URL', '').rstrip('/')
    if not base and has_request_context():
        base = request.host_url.rstrip('/')
    return f"{base}{link}"


def enviar_email(destinatario, assunto, texto):
    """Envia um e-mail simples. Devolve True/False e nunca levanta exceção para a rota."""
    if not email_configurado() or not destinatario:
        return False
    mensagem = EmailMessage()
    mensagem['Subject'] = assunto
    mensagem['From'] = os.environ['MAIL_REMETENTE']
    mensagem['To'] = destinatario
    mensagem.set_content(texto)
    try:
        with smtplib.SMTP(os.environ['MAIL_SERVER'], int(os.environ.get('MAIL_PORT', 587)), timeout=15) as smtp:
            if os.environ.get('MAIL_USE_TLS', '1') != '0':
                smtp.starttls()
            if os.environ.get('MAIL_USERNAME'):
                smtp.login(os.environ['MAIL_USERNAME'], os.environ.get('MAIL_PASSWORD', ''))
            smtp.send_message(mensagem)
        return True
    except Exception as erro:
        log.warning("Falha ao enviar e-mail para %s: %s", destinatario, erro)
        return False


def no_idioma(texto, idioma):
    """Aceita texto pronto ou (chave_de_traducao, {parametros}) e devolve no idioma pedido."""
    if isinstance(texto, tuple):
        chave, parametros = texto
        return t(chave, idioma).format(**parametros)
    return texto


def notificar(usuarios, titulo, mensagem, link=None, tipo='geral', referencia=None, por_email=True):
    """
    Cria a notificação para cada usuário (sem repetir pessoas) e envia o e-mail quando possível.
    titulo e mensagem podem ser texto ou (chave, {parametros}): assim cada pessoa recebe no seu idioma.
    'referencia' evita avisos duplicados: a mesma pessoa não recebe duas vezes a mesma referência
    (ex.: 'checkout:15' para o lembrete do relógio 15). Devolve quantas notificações criou.
    """
    criadas = 0
    unicos = {u.id: u for u in usuarios if u is not None}
    for usuario in unicos.values():
        if referencia and Notificacao.query.filter_by(usuario_id=usuario.id, referencia=referencia).first():
            continue
        idioma = usuario.idioma or 'pt'
        titulo_pessoa, mensagem_pessoa = no_idioma(titulo, idioma), no_idioma(mensagem, idioma)
        db.session.add(Notificacao(usuario_id=usuario.id, titulo=titulo_pessoa, mensagem=mensagem_pessoa,
                                   link=link, tipo=tipo, referencia=referencia))
        criadas += 1
        if por_email and getattr(usuario, 'receber_email', True) is not False:
            corpo = t('notif_email_ola', idioma).format(nome=usuario.nome) + f"\n\n{mensagem_pessoa}\n"
            if link:
                corpo += f"\n{t('notif_email_acesse', idioma)}: {link_absoluto(link)}\n"
            corpo += f"\n{ASSINATURA}"
            enviar_email(usuario.email, f"Jovem Seguro 2026: {titulo_pessoa}", corpo)
    db.session.commit()
    return criadas


def usuarios_gestao(exceto_id=None):
    """Administradores, Mentores Administradores e Gestores B2B ativos (quem responde as demandas)."""
    consulta = Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_GESTAO), Usuario.status == 'Ativo')
    if exceto_id:
        consulta = consulta.filter(Usuario.id != exceto_id)
    return consulta.all()
