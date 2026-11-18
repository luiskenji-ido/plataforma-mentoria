# -*- coding: utf-8 -*-
"""
AGENTE ORQUESTRADOR EXECUTOR
============================
Uso (a tela chama em segundo plano): python agentes_orquestrador/executor.py --ids <id> <id> --provedor gemini --usuario "Nome"

1. Lê os prompts de correção das quatro equipes (coletor.py) e monta o plano com as correções escolhidas.
2. Cria uma CÓPIA do código (git worktree num ramo novo) e uma cópia do banco: o site em uso nunca é alterado aqui.
3. Para cada correção, a IA (Gemini ou Claude, com a Skill) devolve as trocas exatas; cada troca é validada (arquivo
   permitido, trecho único, sintaxe Python/Jinja) e guardada com o plano de rollback (patch reverso).
4. Validação: sobe uma instância temporária com o código corrigido e o banco copiado, os Gerentes aprendem as mudanças
   e rodam as equipes (Funcionalidades, Segurança, Banco de Dados e Fim a Fim). Cada equipe aprova ou reprova
   comparando com a execução anterior.
5. Só com todas as equipes aprovando, o commit fica disponível para o administrador confirmar (commit + push) — ou
   ele clica em rollback e a cópia é descartada: a versão em uso continua a mesma de antes.
"""
import argparse
import difflib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA)
sys.path.insert(0, PASTA)
import coletor          # noqa: E402
import ia_correcao      # noqa: E402
import ambiente_orquestrador as ambiente  # noqa: E402  (nome próprio: o ambiente.py da raiz é outro módulo)

PASTA_AO_VIVO = os.path.join(RAIZ, 'Agent Reports', 'Agentes IA', '.ao_vivo_orquestrador')
PASTA_DADOS = os.path.join(RAIZ, 'instance', 'orquestrador')
ARQUIVO_ESTADO = os.path.join(PASTA_AO_VIVO, 'estado.json')
ARQUIVO_HISTORICO = os.path.join(PASTA_DADOS, 'historico.json')
ARQUIVO_IGNORADOS = os.path.join(PASTA_DADOS, 'ignorados.json')
# Cópias num caminho CURTO: no Windows, caminhos acima de 260 caracteres quebram as pastas de relatório dos agentes
import hashlib as _hashlib  # noqa: E402
PASTA_COPIAS = os.path.join(os.environ.get('ORQUESTRADOR_PASTA_COPIAS') or os.path.join(os.path.expanduser('~'), '.mentoria_orq'),
                            _hashlib.sha1(os.path.normcase(RAIZ).encode('utf-8')).hexdigest()[:8])  # uma pasta por projeto


def _apagar_pasta(caminho):
    """rmtree que também apaga arquivos somente-leitura (objetos do Git no Windows)."""
    import stat

    def liberar(funcao, alvo, _):
        os.chmod(alvo, stat.S_IWRITE)
        funcao(alvo)
    shutil.rmtree(caminho, onerror=liberar) if os.path.exists(caminho) else None
PROIBIDOS = re.compile(r'(^|/)(\.git|\.env|instance|client_secret[^/]*\.json|Agent Reports|\.venv[^/]*|uploads|Backup_repository)(/|$)|\.db$', re.I)
EQUIPES_VALIDACAO = [  # (chave, nome, script, argumentos, tempo máximo em minutos)
    ('funcionalidades', 'Funcionalidades', os.path.join('agentes_funcionalidades', 'gestor_funcionalidades.py'), ['--url', '{url}'], 30),
    ('seguranca', 'Segurança', os.path.join('agentes_seguranca', 'gestor_seguranca.py'), ['--url', '{url}'], 20),
    ('banco', 'Banco de Dados', os.path.join('agentes_banco', 'gestor_banco.py'), [], 20),
    ('e2e', 'Fim a Fim', os.path.join('agentes_omnitest', 'agente_gestor.py'), ['--url', '{url}', '--lento', '0'], 60),
]
SEVERIDADES_BLOQUEIAM = ('Crítica', 'Alta', 'Média')


# ------------------------------------------------------------------------------ arquivos de estado
def _ler_json(caminho, padrao):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def _gravar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    temporario = caminho + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=1, default=str)
    os.replace(temporario, caminho)


def ler_estado():
    return _ler_json(ARQUIVO_ESTADO, None)


def ignorados():
    return _ler_json(ARQUIVO_IGNORADOS, {})


def historico():
    return _ler_json(ARQUIVO_HISTORICO, [])


class Execucao:
    def __init__(self, dados):
        self.dados = dados

    def gravar(self):
        self.dados['batimento'] = time.time()
        _gravar_json(ARQUIVO_ESTADO, self.dados)

    def log(self, texto):
        linha = f"{datetime.now():%H:%M:%S}  {texto}"
        print(linha, flush=True)
        self.dados.setdefault('log', []).append(linha)
        self.dados['log'] = self.dados['log'][-400:]
        self.gravar()

    def etapa(self, chave, status, detalhe=''):
        for e in self.dados['etapas']:
            if e['chave'] == chave:
                e.update(status=status, detalhe=detalhe)
        self.gravar()


# ------------------------------------------------------------------------------ git
def git(*args, cwd=RAIZ, tempo=120):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, timeout=tempo, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


def criar_copia(execucao):
    """Worktree num ramo novo a partir do commit atual + .env, credenciais e uma cópia consistente do banco."""
    d = execucao.dados
    _, base, _ = git('rev-parse', 'HEAD')
    d['base'] = base
    d['ramo'] = f"orquestrador/{d['id']}"
    d['copia'] = os.path.join(PASTA_COPIAS, d['id'])
    os.makedirs(os.path.dirname(d['copia']), exist_ok=True)
    codigo, _, erro = git('worktree', 'add', '-b', d['ramo'], d['copia'], 'HEAD')
    if codigo != 0:
        raise RuntimeError(f'Não foi possível criar a cópia do código: {erro}')
    for nome in ('.env', 'client_secret.json'):
        if os.path.exists(os.path.join(RAIZ, nome)):
            shutil.copy2(os.path.join(RAIZ, nome), os.path.join(d['copia'], nome))
    copiar_banco(d['copia'])
    _, pendentes, _ = git('status', '--porcelain')
    if pendentes:
        execucao.log('⚠ Há alterações não commitadas no código em uso; a cópia parte do último commit e não as inclui.')
    execucao.log(f"Cópia do código criada no ramo {d['ramo']} (base {base[:8]}) com cópia do banco.")


def descartar_copia(dados):
    """Rollback antes do commit: remove a cópia, a cópia da contraprova e o ramo. O código em uso nunca foi tocado."""
    for pasta in (dados.get('copia'), f"{dados['copia']}_base" if dados.get('copia') else None):
        if pasta and os.path.exists(pasta):
            git('worktree', 'remove', '--force', pasta)
            _apagar_pasta(pasta)
    git('worktree', 'prune')
    if dados.get('ramo'):
        git('branch', '-D', dados['ramo'])


def limpar_sobras():
    """Antes de uma execução nova: apaga cópias e ramos deixados por execuções interrompidas (só deste projeto)."""
    if os.path.isdir(PASTA_COPIAS):
        for nome in os.listdir(PASTA_COPIAS):
            pasta = os.path.join(PASTA_COPIAS, nome)
            git('worktree', 'remove', '--force', pasta)
            _apagar_pasta(pasta)
    git('worktree', 'prune')
    _, ramos, _ = git('branch', '--list', 'orquestrador/*', '--format=%(refname:short)')
    for ramo in ramos.splitlines():
        git('branch', '-D', ramo.strip())


# ------------------------------------------------------------------------------ aplicação das trocas
def _sem_numeros_de_linha(trecho):
    """A IA às vezes copia os números de linha mostrados no contexto ('  123| texto'); retira se TODAS as linhas tiverem."""
    linhas = trecho.split('\n')
    if linhas and all(re.match(r'^\s*\d+\| ', l) for l in linhas if l.strip()):
        return '\n'.join(re.sub(r'^\s*\d+\| ', '', l) for l in linhas)
    return trecho


def _caminho_permitido(raiz, arquivo):
    arquivo = (arquivo or '').replace('\\', '/').strip().lstrip('/')
    if not arquivo or '..' in arquivo.split('/') or os.path.isabs(arquivo) or PROIBIDOS.search(arquivo):
        return None
    completo = os.path.normpath(os.path.join(raiz, arquivo))
    return completo if completo.startswith(os.path.normpath(raiz)) else None


def _sintaxe_ok(caminho, texto):
    if caminho.endswith('.py'):
        compile(texto, caminho, 'exec')
    elif caminho.endswith('.html'):
        from jinja2 import Environment
        Environment(extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols']).parse(texto)
    elif caminho.endswith('.json'):
        json.loads(texto)


def aplicar_trocas(raiz, alteracoes):
    """Aplica todas as trocas de UMA correção ou nenhuma. Devolve (originais, problema)."""
    originais, novos = {}, {}
    for alt in alteracoes:
        caminho = _caminho_permitido(raiz, alt.get('arquivo'))
        if not caminho:
            return {}, f"Arquivo não permitido para correção automática: {alt.get('arquivo')}"
        rel = os.path.relpath(caminho, raiz).replace('\\', '/')
        if rel not in novos:
            if os.path.exists(caminho):
                with open(caminho, encoding='utf-8') as f:
                    originais[rel] = f.read()
            else:
                originais[rel] = None
            novos[rel] = originais[rel] if originais[rel] is not None else ''
        atual, novo = _sem_numeros_de_linha(alt.get('trecho_atual') or ''), _sem_numeros_de_linha(alt.get('trecho_novo') or '')
        if not atual:
            if originais[rel] is not None:
                return {}, f"Trecho atual vazio para um arquivo que já existe: {rel}"
            novos[rel] = novo
            continue
        vezes = novos[rel].count(atual)
        if vezes != 1:
            return {}, f"O trecho a trocar aparece {vezes} vez(es) em {rel} (precisa aparecer exatamente 1)."
        novos[rel] = novos[rel].replace(atual, novo, 1)
    for rel, texto in novos.items():
        try:
            _sintaxe_ok(rel, texto)
        except Exception as e:
            return {}, f"A correção deixaria {rel} com erro de sintaxe: {e}"
    for rel, texto in novos.items():
        completo = os.path.join(raiz, rel)
        os.makedirs(os.path.dirname(completo), exist_ok=True)
        with open(completo, 'w', encoding='utf-8', newline='') as f:
            f.write(texto)
    return originais, None


def restaurar(raiz, originais):
    for rel, texto in originais.items():
        completo = os.path.join(raiz, rel)
        if texto is None:
            if os.path.exists(completo):
                os.remove(completo)
        else:
            with open(completo, 'w', encoding='utf-8', newline='') as f:
                f.write(texto)


def patch_de_rollback(raiz, originais):
    """Patch reverso (do corrigido de volta ao original) — o plano de rollback de cada correção, em texto."""
    partes = []
    for rel, antes in originais.items():
        with open(os.path.join(raiz, rel), encoding='utf-8') as f:
            depois = f.read()
        partes += difflib.unified_diff(depois.splitlines(True), (antes or '').splitlines(True), f'a/{rel}', f'b/{rel}')
    return ''.join(partes)


def corrigir(execucao, item):
    d = execucao.dados
    item['status'] = 'corrigindo'
    execucao.log(f"🔧 {item['titulo']} ({item['equipe_nome']} · {item['agente']})")
    correcao = item['_correcao']
    arquivos_texto = ia_correcao.conteudo_dos_arquivos(d['copia'], correcao['arquivos'])
    prompt = coletor.trecho_do_prompt(correcao)
    tentativa = None
    for rodada in (1, 2):
        try:
            resposta = ia_correcao.pedir_correcao(d['provedor'], correcao, prompt, arquivos_texto, tentativa)
        except ia_correcao.IAIndisponivel as e:
            item.update(status='nao_aplicada', motivo=str(e))
            execucao.log(f"   ✗ IA indisponível: {e}")
            return
        except Exception as e:
            item.update(status='nao_aplicada', motivo=f'Falha ao consultar a IA: {e.__class__.__name__}: {e}'[:400])
            execucao.log(f"   ✗ {item['motivo']}")
            return
        item.update(resumo=resposta.get('resumo', ''), rollback=resposta.get('rollback', ''), como_testar=resposta.get('como_testar', ''),
                    riscos=resposta.get('riscos', ''), motivo=resposta.get('motivo', ''))
        if not resposta.get('pode_corrigir') or not resposta.get('alteracoes'):
            item['status'] = 'nao_e_codigo'
            execucao.log(f"   ℹ Não é correção de código: {item['motivo'][:200]}")
            return
        originais, problema = aplicar_trocas(d['copia'], resposta['alteracoes'])
        if not problema:
            break
        tentativa = problema
        execucao.log(f"   ↻ Tentativa {rodada} recusada: {problema}")
    else:
        item.update(status='nao_aplicada', motivo=problema)
        return
    item['arquivos_alterados'] = sorted(originais)
    item['alteracoes'] = [{'arquivo': a['arquivo'], 'explicacao': a.get('explicacao', '')} for a in resposta['alteracoes']]
    rollback = patch_de_rollback(d['copia'], originais)
    caminho_rollback = os.path.join(PASTA_DADOS, 'rollback', d['id'], f"{item['id']}.patch")
    os.makedirs(os.path.dirname(caminho_rollback), exist_ok=True)
    with open(caminho_rollback, 'w', encoding='utf-8') as f:
        f.write(rollback)
    item['patch_rollback'] = caminho_rollback
    item['status'] = 'aplicada'
    execucao.log(f"   ✓ Aplicada em {', '.join(item['arquivos_alterados'])} (plano de rollback guardado).")


# ------------------------------------------------------------------------------ validação pelas equipes
def porta_livre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def ambiente_de_teste():
    """A instância de validação usa a cópia do banco: tira as marcas de produção para os agentes poderem testar."""
    retirar = {'PYTHONANYWHERE_DOMAIN', 'PYTHONANYWHERE_SITE', 'MENTORIA_PRODUCAO', 'WEBSITE_SITE_NAME', 'WEBSITE_INSTANCE_ID',
               'K_SERVICE', 'GAE_SERVICE',
               # A cópia do banco tem pessoas reais: sem SMTP, nenhum e-mail sai da validação
               'MAIL_SERVER', 'MAIL_REMETENTE', 'MAIL_USERNAME', 'MAIL_PASSWORD'}
    env = {k: v for k, v in os.environ.items() if k not in retirar}
    # Vazias de propósito: o .env da cópia não sobrescreve variáveis já definidas, então o SMTP fica desligado de verdade
    env.update(MAIL_SERVER='', MAIL_REMETENTE='', MAIL_USERNAME='', MAIL_PASSWORD='')
    env.update(PYTHONIOENCODING='utf-8', MENTORIA_VALIDACAO='1')  # sem backups automáticos para as pastas reais
    # A validação SEMPRE usa a cópia SQLite (instance/mentoria.db da cópia), nunca o banco real do DATABASE_URL (MySQL)
    env['DATABASE_URL'] = 'sqlite:///mentoria.db'
    return env


def copiar_banco(destino_raiz):
    """Cópia do banco para a validação, sempre em SQLite. Com o banco principal em MySQL (DATABASE_URL), as tabelas
    são copiadas pelo copiar_banco.py da raiz; com SQLite, pela API de backup do SQLite."""
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)
    import banco_config
    principal = banco_config.endereco_do_banco()
    if not banco_config.eh_sqlite(principal):
        import copiar_banco as copia
        pasta = os.path.join(destino_raiz, 'instance')
        os.makedirs(pasta, exist_ok=True)
        arquivo = os.path.join(pasta, 'mentoria.db')
        if os.path.exists(arquivo):
            os.remove(arquivo)
        copia.copiar(principal, 'sqlite:///' + arquivo.replace('\\', '/'), avisar=lambda *_: None)
        return
    banco = os.path.join(RAIZ, 'instance', 'mentoria.db')
    if os.path.exists(banco):
        os.makedirs(os.path.join(destino_raiz, 'instance'), exist_ok=True)
        origem, destino = sqlite3.connect(banco), sqlite3.connect(os.path.join(destino_raiz, 'instance', 'mentoria.db'))
        with destino:
            origem.backup(destino)  # cópia consistente mesmo com o site gravando
        origem.close(), destino.close()


def restaurar_estado(raiz):
    """Ponto de partida idêntico para cada equipe, com e sem a correção: o que uma equipe deixa em disco (backups em
    instance/backups, anexos em uploads/) e no banco some antes da próxima — senão a comparação com a contraprova engana."""
    for pasta in ('instance', 'uploads'):
        alvo = os.path.join(raiz, pasta)
        for tentativa in range(15):  # no Windows o arquivo do banco demora alguns segundos para ser liberado
            try:
                _apagar_pasta(alvo)
                break
            except PermissionError:
                time.sleep(1)
        else:
            # Ainda preso: apaga tudo o que der e o banco é sobrescrito pelo próprio SQLite logo abaixo
            for atual, _, arquivos in os.walk(alvo, topdown=False):
                for nome in arquivos:
                    if nome != 'mentoria.db':
                        try:
                            os.remove(os.path.join(atual, nome))
                        except OSError:
                            pass
    copiar_banco(raiz)


def subir(raiz, rotulo):
    """Instância temporária (127.0.0.1, porta livre) rodando o código de 'raiz' com a cópia do banco dela."""
    porta = porta_livre()
    url = f"http://127.0.0.1:{porta}"
    log = open(os.path.join(PASTA_AO_VIVO, f'instancia_{rotulo}.log'), 'w', encoding='utf-8')
    processo = subprocess.Popen([sys.executable, os.path.join(PASTA, 'servidor_validacao.py'), raiz, str(porta)],
                                cwd=raiz, stdout=log, stderr=subprocess.STDOUT, env=ambiente_de_teste())
    for _ in range(90):
        try:
            urllib.request.urlopen(url + '/', timeout=3)
            return processo, url
        except Exception:
            if processo.poll() is not None:
                break
            time.sleep(2)
    processo.kill()
    raise RuntimeError(f'A instância de validação ({rotulo}) não subiu (ver instancia_{rotulo}.log): '
                       + ('a correção quebrou o início do site.' if rotulo == 'corrigida' else 'o código em uso não iniciou na cópia.'))


def aprender(execucao):
    """Os Gerentes comparam a plataforma corrigida com o que sabiam e ensinam os agentes antes dos testes."""
    d = execucao.dados
    r = subprocess.run([sys.executable, os.path.join(PASTA, 'aprender_validacao.py'), d['copia']], cwd=d['copia'],
                       capture_output=True, text=True, timeout=600, env=ambiente_de_teste(), encoding='utf-8', errors='replace')
    try:
        d['aprendizado'] = json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        d['aprendizado'] = {'erro': (r.stderr or r.stdout or '')[-600:]}
    total = sum(len(v) for v in d['aprendizado'].values() if isinstance(v, list))
    execucao.log(f"🧠 Gerentes aprenderam {total} mudança(s) da correção antes dos testes.")


RELATORIOS_EQUIPE = {  # pasta, padrão e agentes de cada equipe (para conferir que TODOS rodaram nesta validação)
    'seguranca': ('Seguranca', 'Seguranca_{}_2*.json', ['configuracao', 'dados', 'codigo', 'dependencias', 'pentest']),
    'banco': ('BancoDados', 'Banco_{}_2*.json', ['consultas', 'esquema', 'backup', 'dba', 'portabilidade']),
    'funcionalidades': (os.path.join('Funcionalidades', '**'), 'Funcional_{}_2*.json',
                        ['administrador', 'mentor_administrador', 'gestor_parceiro', 'professor', 'mentor', 'aluno', 'avaliador', 'encerramento']),
    'e2e': (os.path.join('OmniTest', '**'), 'Relatorio_OmniTest_{}_2*.json',
            ['administrador', 'aluno', 'professor', 'mentor', 'mentor_administrador', 'gestor_b2b', 'avaliador', 'perfis_personalizados']),
}


def _ultimo(raiz, padrao, desde=None):
    """Caminho e conteúdo do relatório mais recente (opcionalmente só os gerados depois de 'desde')."""
    import glob
    arquivos = [a for a in glob.glob(os.path.join(raiz, 'Agent Reports', padrao), recursive=True) if not desde or os.path.getmtime(a) >= desde]
    if not arquivos:
        return None, {}
    arquivo = max(arquivos, key=os.path.getmtime)
    return arquivo, _ler_json(arquivo, {})


def rodar_equipe(raiz, url, chave):
    """Roda a equipe no código de 'raiz' contra a instância 'url'. Devolve (código de saída ou None se estourou o tempo, início)."""
    _, nome, script, argumentos, minutos = next(e for e in EQUIPES_VALIDACAO if e[0] == chave)
    cmd = [sys.executable, os.path.join(raiz, script)] + [a.format(url=url) for a in argumentos]
    rotulo = 'base' if raiz.endswith('_base') else 'corrigida'
    saida = open(os.path.join(PASTA_AO_VIVO, f'equipe_{chave}_{rotulo}.log'), 'w', encoding='utf-8')
    desde = time.time() - 1
    try:
        r = subprocess.run(cmd, cwd=os.path.dirname(os.path.join(raiz, script)), stdout=saida, stderr=subprocess.STDOUT,
                           env={**ambiente_de_teste(), 'OMNITEST_URL': url}, timeout=minutos * 60)
        return r.returncode, desde
    except subprocess.TimeoutExpired:
        return None, desde


def resultado_da_equipe(raiz, chave, codigo, desde):
    """{'rodou', 'motivo', 'problemas' (conjunto), 'riscos', 'aprovados'} a partir dos relatórios gerados nesta rodada."""
    pasta, padrao, agentes = RELATORIOS_EQUIPE[chave]
    relatorios = {}
    for agente in agentes:
        arquivo, dados = _ultimo(raiz, os.path.join(pasta, padrao.format(agente)), desde)
        if arquivo:
            relatorios[agente] = dados
    faltando = [a for a in agentes if a not in relatorios]
    if codigo is None or codigo != 0 or faltando:
        motivo = 'não terminou no tempo previsto' if codigo is None else (f'saiu com código {codigo}' if codigo else '')
        if faltando:
            motivo += ('; ' if motivo else '') + f"sem relatório desta validação para: {', '.join(faltando)}"
        return {'rodou': False, 'motivo': motivo, 'problemas': set(), 'riscos': {}, 'aprovados': 0}
    problemas, riscos, aprovados = set(), {}, 0
    for agente, r in relatorios.items():
        if chave in ('seguranca', 'banco'):
            riscos[agente] = r.get('nota_risco') or 0
            problemas |= {f"{agente}: {re.sub(r'[0-9]+', '#', a.get('titulo', ''))} [{a.get('severidade')}]"
                          for a in r.get('achados', []) if a.get('severidade') in SEVERIDADES_BLOQUEIAM}
            aprovados += r.get('verificacoes', 0) if isinstance(r.get('verificacoes'), int) else 0
        elif chave == 'funcionalidades':
            problemas |= {f"{agente}: {t.get('titulo')}" for t in r.get('testes', []) if t.get('resultado') == 'Falha'}
            aprovados += sum(1 for t in r.get('testes', []) if t.get('resultado') == 'Aprovado')
        else:
            problemas |= {f"{r.get('perfil') or agente}: {x.get('acao')}" for x in r.get('resultados', []) if 'Falha' in x.get('status', '')}
            aprovados += sum(1 for x in r.get('resultados', []) if 'Aprovado' in x.get('status', ''))
    return {'rodou': True, 'motivo': '', 'problemas': problemas, 'riscos': riscos, 'aprovados': aprovados}


def validar(execucao):
    """Cada equipe testa a cópia corrigida. Se encontrar problemas, faz a CONTRAPROVA: a mesma equipe roda no código SEM a
    correção, no mesmo tipo de cópia. Só conta como regressão o que aparece com a correção e não aparece sem ela."""
    d = execucao.dados
    capacidade = d['ambiente']
    instancia = {}
    contraprova = {}

    def preparar_corrigida():
        # Cada equipe parte de uma cópia NOVA do banco: o que uma equipe grava (ex.: o backup que o fluxo funcional faz)
        # não pode aparecer para a equipe seguinte — senão a contraprova, que roda só aquela equipe, não é comparável.
        if instancia.get('processo'):
            instancia['processo'].kill()
            instancia['processo'].wait(timeout=30)
            restaurar_estado(d['copia'])
        instancia['processo'], d['url_validacao'] = subir(d['copia'], 'corrigida')
        aprender(execucao)  # os Gerentes aprendem as mudanças de novo na cópia limpa do banco

    def preparar_contraprova():
        if not contraprova.get('raiz'):
            contraprova['raiz'] = criar_copia_base(execucao)
        elif contraprova.get('processo'):
            contraprova['processo'].kill()
            contraprova['processo'].wait(timeout=30)
            restaurar_estado(contraprova['raiz'])
        contraprova['processo'], contraprova['url'] = subir(contraprova['raiz'], 'base')

    try:
        preparar_corrigida()
        execucao.log(f"Instância de validação no ar em {d['url_validacao']} (código corrigido + cópia do banco).")
        primeira = True
        for chave, nome, *_ in EQUIPES_VALIDACAO:
            equipe = d['equipes'][chave]
            if equipe['status'] == 'fora':
                continue  # o administrador não escolheu esta equipe para validar
            if chave == 'e2e' and not capacidade['itens']['fim_a_fim']['ok']:
                equipe.update(status='indisponivel', resumo=capacidade['itens']['fim_a_fim']['texto'])
                execucao.log(f"⚠ {nome}: {equipe['resumo']}")
                continue
            equipe['status'] = 'executando'
            if not primeira:
                preparar_corrigida()
            primeira = False
            execucao.log(f"▶ Equipe {nome} testando a plataforma corrigida…")
            codigo, desde = rodar_equipe(d['copia'], d['url_validacao'], chave)
            com = resultado_da_equipe(d['copia'], chave, codigo, desde)
            if not com['rodou']:
                equipe.update(status='reprovado', resumo=f"A equipe não rodou por completo: {com['motivo']}.")
            elif not com['problemas']:
                equipe.update(status='aprovado', resumo=f"Todos os agentes rodaram ({com['aprovados']} verificação(ões)); nenhum problema.")
            else:
                execucao.log(f"   ↔ Problemas encontrados: contraprova da equipe {nome} no código sem a correção (cópia nova do banco)…")
                preparar_contraprova()
                codigo_b, desde_b = rodar_equipe(contraprova['raiz'], contraprova['url'], chave)
                sem = resultado_da_equipe(contraprova['raiz'], chave, codigo_b, desde_b)
                if not sem['rodou']:
                    equipe.update(status='reprovado', resumo=f"Problemas com a correção e a contraprova não rodou ({sem['motivo']}): "
                                                             + '; '.join(sorted(com['problemas'])[:5]))
                else:
                    novos = sorted(com['problemas'] - sem['problemas'])
                    piorou = [a for a, v in com['riscos'].items() if v > sem['riscos'].get(a, 0)]
                    resolvidos = sorted(sem['problemas'] - com['problemas'])
                    if novos or piorou:
                        equipe.update(status='reprovado', resumo='A correção causou: ' + '; '.join(novos[:6])
                                      + (f" Risco maior em: {', '.join(piorou)}." if piorou else ''))
                    else:
                        equipe.update(status='aprovado', resumo=f"{len(com['problemas'])} problema(s) já existiam sem a correção (não vêm dela)"
                                                                + (f"; {len(resolvidos)} resolvido(s) pela correção" if resolvidos else '') + '.')
            equipe['problemas'] = sorted(com['problemas'])[:30]
            execucao.log(f"   {'✓' if equipe['status'] == 'aprovado' else '✗'} {nome}: {equipe['resumo']}")
            execucao.gravar()
    finally:
        if instancia.get('processo'):
            instancia['processo'].kill()
        if contraprova.get('processo'):
            contraprova['processo'].kill()
        if contraprova.get('raiz'):
            git('worktree', 'remove', '--force', contraprova['raiz'])
            _apagar_pasta(contraprova['raiz'])
    # A correção foi confirmada pelos próprios agentes? (o achado sumiu do relatório da cópia)
    ainda = {c['id'] for c in coletor.coletar(os.path.join(d['copia'], 'Agent Reports'))}
    for item in d['correcoes']:
        if item['status'] == 'aplicada':
            item['confirmada'] = item['id'] not in ainda


def criar_copia_base(execucao):
    """Cópia do código EM USO (commit base, sem as correções) com outra cópia do banco — para a contraprova."""
    d = execucao.dados
    raiz = os.path.join(PASTA_COPIAS, f"{d['id']}_base")
    codigo, _, erro = git('worktree', 'add', '--detach', raiz, d['base'])
    if codigo != 0:
        raise RuntimeError(f'Não foi possível montar a contraprova: {erro}')
    for nome in ('.env', 'client_secret.json'):
        if os.path.exists(os.path.join(RAIZ, nome)):
            shutil.copy2(os.path.join(RAIZ, nome), os.path.join(raiz, nome))
    copiar_banco(raiz)
    return raiz


# ------------------------------------------------------------------------------ fluxo principal
def diff_da_copia(copia):
    git('add', '--intent-to-add', '--all', '--', '.', cwd=copia)
    _, diff, _ = git('diff', '--', '.', cwd=copia, tempo=60)
    _, estatistica, _ = git('diff', '--stat', '--', '.', cwd=copia, tempo=60)
    return diff, estatistica


def executar(ids, provedor, usuario, equipes):
    capacidade = ambiente.capacidades()
    todas = {c['id']: c for c in coletor.coletar()}
    escolhidas = [todas[i] for i in ids if i in todas]
    agora = datetime.now()
    dados = {
        'id': agora.strftime('%Y%m%d_%H%M%S'), 'status': 'executando', 'pid': os.getpid(), 'inicio': agora.isoformat(timespec='seconds'),
        'fim': None, 'provedor': provedor, 'usuario': usuario, 'ambiente': capacidade, 'log': [],
        'etapas': [{'chave': c, 'nome': n, 'status': 'aguardando', 'detalhe': ''} for c, n in
                   [('plano', 'Plano de correção'), ('copia', 'Cópia do código e do banco'), ('correcoes', 'Correções pela IA'),
                    ('aprendizado', 'Gerentes aprendem as mudanças'), ('validacao', 'Testes das equipes'), ('aprovacao', 'Aprovação')]],
        'correcoes': [{k: c[k] for k in ('id', 'titulo', 'equipe', 'equipe_nome', 'agente', 'severidade', 'onde', 'detalhe', 'recomendacao')}
                      | {'status': 'pendente', 'arquivos': [a for a, _ in c['arquivos']]} for c in escolhidas],
        'equipes': {c: {'nome': n, 'status': 'aguardando' if c in equipes else 'fora', 'resumo': ''} for c, n, *_ in EQUIPES_VALIDACAO},
    }
    execucao = Execucao(dados)
    for item, c in zip(dados['correcoes'], escolhidas):
        item['_correcao'] = c
    execucao.etapa('plano', 'concluido', f"{len(escolhidas)} correção(ões) escolhida(s) · IA: {provedor} · ambiente: {capacidade['nome']}")
    execucao.log(f"Plano: {len(escolhidas)} correção(ões) com {provedor}, por {usuario}, no ambiente {capacidade['nome']}.")
    try:
        if not capacidade['pode_corrigir']:
            raise RuntimeError('Este ambiente não permite corrigir o código: ' + '; '.join(
                i['texto'] for i in capacidade['itens'].values() if not i['ok']))
        execucao.etapa('copia', 'executando')
        limpar_sobras()  # nenhuma outra execução pode estar ativa (a tela bloqueia), então sobras são de execuções interrompidas
        criar_copia(execucao)
        execucao.etapa('copia', 'concluido', dados['ramo'])
        execucao.etapa('correcoes', 'executando')
        for item in dados['correcoes']:
            corrigir(execucao, item)
            execucao.gravar()
        aplicadas = [i for i in dados['correcoes'] if i['status'] == 'aplicada']
        execucao.etapa('correcoes', 'concluido', f"{len(aplicadas)} de {len(dados['correcoes'])} aplicada(s)")
        if not aplicadas:
            descartar_copia(dados)
            dados['status'] = 'sem_alteracoes'
            execucao.log('Nenhuma correção de código foi aplicada; a cópia foi descartada.')
            return
        dados['diff'], dados['diff_resumo'] = diff_da_copia(dados['copia'])
        for chave in list(dados['equipes']):
            if chave not in equipes:
                dados['equipes'][chave].update(status='fora', resumo='Não selecionada para esta validação.')
        execucao.etapa('aprendizado', 'executando')
        execucao.etapa('validacao', 'executando')
        validar(execucao)
        execucao.etapa('aprendizado', 'concluido', f"{sum(len(v) for v in dados.get('aprendizado', {}).values() if isinstance(v, list))} aprendizado(s)")
        resultado = {c: e['status'] for c, e in dados['equipes'].items() if e['status'] != 'fora'}
        aprovou = resultado and all(s == 'aprovado' for s in resultado.values())
        execucao.etapa('validacao', 'concluido' if aprovou else 'falhou', ', '.join(f"{dados['equipes'][c]['nome']}: {s}" for c, s in resultado.items()))
        if aprovou:
            dados['status'] = 'aguardando_confirmacao'
            execucao.etapa('aprovacao', 'aguardando', 'Todas as equipes aprovaram: falta o administrador confirmar o commit.')
            execucao.log('✅ Todas as equipes aprovaram. Commit liberado para o administrador confirmar (ou fazer rollback).')
        else:
            dados['status'] = 'reprovado'
            execucao.etapa('aprovacao', 'falhou', 'Alguma equipe reprovou: só o rollback está disponível.')
            execucao.log('⛔ Validação reprovada: o commit não será oferecido. Faça o rollback e veja os relatórios das equipes.')
    except Exception as e:
        import traceback
        dados['status'] = 'erro'
        dados['erro'] = f"{e.__class__.__name__}: {e}"
        execucao.log(f"⛔ {dados['erro']}\n{traceback.format_exc()[-800:]}")
    finally:
        for item in dados['correcoes']:
            item.pop('_correcao', None)
        dados['fim'] = datetime.now().isoformat(timespec='seconds')
        execucao.gravar()


# ------------------------------------------------------------------------------ decisão do administrador (chamado pela tela)
def confirmar(usuario):
    """Commit na cópia, avança o ramo em uso para ele (fast-forward), push e recarga do site. Devolve (ok, mensagem)."""
    dados = ler_estado()
    if not dados or dados.get('status') != 'aguardando_confirmacao':
        return False, 'Não há correção aprovada esperando confirmação.'
    arquivos = sorted({a for i in dados['correcoes'] if i['status'] == 'aplicada' for a in i.get('arquivos_alterados', [])})
    _, atual, _ = git('rev-parse', 'HEAD')
    if atual != dados['base']:
        return False, 'O código em uso mudou depois da cópia (houve outro commit). Faça o rollback e rode as correções de novo.'
    _, pendentes, _ = git('status', '--porcelain', '--', *arquivos)
    if pendentes:
        return False, 'Há alterações não commitadas nos mesmos arquivos do código em uso: commit ou descarte antes de confirmar.'
    git('reset', cwd=dados['copia'])
    git('add', '--', *arquivos, cwd=dados['copia'])
    linhas = [f"- [{i['equipe_nome']}] {i['titulo']}" for i in dados['correcoes'] if i['status'] == 'aplicada']
    mensagem = (f"Orquestrador: {len(linhas)} correção(ões) aprovada(s) pelas equipes de agentes\n\n" + '\n'.join(linhas) +
                f"\n\nIA: {dados['provedor']} · Aprovado pelas equipes: " +
                ', '.join(e['nome'] for e in dados['equipes'].values() if e['status'] == 'aprovado') +
                f"\nConfirmado por: {usuario} em {datetime.now():%d/%m/%Y %H:%M}")
    codigo, _, erro = git('commit', '-m', mensagem, cwd=dados['copia'])
    if codigo != 0:
        return False, f'Commit não realizado: {erro[:300]}'
    _, sha, _ = git('rev-parse', 'HEAD', cwd=dados['copia'])
    codigo, _, erro = git('merge', '--ff-only', dados['ramo'])
    if codigo != 0:
        return False, f'Não foi possível levar o commit para o código em uso: {erro[:300]}'
    _, ramo_atual, _ = git('rev-parse', '--abbrev-ref', 'HEAD')
    codigo, _, erro = git('push', 'origin', ramo_atual, tempo=180)
    _, remoto, _ = git('remote', 'get-url', 'origin')
    push = f'Push feito para {remoto} ({ramo_atual}).' if codigo == 0 else f'Commit feito, mas o push falhou: {erro[:200]}'
    descartar_copia(dados)
    recarregou, recarga = ambiente.recarregar_aplicacao()
    dados.update(status='confirmado', commit=sha, confirmado_por=usuario, confirmado_em=datetime.now().isoformat(timespec='seconds'),
                 resultado_push=push, recarga=recarga, diff=None)
    _gravar_json(ARQUIVO_ESTADO, dados)
    hist = historico()
    hist.insert(0, {'id': dados['id'], 'commit': sha, 'ramo': ramo_atual, 'data': dados['confirmado_em'], 'usuario': usuario,
                    'correcoes': linhas, 'push': codigo == 0, 'desfeito': False})
    _gravar_json(ARQUIVO_HISTORICO, hist[:100])
    return True, f'Commit {sha[:8]} criado. {push} {recarga}'


def rollback(usuario):
    """Antes do commit: descarta a cópia — a versão em uso continua exatamente a anterior à mudança."""
    dados = ler_estado()
    if not dados or dados.get('status') not in ('aguardando_confirmacao', 'reprovado', 'erro', 'sem_alteracoes', 'parado'):
        return False, 'Não há correção pendente para desfazer.'
    descartar_copia(dados)
    dados.update(status='revertido', revertido_por=usuario, revertido_em=datetime.now().isoformat(timespec='seconds'), diff=None)
    _gravar_json(ARQUIVO_ESTADO, dados)
    return True, 'Rollback feito: as correções foram descartadas e a versão em uso é a mesma de antes da mudança.'


def desfazer_commit(commit, usuario):
    """Depois do commit: git revert do commit do orquestrador + push + recarga (volta a versão anterior)."""
    hist = historico()
    registro = next((h for h in hist if h['commit'] == commit and not h.get('desfeito')), None)
    if not registro:
        return False, 'Commit do orquestrador não encontrado no histórico.'
    _, pendentes, _ = git('status', '--porcelain', '--untracked-files=no')
    if pendentes:
        return False, 'Há alterações não commitadas no código em uso: commit ou descarte antes de desfazer.'
    codigo, _, erro = git('revert', '--no-edit', commit)
    if codigo != 0:
        git('revert', '--abort')
        return False, f'Não foi possível desfazer automaticamente (conflito com mudanças posteriores): {erro[:300]}'
    _, ramo_atual, _ = git('rev-parse', '--abbrev-ref', 'HEAD')
    codigo, _, erro = git('push', 'origin', ramo_atual, tempo=180)
    _, recarga = ambiente.recarregar_aplicacao()
    registro.update(desfeito=True, desfeito_por=usuario, desfeito_em=datetime.now().isoformat(timespec='seconds'))
    _gravar_json(ARQUIVO_HISTORICO, hist)
    return True, f"Commit {commit[:8]} desfeito (revert{' e push' if codigo == 0 else '; push falhou: ' + erro[:120]}). {recarga}"


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+', required=True)
    parser.add_argument('--provedor', choices=['gemini', 'claude'], default='gemini')
    parser.add_argument('--usuario', default='Administrador')
    parser.add_argument('--equipes', nargs='+', default=[c for c, *_ in EQUIPES_VALIDACAO])
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, '.env'))
    except ImportError:
        pass
    executar(args.ids, args.provedor, args.usuario, args.equipes)
