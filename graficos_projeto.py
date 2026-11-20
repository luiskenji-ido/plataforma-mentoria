# -*- coding: utf-8 -*-
"""
GRÁFICOS DOS PROJETOS (aba Gráficos de cada projeto)
====================================================
- Gantt: uma barra por tarefa (subtarefas logo abaixo da tarefa-mãe), do início ao fim, com o quanto já foi concluído,
  a linha de hoje e o destaque das atrasadas.
- Gráficos sob demanda para o acompanhamento dos mentores: o mentor escolhe o dado e o tipo de gráfico na tela.
Tudo é calculado aqui a partir das tarefas do projeto; a tela só desenha.
"""
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta

STATUS_ORDEM = ['Pendente', 'Em Andamento', 'Concluído']
# Mesmas cores do Gantt, para o gráfico e o cronograma falarem a mesma língua
COR_STATUS = {'Pendente': '#6c757d', 'Em Andamento': '#0d6efd', 'Concluído': '#198754'}
COR_PRAZO = {'No prazo': '#198754', 'Vence em até 7 dias': '#ffc107', 'Atrasada': '#dc3545', 'Concluída': '#20c997', 'Sem prazo': '#adb5bd'}
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

# Dados que o mentor pode transformar em gráfico: chave → (rótulo, tipo de gráfico sugerido)
DADOS = OrderedDict([
    ('status', ('Tarefas por status', 'doughnut')),
    ('responsavel', ('Tarefas por responsável', 'bar')),
    ('conclusao', ('% de conclusão de cada tarefa', 'bar')),
    ('horas', ('Horas registradas por tarefa', 'bar')),
    ('prazo', ('Situação dos prazos', 'pie')),
    ('entregas_mes', ('Tarefas com prazo final por mês', 'line')),
    ('horas_responsavel', ('Horas registradas por responsável', 'bar')),
])


def _dia(valor):
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


def _responsaveis(tarefa):
    nomes = [n.strip() for n in (tarefa.responsavel or '').replace(';', ',').split(',') if n.strip()]
    return nomes or ['Sem responsável']


def _situacao_prazo(tarefa, hoje):
    fim = _dia(tarefa.data_fim)
    if tarefa.status == 'Concluído':
        return 'Concluída'
    if fim is None:
        return 'Sem prazo'
    if fim < hoje:
        return 'Atrasada'
    if fim <= hoje + timedelta(days=7):
        return 'Vence em até 7 dias'
    return 'No prazo'


def ordenar_tarefas(tarefas):
    """Tarefas-mãe por data de início e, logo abaixo de cada uma, as suas subtarefas."""
    def chave(t):
        return (_dia(t.data_inicio) or date.max, t.id)
    maes = sorted([t for t in tarefas if not t.tarefa_pai_id], key=chave)
    filhas = {}
    for t in tarefas:
        if t.tarefa_pai_id:
            filhas.setdefault(t.tarefa_pai_id, []).append(t)
    ordem = []
    for m in maes:
        ordem.append((m, 0))
        ordem += [(f, 1) for f in sorted(filhas.get(m.id, []), key=chave)]
    ids = {t.id for t, _ in ordem}
    ordem += [(t, 1) for t in sorted(tarefas, key=chave) if t.id not in ids]  # subtarefa sem mãe visível
    return ordem


def gantt(projeto, hoje=None):
    hoje = hoje or date.today()
    linhas, sem_datas = [], []
    for t, nivel in ordenar_tarefas(list(projeto.tarefas)):
        inicio, fim = _dia(t.data_inicio), _dia(t.data_fim)
        if inicio and fim and fim < inicio:
            inicio, fim = fim, inicio
        if not (inicio or fim):
            sem_datas.append({'id': t.id, 'nome': t.descricao, 'nivel': nivel, 'status': t.status})
            continue
        inicio, fim = inicio or fim, fim or inicio
        linhas.append({'id': t.id, 'nome': t.descricao, 'nivel': nivel, 'inicio': inicio, 'fim': fim, 'status': t.status or 'Pendente',
                       'pct': max(0, min(100, int(t.percentual_conclusao or (100 if t.status == 'Concluído' else 0)))),
                       'responsavel': ', '.join(_responsaveis(t)), 'prazo': _situacao_prazo(t, hoje)})
    if not linhas:
        return {'linhas': [], 'sem_datas': sem_datas, 'marcas': [], 'hoje_pct': None}
    comeco = min(linha['inicio'] for linha in linhas)
    final = max(linha['fim'] for linha in linhas)
    total = (final - comeco).days + 1
    for linha in linhas:
        linha['esquerda'] = round((linha['inicio'] - comeco).days / total * 100, 3)
        linha['largura'] = max(round(((linha['fim'] - linha['inicio']).days + 1) / total * 100, 3), 0.8)
        linha['dias'] = (linha['fim'] - linha['inicio']).days + 1
    # Marcas da régua: semanas em projetos curtos, meses nos longos
    marcas, passo = [], (7 if total <= 120 else None)
    if passo:
        d = comeco
        while d <= final:
            marcas.append({'pct': round((d - comeco).days / total * 100, 3), 'texto': d.strftime('%d/%m')})
            d += timedelta(days=passo)
    else:
        d = date(comeco.year, comeco.month, 1)
        while d <= final:
            if d >= comeco:
                marcas.append({'pct': round((d - comeco).days / total * 100, 3), 'texto': f"{MESES[d.month - 1]}/{d.strftime('%y')}"})
            d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    hoje_pct = round((hoje - comeco).days / total * 100, 3) if comeco <= hoje <= final else None
    return {'linhas': linhas, 'sem_datas': sem_datas, 'marcas': marcas, 'hoje_pct': hoje_pct,
            'inicio': comeco, 'fim': final, 'dias': total}


def series(projeto, hoje=None, traduzir=None):
    """Séries prontas para os gráficos sob demanda: {dado: {'rotulos': [...], 'valores': [...], 'unidade': '...'}}."""
    hoje = hoje or date.today()
    tr = traduzir or (lambda texto: texto)
    tarefas = list(projeto.tarefas)
    saida = {}
    status = Counter(t.status or 'Pendente' for t in tarefas)
    ordem = [s for s in STATUS_ORDEM if s in status] + [s for s in status if s not in STATUS_ORDEM]
    saida['status'] = {'rotulos': [tr(s) for s in ordem], 'valores': [status[s] for s in ordem], 'unidade': 'tarefas',
                       'cores': [COR_STATUS.get(s, '#6f42c1') for s in ordem]}
    resp = Counter(n for t in tarefas for n in _responsaveis(t))
    saida['responsavel'] = {'rotulos': [tr(n) for n, _ in resp.most_common()], 'valores': [q for _, q in resp.most_common()], 'unidade': 'tarefas'}
    ordenadas = [t for t, _ in ordenar_tarefas(tarefas)]
    saida['conclusao'] = {'rotulos': [t.descricao[:40] for t in ordenadas],
                          'valores': [int(t.percentual_conclusao or (100 if t.status == 'Concluído' else 0)) for t in ordenadas], 'unidade': '%'}
    saida['horas'] = {'rotulos': [t.descricao[:40] for t in ordenadas],
                      'valores': [round((t.tempo_total_minutos or 0) / 60, 1) for t in ordenadas], 'unidade': 'horas'}
    prazos = Counter(_situacao_prazo(t, hoje) for t in tarefas)
    ordem_prazo = [p for p in ('No prazo', 'Vence em até 7 dias', 'Atrasada', 'Concluída', 'Sem prazo') if p in prazos]
    saida['prazo'] = {'rotulos': [tr(p) for p in ordem_prazo], 'valores': [prazos[p] for p in ordem_prazo], 'unidade': 'tarefas',
                      'cores': [COR_PRAZO[p] for p in ordem_prazo]}
    meses = Counter()
    for t in tarefas:
        fim = _dia(t.data_fim)
        if fim:
            meses[(fim.year, fim.month)] += 1
    chaves = sorted(meses)
    saida['entregas_mes'] = {'rotulos': [f"{MESES[m - 1]}/{str(a)[2:]}" for a, m in chaves], 'valores': [meses[k] for k in chaves], 'unidade': 'tarefas'}
    horas_resp = Counter()
    for t in tarefas:
        nomes = _responsaveis(t)
        for n in nomes:
            horas_resp[n] += (t.tempo_total_minutos or 0) / 60 / len(nomes)
    saida['horas_responsavel'] = {'rotulos': [tr(n) for n, _ in horas_resp.most_common()],
                                  'valores': [round(h, 1) for _, h in horas_resp.most_common()], 'unidade': 'horas'}
    return saida


def dados_do_projeto(projeto, hoje=None, traduzir=None):
    return {'gantt': gantt(projeto, hoje), 'series': series(projeto, hoje, traduzir)}
