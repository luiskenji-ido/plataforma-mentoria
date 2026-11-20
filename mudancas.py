# -*- coding: utf-8 -*-
"""
REQUISIÇÃO DE MUDANÇA (RDM em português, CR em inglês, SC em espanhol)
=====================================================================
Toda mudança sensível passa por aqui antes de valer:
  pedido (Aguardando aprovação) → decisão de um membro do grupo de aprovação (Aprovada / Reprovada) → aplicação (Aplicada).
- Grupo de aprovação: apelido em Provedores de IA e custos › Credenciais › "Variável apelido B2B-Comite-Aprovacao"
  (variável COMITE_APROVACAO_APELIDO) e os membros escolhidos logo abaixo, na mesma tela.
- Quem pede não aprova a própria requisição (separação de funções).
- Parâmetros de regras: o pedido guarda os valores novos; aprovada, a mudança é aplicada na data agendada (ou na hora).
- Correções de código do Orquestrador: o commit só é confirmado com uma requisição aprovada; o commit leva o número dela.
Todas as funções rodam dentro de um app_context.
"""
import json
import os
import re
from datetime import datetime

# Regras nomeadas
PREFIXO_POR_IDIOMA = {'pt': 'RDM', 'en': 'CR', 'es': 'SC'}
VARIAVEL_GRUPO = 'COMITE_APROVACAO_APELIDO'
PERFIS_ELEGIVEIS_COMITE = ['Administrador', 'Mentor Administrador']
AGUARDANDO, APROVADA, REPROVADA, APLICADA, CANCELADA = 'Aguardando aprovação', 'Aprovada', 'Reprovada', 'Aplicada', 'Cancelada'
STATUS_ABERTOS = [AGUARDANDO, APROVADA]
TIPOS = {'parametros': 'Parâmetros de regras', 'codigo': 'Correção de código (Orquestrador)', 'outro': 'Outra mudança'}
RISCOS = ['Baixo', 'Médio', 'Alto']
CODIGO = re.compile(r'^(?:(?:RDM|CR|SC)\s*-?\s*)?(\d{4})-(\d{1,4})$', re.I)


# ------------------------------------------------------------------------------ número
def numero(r, idioma='pt'):
    """RDM-2026-0001 (pt), CR-2026-0001 (en), SC-2026-0001 (es)."""
    return f"{PREFIXO_POR_IDIOMA.get(idioma, 'RDM')}-{r.codigo}" if r else ''


def prefixo(idioma='pt'):
    return PREFIXO_POR_IDIOMA.get(idioma, 'RDM')


def achar(texto):
    """Aceita RDM-2026-0001, CR-2026-1, SC 2026-0001 ou 2026-0001."""
    from models import RequisicaoMudanca
    m = CODIGO.match((texto or '').strip())
    if not m:
        return None
    return RequisicaoMudanca.query.filter_by(codigo=f'{m.group(1)}-{int(m.group(2)):04d}').first()


def _proximo_codigo():
    from models import RequisicaoMudanca
    ano = datetime.now().year
    ultimos = [r.codigo for r in RequisicaoMudanca.query.filter(RequisicaoMudanca.codigo.like(f'{ano}-%')).all()]
    seq = max((int(c.split('-')[1]) for c in ultimos), default=0) + 1
    return f'{ano}-{seq:04d}'


# ------------------------------------------------------------------------------ grupo de aprovação
def nome_do_grupo():
    """Apelido cadastrado em Credenciais. As credenciais vão para o ambiente do processo só quando alguém as carrega:
    carrega aqui (no máximo uma leitura do banco por minuto) para valer também logo depois de o servidor reiniciar."""
    try:
        from flask import current_app
        import credenciais_agentes
        credenciais_agentes.carregar(current_app.config['SECRET_KEY'])
    except Exception:
        pass
    return (os.environ.get(VARIAVEL_GRUPO) or '').strip()


def membros():
    from models import MembroComiteMudanca
    return [m.usuario for m in MembroComiteMudanca.query.all() if m.usuario and m.usuario.status == 'Ativo']


def elegiveis():
    """Quem pode ser escolhido como membro do grupo de aprovação."""
    from models import Usuario
    return Usuario.query.filter(Usuario.tipo_usuario.in_(PERFIS_ELEGIVEIS_COMITE), Usuario.status == 'Ativo').order_by(Usuario.nome).all()


def eh_membro(usuario):
    from models import MembroComiteMudanca
    return bool(usuario and getattr(usuario, 'id', None)) and MembroComiteMudanca.query.filter_by(usuario_id=usuario.id).first() is not None


def definir_membros(ids, usuario_id):
    """Troca os membros do grupo pelos escolhidos (só perfis elegíveis). Devolve a quantidade de membros."""
    from models import db, MembroComiteMudanca
    validos = {u.id for u in elegiveis()} & {int(i) for i in ids if str(i).isdigit()}
    atuais = {m.usuario_id: m for m in MembroComiteMudanca.query.all()}
    for uid, m in atuais.items():
        if uid not in validos:
            db.session.delete(m)
    for uid in validos - set(atuais):
        db.session.add(MembroComiteMudanca(usuario_id=uid, incluido_por_id=usuario_id, incluido_em=datetime.now()))
    db.session.commit()
    return len(validos)


def pode_decidir(usuario, r):
    """Membro do grupo, requisição aguardando e não é quem pediu."""
    return bool(r) and r.status == AGUARDANDO and eh_membro(usuario) and r.solicitante_id != usuario.id


def pode_ver(usuario):
    from app import PERFIS_ADMINISTRACAO_SISTEMA
    return usuario.tipo_usuario in PERFIS_ADMINISTRACAO_SISTEMA or eh_membro(usuario)


# ------------------------------------------------------------------------------ pedido, decisão e aplicação
def _avisar(usuarios, titulo, mensagem, r, referencia):
    try:
        from notificacoes import notificar, eh_conta_de_teste
        alvo = [u for u in usuarios if u and not eh_conta_de_teste(u)]
        if alvo:
            notificar(alvo, titulo, mensagem, link=f'/admin/mudancas#rdm_{r.id}', tipo='sistema', referencia=referencia)
    except Exception:
        pass  # o aviso nunca impede o pedido


def criar(tipo, titulo, solicitante, descricao='', justificativa='', risco='Baixo', plano_rollback='', data_agendada=None,
          conteudo=None):
    """Registra o pedido (Aguardando aprovação) e avisa o grupo. Devolve (requisicao, erro)."""
    from models import db, RequisicaoMudanca
    titulo = ' '.join((titulo or '').split())[:200]
    if tipo not in TIPOS:
        return None, 'Tipo de mudança inválido.'
    if len(titulo) < 5:  # regra-nomeada: ok (título mínimo, igual ao das outras telas de cadastro)
        return None, 'Dê um título à mudança (pelo menos 5 letras).'
    if risco not in RISCOS:
        risco = 'Baixo'
    if not nome_do_grupo() or not membros():
        return None, ('Cadastre o grupo de aprovação (Variável apelido B2B-Comite-Aprovacao) e os membros dele em '
                      'Provedores de IA e custos › Credenciais antes de pedir mudanças.')
    r = RequisicaoMudanca(codigo=_proximo_codigo(), tipo=tipo, titulo=titulo, descricao=(descricao or '').strip()[:5000] or None,
                          justificativa=(justificativa or '').strip()[:3000] or None, risco=risco,
                          plano_rollback=(plano_rollback or '').strip()[:3000] or None, status=AGUARDANDO,
                          conteudo=json.dumps(conteudo, ensure_ascii=False) if conteudo else None, grupo_aprovacao=nome_do_grupo(),
                          solicitante_id=solicitante.id, data_solicitacao=datetime.now(), data_agendada=data_agendada)
    db.session.add(r)
    db.session.commit()
    _avisar([u for u in membros() if u.id != solicitante.id], 'Requisição de mudança aguardando aprovação',
            f"{numero(r)} · {r.titulo} — pedida por {solicitante.nome}.", r, f'rdm-pedido-{r.id}')
    return r, None


def anexar_conteudo(r, conteudo):
    """Liga o que será aplicado a uma requisição criada antes (pelo formulário), enquanto ela aguarda aprovação."""
    from models import db
    r.conteudo = json.dumps(conteudo, ensure_ascii=False)
    db.session.commit()


def conteudo(r):
    try:
        return json.loads(r.conteudo) if r and r.conteudo else {}
    except ValueError:
        return {}


def decidir(r, usuario, aprovar, motivo=''):
    """Aprova ou reprova. Aprovada e já na data (ou sem data), uma mudança de parâmetros é aplicada na hora.
    Devolve (ok, mensagem em português)."""
    from models import db
    if not r:
        return False, 'Requisição de mudança não encontrada.'
    if r.status != AGUARDANDO:
        return False, 'Esta requisição já foi decidida.'
    if r.solicitante_id == usuario.id:
        return False, 'Quem pediu a mudança não pode aprová-la: outro membro do grupo de aprovação decide.'
    if not eh_membro(usuario):
        return False, 'Só os membros do grupo de aprovação podem decidir.'
    if not aprovar and len((motivo or '').strip()) < 3:  # regra-nomeada: ok (mínimo do comentário, como MINIMO_CARACTERES_COMENTARIO)
        return False, 'Explique o motivo da reprovação.'
    r.status = APROVADA if aprovar else REPROVADA
    r.aprovador_id, r.data_decisao, r.motivo_decisao = usuario.id, datetime.now(), (motivo or '').strip()[:500] or None
    db.session.commit()
    _avisar([r.solicitante], 'Requisição de mudança aprovada' if aprovar else 'Requisição de mudança reprovada',
            f"{numero(r)} · {r.titulo} — {usuario.nome}" + (f": {r.motivo_decisao}" if r.motivo_decisao else '.'), r,
            f'rdm-decisao-{r.id}')
    if aprovar:
        aplicar_vencidas()
    return True, 'Requisição aprovada.' if aprovar else 'Requisição reprovada.'


def cancelar(r, usuario):
    from models import db
    from app import PERFIS_ADMINISTRACAO_SISTEMA
    if not r or r.status not in STATUS_ABERTOS:
        return False, 'Só dá para cancelar uma requisição que ainda não foi aplicada.'
    if r.solicitante_id != usuario.id and usuario.tipo_usuario not in PERFIS_ADMINISTRACAO_SISTEMA:
        return False, 'Só quem pediu (ou um Administrador) pode cancelar.'
    r.status = CANCELADA
    r.resultado = f'Cancelada por {usuario.nome} em {datetime.now():%d/%m/%Y %H:%M}.'
    db.session.commit()
    return True, 'Requisição cancelada.'


def no_prazo(r, agora=None):
    return r.data_agendada is None or r.data_agendada <= (agora or datetime.now())


def aplicar_vencidas(agora=None):
    """Aplica as mudanças de parâmetros aprovadas cuja data agendada já chegou (chamado na decisão, na tela de
    parâmetros e pelas tarefas agendadas). Devolve quantas aplicou."""
    from models import db, RequisicaoMudanca
    import regras_negocio as rn
    aplicadas = 0
    for r in RequisicaoMudanca.query.filter_by(status=APROVADA, tipo='parametros').all():
        if not no_prazo(r, agora):
            continue
        dados = conteudo(r)
        valores = {c: novo for c, (_, novo) in (dados.get('valores') or {}).items()}
        if not valores:
            continue
        alteradas, erros = rn.salvar_varios(valores, r.solicitante_id, f"{dados.get('motivo') or r.titulo} ({numero(r)})")
        if erros:
            r.resultado = 'Não aplicada: ' + '; '.join(f'{rn.nome_da_regra(c)}: {e}' for c, e in erros.items())
        else:
            r.status, r.data_aplicacao, r.aplicado_por_id = APLICADA, datetime.now(), r.aprovador_id
            r.resultado = ', '.join(rn.nome_da_regra(c) for c in alteradas) or 'Os valores já estavam iguais.'
            aplicadas += 1
        db.session.commit()
    return aplicadas


def autorizacao_para_parametros(texto, idioma='pt'):
    """Na tela Parâmetros de regras só se salva com uma CR de parâmetros CRIADA E APROVADA (sem valores: ela autoriza
    a mudança que a pessoa faz na tela). Devolve (requisicao, erro em português)."""
    if not (texto or '').strip():
        return None, ('Para salvar, a requisição de mudança precisa estar criada e aprovada: crie a CR em “Criar Requisição '
                      'de Mudança” (Parâmetros e regras), espere a aprovação do grupo e informe o número dela aqui.')
    r = achar(texto)
    if not r:
        return None, 'Requisição de mudança não encontrada.'
    if r.tipo != 'parametros':
        return None, 'Esta requisição não é de parâmetros e regras.'
    if r.status == AGUARDANDO:
        return None, 'Esta requisição ainda aguarda a aprovação do grupo.'
    if r.status != APROVADA:
        return None, 'Esta requisição já foi encerrada (aplicada, reprovada ou cancelada). Crie outra.'
    if conteudo(r).get('valores'):
        return None, 'Esta requisição já traz os valores novos e passa a valer sozinha na aprovação (ou na data agendada).'
    if not no_prazo(r):
        return None, 'Esta requisição está agendada para mais tarde: salve a partir da data agendada.'
    return r, None


def registrar_uso(r, usuario, resumo):
    """A CR aprovada foi usada na tela Parâmetros de regras: fica Aplicada com o que mudou."""
    from models import db
    r.status, r.data_aplicacao, r.aplicado_por_id = APLICADA, datetime.now(), usuario.id
    r.resultado = resumo
    db.session.commit()


def registrar_commit(r, usuario, commit, correcoes):
    """O Orquestrador confirmou o commit com esta requisição: fica Aplicada com o commit e o que foi commitado."""
    from models import db
    r.status, r.data_aplicacao, r.aplicado_por_id = APLICADA, datetime.now(), usuario.id
    r.resultado = f"Commit {commit[:8]}\n" + '\n'.join(correcoes)
    db.session.commit()


# ------------------------------------------------------------------------------ listas para as telas
def abertas(tipo=None):
    from models import RequisicaoMudanca
    q = RequisicaoMudanca.query.filter(RequisicaoMudanca.status.in_(STATUS_ABERTOS))
    if tipo:
        q = q.filter_by(tipo=tipo)
    return q.order_by(RequisicaoMudanca.data_solicitacao.desc()).all()


def aprovadas_para_commit():
    """Requisições de código aprovadas e já na data agendada: as únicas que liberam o commit do Orquestrador."""
    return [r for r in abertas('codigo') if r.status == APROVADA and no_prazo(r)]


def todas(limite=200):
    from models import RequisicaoMudanca
    return RequisicaoMudanca.query.order_by(RequisicaoMudanca.data_solicitacao.desc()).limit(limite).all()
