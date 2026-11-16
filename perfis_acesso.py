# -*- coding: utf-8 -*-
"""
PERFIS DE ACESSO PERSONALIZADOS
===============================
Um perfil personalizado herda de um dos perfis do sistema (o "perfil-base", gravado em usuario.tipo_usuario)
e liga/desliga MÓDULOS. Ele nunca ganha mais do que o perfil-base: todas as verificações que as telas já fazem
continuam valendo; o perfil personalizado só RESTRINGE.

  - MODULOS: catálogo de módulos com os endpoints de cada um;
  - MODULOS_POR_BASE: módulos que cada perfil-base tem de fato (o que pode ser ligado);
  - modulo_liberado(usuario, chave): usado no menu e nas telas;
  - endpoint_bloqueado(usuario, endpoint): usado no before_request do app.
"""
import json

PERFIS_BASE = ['Aluno', 'Professor', 'Mentor', 'Mentor Administrador', 'Administrador', 'Admin B2B', 'Avaliador Banca']

# chave: (rótulo em português, ícone, endpoints do módulo, obrigatório)
MODULOS = {
    'painel': ('Painel Geral', 'bi-speedometer2', ['dashboard', 'salvar_graficos_painel'], True),
    'sessoes': ('Sessões', 'bi-calendar-check', ['sessoes', 'sincronizar_sessao_aluno'], False),
    'acompanhamento': ('Acompanhamento', 'bi-graph-up-arrow',
                       ['acompanhamento', 'fazer_checkin_aula', 'sincronizar_agenda_acompanhamento', 'conectar_agenda',
                        'desconectar_agenda', 'chat_ia'], False),
    # oauth2callback fica fora dos módulos: é o retorno do Google comum à Agenda e ao Gmail das reuniões (exige login)
    'atividades_extras': ('Atividades extras', 'bi-people-fill',
                          ['atividades_extras', 'nova_atividade_extra', 'acao_atividade_extra', 'relatorio_atividade_extra'], False),
    'hub': ('Hub Educacional', 'bi-diagram-3-fill', ['gerenciar_turmas', 'editar_curso', 'deletar_curso', 'api_mentores_empresa'], False),
    'diario': ('Diário de Classe (frequência e notas)', 'bi-journal-check', ['gerenciar_frequencia', 'gerenciar_notas'], False),
    'projetos': ('Projetos (TCC)', 'bi-kanban',
                 ['projetos', 'nova_tarefa', 'atualizar_tarefa', 'deletar_tarefa', 'deletar_projeto', 'avaliar_projeto',
                  'enviar_entrega_tcc', 'aprovar_versao_final'], False),
    'bancas': ('Bancas (Minhas bancas e Sala da Banca)', 'bi-person-video3',
               ['minhas_bancas', 'painel_banca', 'relogio_banca', 'perguntas_banca', 'cronometro_banca',
                'estado_cronometro_banca', 'telao_banca', 'ficha_banca'], False),
    'biblioteca': ('Biblioteca de TCCs', 'bi-journal-bookmark', ['biblioteca_tccs', 'baixar_acervo'], False),
    'certificados': ('Certificados', 'bi-award', ['meus_certificados', 'emitir_certificado'], False),
    'demandas': ('Portal de Demandas', 'bi-headset', ['portal_demandas'], False),
    'voluntariado': ('Relógio de voluntariado e relatórios ESG', 'bi-stopwatch',
                     ['bater_ponto_voluntariado', 'lancamento_manual_voluntariado', 'exportar_relatorio_esg', 'exportar_relatorio_esg_pdf'], False),
    'cadastros': ('Cadastros e grupos', 'bi-people', ['gerenciar_usuarios', 'editar_usuario', 'gerenciar_grupos', 'editar_grupo', 'deletar_grupo'], False),
    'solicitacoes': ('Solicitações de mentoria', 'bi-envelope-paper', ['gerenciar_solicitacoes', 'acao_solicitacao'], False),
    'trilha_gestao': ('Gestão da trilha do TCC', 'bi-mortarboard', ['gestao_trilha_tcc'], False),
    'reunioes': ('Reuniões ITM × B2B', 'bi-journal-text', ['reunioes', 'editar_reuniao', 'detalhe_reuniao', 'agenda_reuniao_ics',
                                                         'enviar_convite', 'conectar_gmail', 'desconectar_gmail'], False),
    'agenda_bancas': ('Agenda de bancas e avaliadores', 'bi-calendar-event', ['agenda_bancas', 'avaliadores_banca', 'curriculo_avaliador'], False),
    'indicadores': ('Indicadores de voluntariado', 'bi-bar-chart-line', ['indicadores_voluntariado', 'indicadores_voluntariado_csv'], False),
    'perfis_acesso': ('Perfis de acesso', 'bi-person-gear', ['perfis_acesso_view'], False),
    'parametros': ('Parâmetros de regras', 'bi-sliders', ['parametros_regras'], False),
    'agentes_ia': ('Agentes IA e governança de aprendizados', 'bi-robot',
                   ['agentes_ia', 'iniciar_agentes_ia', 'parar_agentes_ia', 'estado_agentes_ia_json', 'quadro_agentes_ia',
                    'arquivo_agentes_ia', 'governanca_aprendizados', 'governanca_aprendizados_csv', 'agentes_seguranca',
                    'iniciar_agentes_seguranca', 'parar_agentes_seguranca', 'estado_agentes_seguranca_json', 'aprender_agentes_seguranca',
                    'agentes_banco', 'iniciar_agentes_banco', 'parar_agentes_banco', 'estado_agentes_banco_json', 'aprender_agentes_banco',
                    'manutencao_agentes_banco', 'agentes_funcionalidades', 'iniciar_agentes_funcionalidades', 'parar_agentes_funcionalidades',
                    'estado_agentes_funcionalidades_json', 'quadro_agentes_funcionalidades', 'aprender_agentes_funcionalidades',
                    'agentes_orquestrador', 'iniciar_orquestrador', 'ignorar_correcao', 'estado_orquestrador_json',
                    'diff_orquestrador', 'confirmar_orquestrador', 'rollback_orquestrador', 'desfazer_orquestrador',
                    'parar_orquestrador'], False),
    'manutencao': ('Manutenção do banco de dados', 'bi-database-fill-gear', ['manutencao_banco', 'baixar_backup', 'relatorio_auditoria_backup'], False),
}

_comum = ['painel', 'biblioteca', 'certificados', 'demandas']
_aprendizagem = ['sessoes', 'acompanhamento', 'atividades_extras', 'projetos']
_gestao = ['hub', 'diario', 'bancas', 'voluntariado', 'reunioes', 'agenda_bancas', 'indicadores']
MODULOS_POR_BASE = {
    'Aluno': _comum + _aprendizagem,
    'Professor': _comum + _aprendizagem + ['diario', 'bancas', 'voluntariado'],
    'Mentor': _comum + _aprendizagem + ['diario', 'bancas', 'voluntariado'],
    'Mentor Administrador': _comum + _aprendizagem + _gestao + ['cadastros', 'solicitacoes', 'trilha_gestao'],
    'Administrador': _comum + _aprendizagem + _gestao + ['cadastros', 'trilha_gestao', 'perfis_acesso', 'parametros', 'agentes_ia', 'manutencao'],
    'Admin B2B': _comum + _aprendizagem + _gestao,
    'Avaliador Banca': _comum + ['bancas', 'voluntariado'],
}

MODULO_DO_ENDPOINT = {ep: chave for chave, (_, _, eps, _) in MODULOS.items() for ep in eps}


def modulos_validos(perfil_base, escolhidos):
    """Só módulos que o perfil-base tem; o Painel Geral é sempre incluído."""
    disponiveis = MODULOS_POR_BASE.get(perfil_base, [])
    return [m for m in disponiveis if m in set(escolhidos or []) or MODULOS[m][3]]


def _perfil(usuario):
    return getattr(usuario, 'perfil_personalizado', None) if getattr(usuario, 'perfil_personalizado_id', None) else None


def modulo_liberado(usuario, chave):
    """True quando o utilizador pode usar o módulo (perfis padrão: sempre; personalizados: conforme a lista)."""
    perfil = _perfil(usuario)
    if perfil is None or MODULOS.get(chave, (None, None, None, False))[3]:
        return True
    return bool(perfil.ativo) and chave in perfil.lista_modulos()


def endpoint_bloqueado(usuario, endpoint):
    """Módulo do endpoint quando o perfil personalizado não o libera (None = liberado)."""
    modulo = MODULO_DO_ENDPOINT.get(endpoint)
    if modulo and not modulo_liberado(usuario, modulo):
        return modulo
    return None


def nome_do_perfil(usuario):
    perfil = _perfil(usuario)
    return perfil.nome if perfil else usuario.tipo_usuario


def resolver_nivel(valor):
    """Valor do campo 'Nível' do cadastro → (tipo_usuario, perfil_personalizado_id) ou None se inválido.
    Perfis padrão: 'Mentor'; perfis personalizados: 'custom:<id>'."""
    from models import PerfilPersonalizado, db
    valor = (valor or '').strip()
    if valor in PERFIS_BASE:
        return valor, None
    if valor.startswith('custom:') and valor[7:].isdigit():
        perfil = db.session.get(PerfilPersonalizado, int(valor[7:]))
        if perfil and perfil.ativo:
            return perfil.perfil_base, perfil.id
    return None


def descrever(perfil):
    return json.dumps({'nome': perfil.nome, 'base': perfil.perfil_base, 'modulos': perfil.lista_modulos(),
                       'ativo': bool(perfil.ativo)}, ensure_ascii=False)
