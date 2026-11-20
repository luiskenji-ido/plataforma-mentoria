# -*- coding: utf-8 -*-
"""
LIMPEZA DOS DADOS DO FLUXO FUNCIONAL
====================================
Apaga tudo o que os Agentes de Funcionalidades criaram, sem deixar órfãos:
  - raízes: usuários *_funcional@local.com e qualquer linha com a marca [Funcional] em colunas de texto;
  - em cascata: todas as linhas que apontam para as raízes (mapa de chaves estrangeiras do próprio banco),
    inclusive tabelas de associação (grupo_usuario, turma_aluno…);
  - arquivos: entregas do TCC, acervo e currículos ligados às linhas apagadas.
O Gerente faz um backup antes da execução do fluxo; esta limpeza só roda dentro de um app_context.
Uso direto: python agentes_funcionalidades/limpeza.py
"""
import os
import sys

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

MARCA = "[Funcional]"
DOMINIO = "%_funcional@local.com"


def _q(nome):
    return '"' + nome.replace('"', '') + '"'


def _mapa_filhos(db):
    """{tabela_pai: [(tabela_filha, coluna_fk)]} pelas chaves estrangeiras declaradas nos modelos."""
    filhos = {}
    for tabela in db.metadata.tables.values():
        for fk in tabela.foreign_keys:
            filhos.setdefault(fk.column.table.name, []).append((tabela.name, fk.parent.name))
    return filhos


def _pk(db, tabela):
    colunas = [c.name for c in db.metadata.tables[tabela].primary_key.columns]
    return colunas[0] if len(colunas) == 1 else None


def limpar(registrar=print):
    from sqlalchemy import text
    from app import app, db, PASTA_TCC, PASTA_ACERVO, PASTA_LOGOS, PASTA_GRAVACOES, PASTA_AULAS
    with app.app_context():
        con = db.session.connection()
        filhos = _mapa_filhos(db)
        apagar = {}  # tabela -> set(ids)

        def marcar(tabela, ids):
            ids = set(ids) - apagar.get(tabela, set())
            if not ids:
                return
            apagar.setdefault(tabela, set()).update(ids)
            for filha, coluna in filhos.get(tabela, []):
                pk = _pk(db, filha)
                if pk is None:
                    continue  # associação: apagada direto no fim
                lista = ",".join(str(int(i)) for i in ids)
                novos = [r[0] for r in con.execute(text(f"SELECT {_q(pk)} FROM {_q(filha)} WHERE {_q(coluna)} IN ({lista})"))]
                marcar(filha, novos)

        usuarios = [r[0] for r in con.execute(text("SELECT id FROM usuario WHERE email LIKE :d"), {"d": DOMINIO})]
        marcar("usuario", usuarios)
        for nome, tabela in db.metadata.tables.items():
            pk = _pk(db, nome)
            if pk is None:
                continue
            colunas_texto = [c.name for c in tabela.columns if str(c.type).upper().startswith(("VARCHAR", "TEXT", "STRING"))]
            for coluna in colunas_texto:
                ids = [r[0] for r in con.execute(text(f"SELECT {_q(pk)} FROM {_q(nome)} WHERE {_q(coluna)} LIKE :m"), {"m": f"%{MARCA}%"})]
                marcar(nome, ids)

        # Arquivos ligados às linhas que vão sair
        arquivos = []
        if apagar.get("entrega_tcc"):
            lista = ",".join(str(i) for i in apagar["entrega_tcc"])
            arquivos += [os.path.join(PASTA_TCC, r[0]) for r in con.execute(text(f"SELECT arquivo FROM entrega_tcc WHERE id IN ({lista})")) if r[0]]
        if apagar.get("tcc_acervo"):
            lista = ",".join(str(i) for i in apagar["tcc_acervo"])
            for r in con.execute(text(f"SELECT arquivo_pdf, arquivo_slides FROM tcc_acervo WHERE id IN ({lista})")):
                arquivos += [os.path.join(PASTA_ACERVO, a) for a in r if a]

        if apagar.get("empresa"):
            lista = ",".join(str(i) for i in apagar["empresa"])
            arquivos += [os.path.join(PASTA_LOGOS, r[0]) for r in con.execute(text(f"SELECT logo_arquivo FROM empresa WHERE id IN ({lista})")) if r[0]]

        if apagar.get("reuniao_institucional"):  # arquivo da gravação enviado à reunião
            lista = ",".join(str(int(i)) for i in apagar["reuniao_institucional"])
            arquivos += [os.path.join(PASTA_GRAVACOES, r[0]) for r in
                         con.execute(text(f"SELECT gravacao_arquivo FROM reuniao_institucional WHERE id IN ({lista})")) if r[0]]

        if apagar.get("aula_curso"):  # vídeos e materiais enviados às aulas dos cursos
            lista = ",".join(str(int(i)) for i in apagar["aula_curso"])
            for r in con.execute(text(f"SELECT video_arquivo, material_arquivo FROM aula_curso WHERE id IN ({lista})")):
                arquivos += [os.path.join(PASTA_AULAS, a) for a in r if a]

        if apagar.get("fonte_conhecimento"):  # documentos enviados ao Assistente da Plataforma
            lista = ",".join(str(int(i)) for i in apagar["fonte_conhecimento"])
            # documentos novos guardam a chave relativa ('base_conhecimento/x'); os antigos, o caminho absoluto
            arquivos += [r[0] if os.path.isabs(r[0]) else os.path.join(app.config["UPLOAD_FOLDER"], r[0])
                         for r in con.execute(text(f"SELECT arquivo_caminho FROM fonte_conhecimento WHERE id IN ({lista})")) if r[0]]

        # Associações (sem PK própria) que apontam para qualquer linha apagada
        total = 0
        for pai, ids in apagar.items():
            lista = ",".join(str(int(i)) for i in ids)
            for filha, coluna in filhos.get(pai, []):
                if _pk(db, filha) is None:
                    total += con.execute(text(f"DELETE FROM {_q(filha)} WHERE {_q(coluna)} IN ({lista})")).rowcount
        # Linhas: filhas antes das mães (ordem inversa das dependências)
        ordem = [t.name for t in reversed(db.metadata.sorted_tables)]
        for tabela in ordem:
            ids = apagar.get(tabela)
            if ids:
                lista = ",".join(str(int(i)) for i in ids)
                total += con.execute(text(f"DELETE FROM {_q(tabela)} WHERE {_q(_pk(db, tabela))} IN ({lista})")).rowcount
        db.session.commit()
        removidos = 0
        for caminho in arquivos:
            try:
                os.remove(caminho)
                removidos += 1
            except OSError:
                pass
        resumo = {t: len(i) for t, i in sorted(apagar.items())}
        registrar(f"🧹 Limpeza: {total} linha(s) em {len(resumo)} tabela(s) e {removidos} arquivo(s) removidos")
        # Conferência: nada do fluxo pode sobrar
        sobras = db.session.execute(text("SELECT COUNT(*) FROM usuario WHERE email LIKE :d"), {"d": DOMINIO}).scalar()
        return {"linhas": total, "tabelas": resumo, "arquivos": removidos, "sobras_usuarios": sobras}


if __name__ == "__main__":
    print(limpar())
