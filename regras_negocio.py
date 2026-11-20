# -*- coding: utf-8 -*-
"""
PARÂMETROS DAS REGRAS DE NEGÓCIO
================================
Um único lugar para os números que definem as regras da plataforma (frequência mínima do MEC, nota de aprovação,
pesos da banca, política de senha...). A gestão muda pela tela Administração › Parâmetros de regras; o código lê com
    from regras_negocio import regra
    regra('freq_minima_pct')   # → 75
Sem valor gravado (ou fora de uma requisição), vale o padrão do catálogo — o sistema funciona igual a antes.
Regras novas criadas pela gestão ficam disponíveis do mesmo jeito: regra('minha_regra').
"""
import re
from datetime import datetime

# ------------------------------------------------------------------------------ catálogo
GRUPOS = [
    ('frequencia', 'Frequência (regra do MEC)', 'bi-calendar-check'),
    ('notas', 'Notas do diário de classe', 'bi-journal-check'),
    ('banca', 'Banca do TCC', 'bi-award'),
    ('seguranca', 'Senhas e acesso', 'bi-shield-lock'),
    ('acompanhamento', 'Ocorrências e acompanhamento', 'bi-exclamation-triangle'),
    ('avaliacoes', 'Avaliações e alertas', 'bi-star-half'),
    ('reunioes', 'Reuniões com os parceiros B2B', 'bi-journal-text'),
    ('cursos', 'Conteúdo dos cursos (aulas e testes)', 'bi-play-btn'),
    ('ia','Inteligência artificial (custos)', 'bi-cpu'),
    ('personalizadas', 'Regras criadas pela gestão', 'bi-plus-square'),
]

# chave: (grupo, nome, descrição, tipo, padrão, mínimo, máximo, unidade, onde é usada)
CATALOGO = {
    'freq_minima_pct': ('frequencia', 'Frequência mínima para aprovação',
                        'Abaixo desta frequência o aluno é reprovado por faltas (LDB/MEC: 75%). Faltas justificadas não contam.',
                        'inteiro', 75, 1, 100, '%', 'Diário de classe (situação do aluno) e indicadores de frequência'),
    'freq_alerta_cota_pct': ('frequencia', 'Alerta de risco por faltas',
                             'O aluno entra em risco quando já usou esta parte da cota de faltas permitida.',
                             'inteiro', 75, 1, 100, '% da cota', 'Diário de classe e indicadores de frequência'),
    'freq_dias_letivos_semana': ('frequencia', 'Dias letivos por semana',
                                 'Usado para estimar quantas aulas a turma já teve desde o início.',
                                 'inteiro', 5, 1, 7, 'dias', 'Cálculo da frequência esperada'),
    'nota_minima_diario': ('notas', 'Média mínima para aprovação no diário',
                           'Média entre a nota técnica e a de postura de cada disciplina. Abaixo dela, o aluno é reprovado por nota.',
                           'decimal', 7.0, 0, 10, 'de 0 a 10', 'Diário de classe › Gestão de notas'),
    'banca_nota_aprovacao': ('banca', 'Nota final mínima para aprovar o TCC',
                             'Com nota final abaixo deste valor, o projeto vai para Recuperação.',
                             'decimal', 7.0, 0, 10, 'de 0 a 10', 'Encerramento da banca'),
    'banca_peso_escrito': ('banca', 'Peso do trabalho escrito na nota final', 'Os três pesos da banca precisam somar 100%.',
                           'inteiro', 40, 0, 100, '%', 'Nota final da banca'),
    'banca_peso_apresentacao': ('banca', 'Peso da apresentação oral na nota final', 'Os três pesos da banca precisam somar 100%.',
                                'inteiro', 40, 0, 100, '%', 'Nota final da banca'),
    'banca_peso_visual': ('banca', 'Peso do material visual na nota final', 'Os três pesos da banca precisam somar 100%.',
                          'inteiro', 20, 0, 100, '%', 'Nota final da banca'),
    'banca_nota_exige_justificativa': ('banca', 'Nota que exige justificativa do avaliador',
                                       'Notas abaixo deste valor só são aceitas com justificativa escrita.',
                                       'decimal', 7.0, 0, 10, 'de 0 a 10', 'Formulário de avaliação da banca'),
    'banca_justificativa_min': ('banca', 'Tamanho mínimo da justificativa', 'Quantidade mínima de caracteres da justificativa.',
                                'inteiro', 10, 1, 500, 'caracteres', 'Formulário de avaliação da banca'),
    'senha_min_caracteres': ('seguranca', 'Tamanho mínimo da senha',
                             'Toda senha também exige letra maiúscula, minúscula, número e caractere especial.',
                             'inteiro', 10, 8, 64, 'caracteres', 'Cadastro, troca e recuperação de senha'),
    'login_tentativas_bloqueio': ('seguranca', 'Tentativas de login antes do bloqueio',
                                  'Depois deste número de senhas erradas seguidas, a conta é bloqueada.',
                                  'inteiro', 5, 3, 20, 'tentativas', 'Login'),
    'senha_dias_expiracao': ('seguranca', 'Validade da senha', 'Dias até a plataforma pedir uma senha nova (aviso no painel).',
                             'inteiro', 90, 15, 365, 'dias', 'Painel (aviso de troca de senha)'),
    'ocorrencia_prazo_dias': ('acompanhamento', 'Prazo para responder uma ocorrência',
                              'Prazo padrão para o responsável dar o retorno (feedback); quem registra pode mudar a data.',
                              'inteiro', 3, 1, 30, 'dias', 'Ocorrências (prazo e sinal vermelho de atraso)'),
    'ocorrencia_alerta_dias': ('acompanhamento', 'Aviso antes do prazo da ocorrência',
                               'Sinal amarelo quando faltam estes dias (ou menos) e o responsável ainda não respondeu.',
                               'inteiro', 1, 0, 10, 'dias', 'Ocorrências (sinal amarelo)'),
    'ruido_comunicacao_limite': ('avaliacoes', 'Limite do alerta de ruído de comunicação',
                                 'Média de "Comunicação" (e de "Engajamento") recebida nas avaliações abaixo deste valor gera alerta.',
                                 'decimal', 3.5, 1, 5, 'de 1 a 5', 'Avaliações › Alertas de acompanhamento'),
    'gravacao_reuniao_limite_mb': ('reunioes', 'Tamanho máximo do arquivo da gravação',
                                   'Maior arquivo de gravação (vídeo ou áudio) que a gestão pode enviar para a reunião. '
                                   'Ajuste conforme o espaço em disco do servidor. No servidor Ubuntu, o Nginx precisa aceitar '
                                   'o mesmo tamanho na rota da gravação.',
                                   'inteiro', 100, 10, 4096, 'MB', 'Reuniões › Gravação'),
    'aula_video_percentual_minimo': ('cursos', 'Quanto do vídeo o aluno precisa assistir',
                                     'Parte do vídeo da aula (em segundos realmente assistidos, sem contar o que foi pulado) '
                                     'para o vídeo contar como concluído no progresso automático.',
                                     'inteiro', 90, 50, 100, '%', 'Meus cursos › Vídeo da aula'),
    'aula_teste_nota_minima': ('cursos', 'Nota mínima no teste da aula',
                               'Acertos necessários no teste de conhecimento para a aula contar como concluída. '
                               'O aluno pode refazer o teste quantas vezes quiser; vale a melhor nota.',
                               'inteiro', 70, 0, 100, '%', 'Meus cursos › Teste de conhecimento'),
    'aula_teste_questoes': ('cursos', 'Perguntas por teste gerado',
                            'Quantas perguntas a IA (ou o gerador automático) escreve para cada aula. A gestão pode editar, '
                            'apagar e acrescentar perguntas depois.',
                            'inteiro', 3, 1, 10, 'perguntas', 'Hub Educacional › Conteúdo do curso'),
    'video_aula_limite_mb': ('cursos', 'Tamanho máximo do vídeo da aula',
                             'Maior arquivo de vídeo que a gestão pode enviar para uma aula. Ajuste conforme o espaço em disco '
                             'do servidor. No servidor Ubuntu, o Nginx precisa aceitar o mesmo tamanho na rota do vídeo da aula.',
                             'inteiro', 100, 10, 4096, 'MB', 'Hub Educacional › Conteúdo do curso'),
    'desengajamento_dias': ('avaliacoes','Dias sem atividade para o alerta de desengajamento',
                            'Jovem ou mentor sem nenhuma atividade na plataforma (login, frequência, sessão, entrega, presença) por estes dias.',
                            'inteiro', 14, 3, 90, 'dias', 'Avaliações › Alertas de acompanhamento'),
    'micro_avaliacao_dias': ('avaliacoes', 'Frequência da microavaliação',
                             'A cada quantos dias abre sozinha uma microavaliação (jovem ↔ mentor, 1 a 5). Zero desliga.',
                             'inteiro', 15, 0, 90, 'dias', 'Avaliações (rotina de hora em hora)'),
    'checkout_esquecido_minutos': ('acompanhamento', 'Aviso de saída esquecida',
                                   'Minutos depois do fim previsto (reunião, atividade extra ou banca) para avisar por e-mail quem não fez o check-out. A rotina roda de hora em hora.',
                                   'inteiro', 30, 10, 240, 'minutos', 'Lembretes automáticos (e-mail)'),
    'relogio_esquecido_horas': ('acompanhamento', 'Aviso do relógio de voluntariado aberto',
                                'Horas com o relógio de voluntariado aberto (sem fim previsto) para lembrar o check-out.',
                                'inteiro', 4, 1, 24, 'horas', 'Lembretes automáticos (e-mail)'),
    'prazo_tcc_aviso_horas': ('acompanhamento', 'Aviso antes do prazo de entrega do TCC',
                              'Horas antes do prazo do escrito ou dos slides para avisar por e-mail o grupo que ainda não entregou.',
                              'inteiro', 48, 12, 168, 'horas', 'Lembretes automáticos (e-mail)'),
    'avaliacao_minimo_respostas': ('avaliacoes', 'Mínimo de avaliações para mostrar resultados',
                                   'A pessoa só vê o que recebeu (sem nomes) e os alertas só disparam a partir deste número de avaliações.',
                                   'inteiro', 2, 1, 10, 'avaliações', 'Avaliações › Resultados e alertas'),
    'ia_teto_mensal_usd': ('ia', 'Teto de gasto mensal com IA',
                           'Somando todas as IAs (Assistente, Acompanhamento e Orquestrador). Ao atingir o teto, as IAs param até o mês '
                           'seguinte: o Assistente passa a mostrar só os trechos encontrados. Zero desliga as IAs.',
                           'decimal', 10.0, 0, 10000, 'US$ por mês', 'Provedores de IA (todas as chamadas)'),
    'ia_aviso_teto_pct': ('ia', 'Aviso antes do teto',
                          'Avisa os Administradores (sino e e-mail) quando o gasto do mês chega a esta parte do teto.',
                          'inteiro', 80, 10, 100, '% do teto', 'Provedores de IA (aviso)'),
    'assistente_trechos': ('ia', 'Trechos enviados à IA por pergunta',
                           'Quantos trechos da base de conhecimento vão junto com cada pergunta. Menos trechos = resposta mais barata.',
                           'inteiro', 5, 2, 12, 'trechos', 'Assistente da Plataforma'),
    'assistente_cache_dias': ('ia', 'Reaproveitar respostas iguais por',
                              'A mesma primeira pergunta, com a base sem mudança, reaproveita a resposta já dada (sem custo). Zero desliga.',
                              'inteiro', 30, 0, 365, 'dias', 'Assistente da Plataforma'),
}

TIPOS = {'inteiro': 'Número inteiro', 'decimal': 'Número decimal', 'texto': 'Texto', 'sim_nao': 'Sim ou não'}
SOMA_100 = ('banca_peso_escrito', 'banca_peso_apresentacao', 'banca_peso_visual')
CHAVE_VALIDA = re.compile(r'^[a-z][a-z0-9_]{2,58}$')


def _modelos():
    from models import db, ParametroRegra, HistoricoParametro
    return db, ParametroRegra, HistoricoParametro


# ------------------------------------------------------------------------------ conversão
def converter(tipo, texto):
    """Texto digitado → valor do tipo certo. Levanta ValueError com a explicação."""
    texto = (str(texto) if texto is not None else '').strip()
    if tipo == 'inteiro':
        if not re.fullmatch(r'-?\d+', texto):
            raise ValueError('Informe um número inteiro.')
        return int(texto)
    if tipo == 'decimal':
        try:
            return round(float(texto.replace(',', '.')), 2)
        except ValueError:
            raise ValueError('Informe um número (ex.: 7 ou 6,5).')
    if tipo == 'sim_nao':
        if texto.lower() not in ('sim', 'nao', 'não', 'true', 'false', '1', '0'):
            raise ValueError('Escolha sim ou não.')
        return texto.lower() in ('sim', 'true', '1')
    if not texto:
        raise ValueError('Informe um valor.')
    return texto[:500]


def para_texto(valor):
    if isinstance(valor, bool):
        return 'sim' if valor else 'nao'
    return str(valor)


# ------------------------------------------------------------------------------ leitura
def _gravados():
    """Valores gravados, lidos uma vez por requisição (g) para não consultar o banco a cada regra."""
    try:
        from flask import g, has_app_context
        if not has_app_context():
            return {}
        if not hasattr(g, '_parametros_regra'):
            _, ParametroRegra, _ = _modelos()
            g._parametros_regra = {p.chave: p for p in ParametroRegra.query.all()}
        return g._parametros_regra
    except Exception:
        return {}


def _esquecer():
    try:
        from flask import g
        g.pop('_parametros_regra', None)
    except Exception:
        pass


def regra(chave, padrao=None):
    """Valor atual da regra (gravado pela gestão ou o padrão do catálogo)."""
    meta = CATALOGO.get(chave)
    gravado = _gravados().get(chave)
    if gravado is not None:
        tipo = meta[3] if meta else (gravado.tipo or 'texto')
        try:
            return converter(tipo, gravado.valor)
        except ValueError:
            pass
    return meta[4] if meta else padrao


def padrao_senha_forte():
    """Política de senha com o tamanho mínimo parametrizado."""
    return rf'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{{{int(regra("senha_min_caracteres"))},}}$'


def listar():
    """Tudo o que a tela mostra, agrupado: valor atual, padrão, se foi alterado e a última alteração."""
    gravados = _gravados()
    itens = []
    for chave, (grupo, nome, descricao, tipo, padrao, minimo, maximo, unidade, uso) in CATALOGO.items():
        p = gravados.get(chave)
        atual = regra(chave)
        itens.append({'chave': chave, 'grupo': grupo, 'nome': nome, 'descricao': descricao, 'tipo': tipo, 'padrao': padrao,
                      'minimo': minimo, 'maximo': maximo, 'unidade': unidade, 'uso': uso, 'valor': atual,
                      'alterado': atual != padrao, 'personalizado': False,
                      'atualizado_em': p.atualizado_em if p else None, 'atualizado_por': p.atualizado_por.nome if p and p.atualizado_por else None})
    for chave, p in sorted(gravados.items()):
        if p.personalizado:
            itens.append({'chave': chave, 'grupo': 'personalizadas', 'nome': p.nome or chave, 'descricao': p.descricao or '',
                          'tipo': p.tipo or 'texto', 'padrao': None, 'minimo': None, 'maximo': None, 'unidade': '',
                          'uso': 'Disponível para novas regras: regra(\'%s\')' % chave, 'valor': regra(chave), 'alterado': False,
                          'personalizado': True, 'atualizado_em': p.atualizado_em,
                          'atualizado_por': p.atualizado_por.nome if p.atualizado_por else None})
    return itens


# ------------------------------------------------------------------------------ gravação (com histórico)
def _historico(chave, acao, anterior, novo, motivo, usuario_id):
    db, _, HistoricoParametro = _modelos()
    db.session.add(HistoricoParametro(chave=chave, acao=acao, valor_anterior=None if anterior is None else para_texto(anterior),
                                      valor_novo=None if novo is None else para_texto(novo), motivo=(motivo or '').strip()[:500] or None,
                                      usuario_id=usuario_id, data=datetime.utcnow()))


def preparar_varios(valores):
    """Só valida, sem gravar (para a requisição de mudança): devolve ({chave: (anterior, novo) em texto} das regras que
    MUDAM, erros). Mesmas regras do salvar_varios: tipo, limites e pesos da banca somando 100%."""
    novos, erros = _validar(valores)
    if erros:
        return {}, erros
    return {c: (para_texto(regra(c)), para_texto(v)) for c, v in novos.items() if v != regra(c)}, {}


def _validar(valores):
    gravados = _gravados()
    novos, erros = {}, {}
    for chave, texto in valores.items():
        meta = CATALOGO.get(chave)
        p = gravados.get(chave)
        if not meta and not (p and p.personalizado):
            continue
        tipo = meta[3] if meta else (p.tipo or 'texto')
        try:
            valor = converter(tipo, texto)
        except ValueError as e:
            erros[chave] = str(e)
            continue
        if meta and meta[5] is not None and not (meta[5] <= valor <= meta[6]):
            erros[chave] = f'Use um valor entre {meta[5]} e {meta[6]}.'
            continue
        novos[chave] = valor
    pesos = {c: novos.get(c, regra(c)) for c in SOMA_100}
    if any(c in novos for c in SOMA_100) and sum(pesos.values()) != 100:
        erros['banca_peso_escrito'] = f'Os pesos da banca somam {sum(pesos.values())}%: precisam somar 100%.'
    return novos, erros


def salvar_varios(valores, usuario_id, motivo=''):
    """valores = {chave: texto}. Valida tudo antes de gravar (inclusive pesos que somam 100%).
    Devolve (alteradas, erros) — com qualquer erro nada é gravado."""
    db, ParametroRegra, _ = _modelos()
    gravados = _gravados()
    novos, erros = _validar(valores)
    if erros:
        return [], erros
    alteradas = []
    for chave, valor in novos.items():
        anterior = regra(chave)
        if valor == anterior:
            continue
        p = gravados.get(chave) or ParametroRegra(chave=chave)
        p.valor, p.atualizado_em, p.atualizado_por_id = para_texto(valor), datetime.utcnow(), usuario_id
        db.session.add(p)
        _historico(chave, 'Alterado', anterior, valor, motivo, usuario_id)
        alteradas.append(chave)
    db.session.commit()
    _esquecer()
    return alteradas, {}


def restaurar(chave, usuario_id, motivo=''):
    """Volta a regra do catálogo ao valor-padrão (apaga o valor gravado)."""
    db, ParametroRegra, _ = _modelos()
    meta = CATALOGO.get(chave)
    p = db.session.get(ParametroRegra, chave)
    if not meta or not p:
        return False
    if meta[0] == 'banca' and chave in SOMA_100:
        # Pesos voltam juntos ao padrão (40/40/20) para continuar somando 100%
        for c in SOMA_100:
            outro = db.session.get(ParametroRegra, c)
            if outro:
                _historico(c, 'Restaurado', regra(c), CATALOGO[c][4], motivo, usuario_id)
                db.session.delete(outro)
    else:
        _historico(chave, 'Restaurado', regra(chave), meta[4], motivo, usuario_id)
        db.session.delete(p)
    db.session.commit()
    _esquecer()
    return True


def criar(chave, nome, tipo, texto, descricao, usuario_id):
    """Regra nova da gestão. Devolve a mensagem de erro ou None."""
    db, ParametroRegra, _ = _modelos()
    chave = (chave or '').strip().lower()
    if not CHAVE_VALIDA.match(chave):
        return 'O código deve ter de 3 a 59 letras minúsculas, números ou _ e começar com letra (ex.: horas_minimas_estagio).'
    if chave in CATALOGO or db.session.get(ParametroRegra, chave):
        return 'Já existe uma regra com este código.'
    if tipo not in TIPOS:
        return 'Escolha o tipo da regra.'
    if not (nome or '').strip():
        return 'Dê um nome para a regra.'
    try:
        valor = converter(tipo, texto)
    except ValueError as e:
        return str(e)
    db.session.add(ParametroRegra(chave=chave, valor=para_texto(valor), personalizado=True, nome=nome.strip()[:150],
                                  descricao=(descricao or '').strip()[:1000] or None, tipo=tipo,
                                  atualizado_em=datetime.utcnow(), atualizado_por_id=usuario_id))
    _historico(chave, 'Criado', None, valor, descricao, usuario_id)
    db.session.commit()
    _esquecer()
    return None


def excluir(chave, usuario_id, motivo=''):
    """Só as regras criadas pela gestão podem ser excluídas (as do sistema voltam ao padrão)."""
    db, ParametroRegra, _ = _modelos()
    p = db.session.get(ParametroRegra, chave)
    if not p or not p.personalizado:
        return False
    _historico(chave, 'Excluído', regra(chave), None, motivo, usuario_id)
    db.session.delete(p)
    db.session.commit()
    _esquecer()
    return True


def historico(limite=100):
    _, _, HistoricoParametro = _modelos()
    return HistoricoParametro.query.order_by(HistoricoParametro.data.desc()).limit(limite).all()


def nome_da_regra(chave):
    if chave in CATALOGO:
        return CATALOGO[chave][1]
    db, ParametroRegra, _ = _modelos()
    p = db.session.get(ParametroRegra, chave) if chave else None
    return p.nome if p and p.nome else chave
