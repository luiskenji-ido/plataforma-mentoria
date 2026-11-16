# -*- coding: utf-8 -*-
"""Os quatro Gerentes aprendem as mudanças da cópia corrigida (na cópia do banco) antes dos testes.
Uso: python aprender_validacao.py <pasta da cópia>. Imprime, na última linha, um JSON {gerente: [aprendizados]}."""
import json
import os
import sys

raiz = os.path.abspath(sys.argv[1])
os.chdir(raiz)
sys.path.insert(0, raiz)
from app import app  # noqa: E402

resultado = {}
with app.app_context():
    for nome, modulo in (('Gerente Técnico (Fim a Fim)', 'conhecimento'), ('Gerente de Segurança', 'conhecimento_seguranca'),
                         ('Gerente de Banco de Dados', 'conhecimento_banco'), ('Gerente de Funcionalidades', 'conhecimento_funcional')):
        try:
            itens = __import__(modulo).detectar_mudancas('Orquestrador executor (validação da correção)')
            resultado[nome] = [f"{a.codigo}: {a.titulo}" for a in itens]
        except Exception as e:
            resultado[nome] = [f"erro ao aprender: {e.__class__.__name__}: {e}"]
print(json.dumps(resultado, ensure_ascii=False))
