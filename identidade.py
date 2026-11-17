# -*- coding: utf-8 -*-
"""
IDENTIDADE DA INSTITUIÇÃO
=========================
Cada cliente tem a sua própria instalação. Nenhum nome de instituição ou de programa fica fixo no código: as telas,
os e-mails, os certificados e o Assistente leem a identidade cadastrada em Administração › Sistema › Identidade da
instituição (tabela identidade_instituicao, uma linha só).

Campos:
- nome        nome completo da instituição (ex.: "Instituto Exemplo")
- apelido     sigla ou nome curto, usado em botões e rótulos curtos (ex.: "IEX" em "Reuniões IEX × B2B")
- plataforma  nome do programa ou da plataforma (ex.: "Programa de Mentoria 2026")
- logo, site, e-mail de contato e o cargo de quem assina o certificado pela instituição

Nos textos das telas (t() e tt()), os marcadores {instituicao}, {apelido} e {plataforma} são trocados pelo valor
cadastrado depois da tradução. Ex.: tt('Reuniões {apelido} × B2B') → "Reuniões IEX × B2B".
No Jinja: {{ marca.apelido }}, {{ marca.nome }}, {{ marca.plataforma }}, {{ marca.logo_url }}.

A leitura fica em cache por 30 segundos (cada processo do servidor) e é renovada na hora em quem salva.
"""
import time

PADRAO = {
    'nome': 'Instituição',
    'apelido': 'Instituição',
    'plataforma': 'Plataforma de Mentoria',
    'logo_arquivo': None,
    'site': '',
    'email_contato': '',
    'cargo_assinatura': 'Direção Institucional',
}
LIMITES = {'nome': 150, 'apelido': 30, 'plataforma': 120, 'site': 300, 'email_contato': 150, 'cargo_assinatura': 120}
VALIDADE_CACHE = 30.0
_CACHE = {'quando': 0.0, 'dados': None}
MARCADORES = ('{instituicao}', '{apelido}', '{plataforma}')


def _ler_do_banco():
    from models import IdentidadeInstituicao
    linha = IdentidadeInstituicao.query.order_by(IdentidadeInstituicao.id).first()
    if linha is None:
        return dict(PADRAO, configurada=False)
    dados = {campo: (getattr(linha, campo) or PADRAO[campo]) for campo in PADRAO}
    dados['logo_arquivo'] = linha.logo_arquivo
    dados['configurada'] = True
    dados['atualizado_em'] = linha.atualizado_em
    return dados


def obter():
    """Identidade vigente (dicionário). Fora de um app_context, ou com o banco indisponível, devolve o padrão."""
    agora = time.time()
    if _CACHE['dados'] is not None and agora - _CACHE['quando'] < VALIDADE_CACHE:
        return _CACHE['dados']
    try:
        dados = _ler_do_banco()
    except Exception:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return _CACHE['dados'] or dict(PADRAO, configurada=False)
    _CACHE.update(quando=agora, dados=dados)
    return dados


def limpar_cache():
    _CACHE.update(quando=0.0, dados=None)


def aplicar(texto):
    """Troca {instituicao}, {apelido} e {plataforma} pelos valores cadastrados (outros marcadores ficam como estão)."""
    if not isinstance(texto, str) or '{' not in texto or not any(m in texto for m in MARCADORES):
        return texto
    dados = obter()
    return (texto.replace('{instituicao}', dados['nome']).replace('{apelido}', dados['apelido'])
            .replace('{plataforma}', dados['plataforma']))


def salvar(campos, usuario_id=None):
    """Grava a identidade (cria a linha na primeira vez). Devolve a lista de erros ([] = salvo)."""
    from models import db, IdentidadeInstituicao
    limpos = {}
    for campo, limite in LIMITES.items():
        valor = ' '.join(str(campos.get(campo) or '').split())
        if len(valor) > limite:
            return [f'{campo}: máximo de {limite} caracteres.']
        limpos[campo] = valor
    erros = [f'{rotulo} é obrigatório.' for campo, rotulo in (('nome', 'O nome da instituição'), ('apelido', 'O apelido'),
                                                              ('plataforma', 'O nome da plataforma')) if not limpos[campo]]
    if limpos['site'] and not limpos['site'].lower().startswith(('https://', 'http://')):
        erros.append('O site deve começar com https://')
    if limpos['email_contato'] and ('@' not in limpos['email_contato'] or ' ' in limpos['email_contato']):
        erros.append('E-mail de contato inválido.')
    if erros:
        return erros
    linha = IdentidadeInstituicao.query.order_by(IdentidadeInstituicao.id).first()
    if linha is None:
        linha = IdentidadeInstituicao(**limpos)
        db.session.add(linha)
    else:
        for campo, valor in limpos.items():
            setattr(linha, campo, valor)
    linha.atualizado_por_id = usuario_id
    db.session.commit()
    limpar_cache()
    return []


def definir_logo(nome_arquivo):
    """Grava o nome do arquivo do logo (ou None) e devolve o nome do arquivo anterior, para apagar."""
    from models import db, IdentidadeInstituicao
    linha = IdentidadeInstituicao.query.order_by(IdentidadeInstituicao.id).first()
    if linha is None:
        linha = IdentidadeInstituicao(**{c: PADRAO[c] for c in LIMITES})
        db.session.add(linha)
    antigo = linha.logo_arquivo
    linha.logo_arquivo = nome_arquivo
    db.session.commit()
    limpar_cache()
    return antigo
