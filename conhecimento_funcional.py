# -*- coding: utf-8 -*-
"""
CONHECIMENTO FUNCIONAL — o que o Gerente de Funcionalidades aprende e ensina aos agentes de cada perfil
====================================================================================================
Mesmas regras de governança dos outros gerentes (conhecimento.py): assinatura SHA-256, trilha de eventos,
revogação e limpeza para compliance na tela Governança de aprendizados.

1. Detecção interna (autônoma, aplicada na hora): o Gerente lê as REGRAS DE NEGÓCIO da própria plataforma e ensina
   aos agentes — as expectativas dos testes vêm daqui, não de listas fixas no código dos agentes:
     - módulos de cada perfil (perfis_acesso.MODULOS_POR_BASE) e as páginas de cada módulo → matriz de acesso;
     - regras de perfis do app (quem cadastra projeto, quem gere bancas, quem cria atividades, quem faz a trilha…);
     - versão do termo de voluntariado e rotas novas (que ainda não têm teste funcional próprio).
   Quando uma regra muda, os agentes passam a esperar o novo comportamento na próxima execução.
2. Fontes oficiais (só domínios da lista de Fontes confiáveis, HTTPS): para cada tipo de falha encontrada, o Gerente
   propõe a página oficial que ensina o assunto (OWASP para permissões e validação, gov.br para LGPD). Fica PENDENTE.
"""
import re
import json
from datetime import datetime

from flask import current_app

import conhecimento
from conhecimento import criar_aprendizado, aprendizados_para, registrar_consumo, evento, _estado, _gravar_estado
from models import db, AprendizadoAgente

GERENTE_FUNCIONAL = 'Gerente de Funcionalidades'
GRUPO = 'funcionalidades'
ORDEM = ['administrador', 'mentor_administrador', 'gestor_parceiro', 'professor', 'mentor', 'aluno', 'avaliador', 'encerramento']
AGENTES_FUNCIONAIS = [f"fn_{c}" for c in ORDEM]
PERFIL_DO_AGENTE = {'administrador': 'Administrador', 'mentor_administrador': 'Mentor Administrador', 'gestor_parceiro': 'Admin B2B',
                    'professor': 'Professor', 'mentor': 'Mentor', 'aluno': 'Aluno', 'avaliador': 'Avaliador Banca',
                    'encerramento': 'Mentor Administrador'}
REGRAS_DO_APP = ['PERFIS_SEM_CADASTRO_PROJETO', 'PERFIS_CRIAM_ATIVIDADE_EXTRA', 'PERFIS_GESTAO_REUNIOES', 'PERFIS_GESTAO_BANCA',
                 'PERFIS_ESCALAVEIS_BANCA', 'PERFIS_TRILHA_TCC', 'VERSAO_TERMO_ATUAL', 'TIPOS_ENTREGA_TCC', 'LIMITE_ENTREGA_MB',
                 'PERFIS_DUVIDAS_ACOMPANHAMENTO', 'PERFIS_GESTAO_CURSOS']
ACOES = re.compile(r"excluir|apagar|deletar|remover|logout|sair|executar|restaurar|limpar|desconectar|parar|iniciar|encerrar|aprovar|"
                   r"rejeitar|reabrir|cancelar|toggle|alternar|marcar|sincronizar|forcar|reset|exportar|baixar|arquivo|csv|json|pdf|quadro|"
                   r"google|oauth|autoriz|conectar|aprender|manutencao", re.I)
DOC_POR_CATEGORIA = {
    'Permissão do perfil': ('https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html', 'OWASP: controle de autorização por perfil'),
    'Validação de dados': ('https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html', 'OWASP: validação de entradas'),
    'Primeiro acesso e onboarding': ('https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html', 'OWASP: autenticação'),
    'Integridade dos dados': ('https://docs.sqlalchemy.org/en/20/orm/session_basics.html', 'SQLAlchemy: sessão e transações'),
}


# ------------------------------------------------------------------------------ retrato das regras de negócio
# Ferramentas dos próprios agentes: telas dos agentes, governança, credenciais dos agentes e o Orquestrador (que altera o
# código e só roda com aprovação do Administrador: nunca é exercitado pelos testes de fim a fim)
FERRAMENTA = re.compile(r"^((iniciar|parar|aprender|estado|quadro|manutencao)_)?agentes_|^governanca_|^arquivo_agentes"
                        r"|_orquestrador$|^credenciais_agentes|^ignorar_correcao$")


def eh_ferramenta(endpoint):
    """Telas e botões dos próprios agentes (não são funções de negócio da plataforma)."""
    return bool(FERRAMENTA.search(endpoint))


def _valor_json(valor):
    if isinstance(valor, dict):
        return {k: sorted(v) if isinstance(v, (set, list, tuple)) else v for k, v in valor.items()}
    if isinstance(valor, (set, tuple)):
        return sorted(valor)
    return valor


def retrato_regras():
    import app as modulo_app
    import perfis_acesso
    rotas_get = {}
    for r in current_app.url_map.iter_rules():
        if 'GET' in r.methods and not r.arguments and r.endpoint != 'static' and not ACOES.search(r.endpoint):
            rotas_get.setdefault(r.endpoint, r.rule)
    rotas_post = sorted({r.endpoint for r in current_app.url_map.iter_rules() if 'POST' in r.methods and not eh_ferramenta(r.endpoint)})
    return {
        'modulos_por_base': {k: sorted(v) for k, v in perfis_acesso.MODULOS_POR_BASE.items()},
        'modulos': {k: sorted(e for e in eps if e in rotas_get) for k, (_, _, eps, _) in perfis_acesso.MODULOS.items()},
        'rotas_get': rotas_get,
        'rotas_post': rotas_post,
        'regras_app': {nome: _valor_json(getattr(modulo_app, nome)) for nome in REGRAS_DO_APP if hasattr(modulo_app, nome)},
    }


def _criar(titulo, tipo, conteudo, destino, descricao, origem, **extra):
    return criar_aprendizado(titulo, tipo, conteudo, destino, descricao, origem, gerente=GERENTE_FUNCIONAL, **extra)


def _agentes_do_endpoint(endpoint, retrato):
    modulo = next((m for m, eps in retrato['modulos'].items() if endpoint in eps), None)
    if not modulo:
        return [GRUPO]
    return [f"fn_{c}" for c, perfil in PERFIL_DO_AGENTE.items() if modulo in retrato['modulos_por_base'].get(perfil, [])] or [GRUPO]


# ------------------------------------------------------------------------------ 1. detecção interna (autônoma)
def detectar_mudancas(origem=GERENTE_FUNCIONAL):
    atual = retrato_regras()
    anterior = _estado('retrato_funcional', None)
    criados = []
    if anterior is None:
        criados.append(_criar('Linha de base das regras de negócio registrada', 'fn_linha_base', atual, [GRUPO],
                              f"{len(atual['modulos_por_base'])} perfis, {len(atual['modulos'])} módulos, {len(atual['rotas_post'])} funções que gravam dados.",
                              origem))
        anterior = atual
    mudou = {k: atual[k] for k in ('modulos_por_base', 'modulos', 'regras_app') if anterior.get(k) != atual[k]}
    if mudou:
        partes = []
        for chave in mudou:
            if chave == 'regras_app':
                partes += [n for n in atual['regras_app'] if anterior.get('regras_app', {}).get(n) != atual['regras_app'][n]]
            else:
                partes.append(chave)
        criados.append(_criar(f"Regras de negócio mudaram: {', '.join(partes)[:150]}", 'fn_regra', atual, [GRUPO],
                              'Os agentes passam a esperar o novo comportamento (matriz de acesso e regras de cada perfil).', origem))
    novas = sorted(set(atual['rotas_post']) - set(anterior.get('rotas_post', [])))
    if novas:
        destino = sorted({a for e in novas for a in _agentes_do_endpoint(e, atual)})
        criados.append(_criar(f"{len(novas)} função(ões) nova(s) sem teste funcional próprio", 'fn_rota_nova', {'endpoints': novas}, destino,
                              'Os agentes avisam que estas funções ainda não têm um passo no fluxo de teste: ' + ', '.join(novas[:8]), origem))
    _gravar_estado('retrato_funcional', atual)
    _gravar_estado('ultima_deteccao_funcional', {'em': datetime.now().isoformat(timespec='seconds'), 'origem': origem, 'novos': len(criados)})
    db.session.commit()
    return criados


# ------------------------------------------------------------------------------ consumo pelos agentes
def para_agente(chave_agente, tipos=None):
    alvo = f"fn_{chave_agente}"
    itens = [a for a in aprendizados_para(alvo, tipos) if a.tipo.startswith('fn_')
             or (a.tipo == 'referencia_externa' and alvo in json.loads(a.agentes_destino or '[]'))]
    grupo = [a for a in aprendizados_para(GRUPO, tipos) if a not in itens and GRUPO in json.loads(a.agentes_destino or '[]')]
    return sorted(itens + grupo, key=lambda a: a.id)


def consumir(chave_agente, itens):
    registrar_consumo(f"Agente funcional {chave_agente}", itens)


def regras_aprendidas(itens):
    """As regras mais recentes aprendidas (linha de base ou última mudança) + funções novas sem teste."""
    regras = {}
    for a in itens:
        dados = json.loads(a.conteudo)
        if a.tipo in ('fn_linha_base', 'fn_regra'):
            regras = {**regras, **dados, 'aprendizado': a.codigo}
        elif a.tipo == 'fn_rota_nova':
            regras.setdefault('funcoes_novas', []).extend(e for e in dados.get('endpoints', []) if not eh_ferramenta(e))
    return regras


# ------------------------------------------------------------------------------ 2. fontes oficiais (pendentes até aprovação)
def aprender_com_falhas(relatorios, origem=GERENTE_FUNCIONAL):
    criados = []
    for rel in relatorios:
        categorias = {t['categoria'] for t in rel.get('testes', []) if t['resultado'] != 'Aprovado'}
        for categoria in sorted(categorias):
            if categoria not in DOC_POR_CATEGORIA:
                continue
            url, tema = DOC_POR_CATEGORIA[categoria]
            if AprendizadoAgente.query.filter(AprendizadoAgente.tipo == 'referencia_externa', AprendizadoAgente.fonte_url == url,
                                              AprendizadoAgente.agentes_destino.like(f'%fn_{rel["chave"]}%')).first():
                continue
            try:
                criados.append(conhecimento.buscar_fonte_oficial(url, tema, gerente=GERENTE_FUNCIONAL, destino=[f"fn_{rel['chave']}"]))
            except Exception as e:
                db.session.rollback()
                evento('Busca recusada', f"{url}: {e}", agente=GERENTE_FUNCIONAL)
                db.session.commit()
    return criados


# ------------------------------------------------------------------------------ 3. ensinar as outras equipes de agentes
# Regras de negócio que o fluxo funcional valida e que as outras equipes também precisam vigiar sempre.
# Cada regra leva as instruções de verificação para cada agente que a recebe (a chave 'agente' é o destino):
#   seg_* = Agentes de Segurança · db_* = Agentes de Banco de Dados · demais = agentes de teste fim a fim (por perfil).
E2E = ['administrador', 'aluno', 'professor', 'mentor', 'mentor_administrador', 'gestor_b2b', 'avaliador', 'perfis_personalizados']
NOTAS_0_A_10 = {'acompanhamento': ['nota_tecnica', 'nota_postura'], 'projeto': ['nota_conteudo', 'nota_apresentacao', 'nota_visual', 'nota_final'],
                'avaliacao_banca': ['nota_escrita', 'nota_apresentacao', 'nota_visual']}
REGRAS_ENSINAVEIS = [
    {'chave': 'escalada_criar_administrador', 'teste': 'Mentor Administrador não cria Administrador',
     'titulo': 'Só o Administrador cria, promove ou altera Administradores',
     'verificacoes': [
         {'agente': 'seg_pentest', 'tipo': 'criacao_proibida', 'perfil': 'Mentor Administrador', 'rota': '/admin/usuarios',
          'campos': {'tipo_usuario': 'Administrador', 'status': 'Ativo', 'forcar_troca_senha': 'False'}},
         {'agente': 'mentor_administrador', 'tipo': 'opcao_proibida', 'pagina': '/admin/usuarios', 'seletor': '#tipo_usuario_novo', 'valor': 'Administrador'}]},
    {'chave': 'tarefa_de_outro_grupo', 'teste': 'Aluno não cria tarefa em projeto de outro grupo',
     'titulo': 'Só o grupo do projeto e a gestão mexem nas tarefas e no projeto',
     'verificacoes': [{'agente': 'seg_pentest', 'tipo': 'recurso_de_outro_grupo', 'perfil': 'Aluno', 'rota': '/projetos/nova_tarefa', 'campo': 'projeto_id'}]},
    {'chave': 'troca_senha_obrigatoria_global', 'teste': 'Troca de senha obrigatória bloqueia o painel',
     'titulo': 'Troca de senha obrigatória vale para todas as páginas (inclusive depois da recuperação)',
     'verificacoes': [{'agente': 'seg_pentest', 'tipo': 'troca_senha_global', 'paginas': ['/dashboard', '/projetos']}]
                     + [{'agente': a, 'tipo': 'troca_senha_global_ui', 'pagina': '/dashboard'} for a in E2E if a != 'perfis_personalizados']},
    {'chave': 'politica_senha_em_todo_cadastro', 'teste': 'Importação por CSV com senha provisória forte e troca obrigatória',
     'titulo': 'Todo cadastro ou troca de senha aplica a política de senha forte',
     'verificacoes': [{'agente': 'seg_codigo', 'tipo': 'politica_senha_codigo', 'padrao': 'PADRAO_SENHA_FORTE'}]},
    {'chave': 'conta_nova_sem_heranca', 'teste': 'Contas novas nascem sem dados de outra conta',
     'titulo': 'Conta nova nunca herda credenciais de um usuário apagado (sem órfãos de usuário)',
     'verificacoes': [{'agente': 'seg_dados', 'tipo': 'credenciais_orfas',
                       'tabelas': ['seguranca_usuario', 'termo_aceite', 'historico_senha', 'conclusao_modulo_tcc']}]},
    {'chave': 'notas_de_0_a_10', 'teste': 'Notas fora de 0 a 10 são recusadas', 'titulo': 'Notas sempre entre 0 e 10',
     'verificacoes': [{'agente': 'seg_dados', 'tipo': 'faixa_numerica', 'colunas': NOTAS_0_A_10, 'min': 0, 'max': 10},
                      {'agente': 'db_esquema', 'tipo': 'faixa_numerica', 'colunas': NOTAS_0_A_10, 'min': 0, 'max': 10},
                      {'agente': 'professor', 'tipo': 'campos_com_faixa', 'pagina': '/admin/notas', 'prefixos': ['nota_tecnica_', 'nota_postura_'],
                       'min': '0', 'max': '10'}]},
]


def _destino_do_agente(agente):
    return agente if agente.startswith(('seg_', 'db_')) else agente


def ensinar_outros_agentes(relatorios=None, origem=GERENTE_FUNCIONAL):
    """Publica cada regra verificada pelo fluxo para as equipes de Segurança, Banco de Dados e testes fim a fim
    (aplicada na hora, revogável na Governança). Atualiza o resultado da última execução do fluxo."""
    resultado_por_teste = {}
    for rel in relatorios or []:
        for t in rel.get('testes', []):
            resultado_por_teste[t['titulo']] = {'resultado': t['resultado'], 'agente': rel['nome']}
    criados = []
    for regra in REGRAS_ENSINAVEIS:
        existente = AprendizadoAgente.query.filter(AprendizadoAgente.tipo == 'regra_verificada',
                                                   AprendizadoAgente.conteudo.like(f'%"chave": "{regra["chave"]}"%')).first()
        ultimo = resultado_por_teste.get(regra['teste'])
        if existente:
            if ultimo:
                evento('Regra verificada novamente', f"{regra['chave']}: {ultimo['resultado']} ({ultimo['agente']})", existente.codigo, GERENTE_FUNCIONAL)
            continue
        destino = sorted({_destino_do_agente(v['agente']) for v in regra['verificacoes']})
        conteudo = {**regra, 'validada_por': ultimo['agente'] if ultimo else 'Agentes de Funcionalidades'}
        criados.append(_criar(f"Regra de negócio para vigiar: {regra['titulo']}", 'regra_verificada', conteudo, destino,
                              f"Validada no fluxo funcional; {len(regra['verificacoes'])} verificação(ões) para {', '.join(destino)[:200]}.", origem))
    db.session.commit()
    return criados


def verificacoes_para(itens, agente):
    """Instruções de verificação das regras aprendidas para um agente específico."""
    saida = []
    for a in itens:
        if a.tipo != 'regra_verificada':
            continue
        dados = json.loads(a.conteudo)
        for v in dados.get('verificacoes', []):
            if v['agente'] == agente:
                saida.append({**v, 'regra': dados['titulo'], 'codigo': a.codigo})
    return saida


def resumo_para_tela():
    contagem = {a: {'Aplicado': 0, 'Pendente': 0} for a in [GRUPO] + AGENTES_FUNCIONAIS}
    for a in AprendizadoAgente.query.filter(AprendizadoAgente.status.in_(['Aplicado', 'Pendente'])).all():
        for destino in json.loads(a.agentes_destino or '[]'):
            if destino in contagem:
                contagem[destino][a.status] += 1
    return {'contagem': contagem, 'ultima': _estado('ultima_deteccao_funcional', None)}
