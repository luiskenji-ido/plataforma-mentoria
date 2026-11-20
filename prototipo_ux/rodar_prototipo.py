# -*- coding: utf-8 -*-
"""
PROTÓTIPO DE UX/UI — a plataforma real com o visual proposto, sem tocar em produção
==================================================================================
Roda o mesmo app.py numa CÓPIA do banco (prototipo_ux/dados/prototipo.db) e numa porta própria, com:
  - o tema proposto (prototipo_ux/static/tema.css) injetado em todas as telas;
  - as telas redesenhadas de prototipo_ux/templates/ no lugar das de produção (as demais continuam as atuais).
Nenhum arquivo de produção é alterado: apagar a pasta prototipo_ux desfaz tudo.

Uso (na raiz do projeto):
  python prototipo_ux/rodar_prototipo.py              → protótipo em http://127.0.0.1:5070
  python prototipo_ux/rodar_prototipo.py --sem-tema   → a mesma cópia com o visual atual em http://127.0.0.1:5071 (o "antes")
  python prototipo_ux/rodar_prototipo.py --novo-banco → recopia o banco de instance/mentoria.db antes de subir
Contas de demonstração (só desta cópia): veja prototipo_ux/LEIAME.md.
"""
import os
import re
import sys
import shutil
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA)
BANCO = os.path.join(PASTA, 'dados', 'prototipo.db')
SEM_TEMA = '--sem-tema' in sys.argv
PORTA = 5071 if SEM_TEMA else 5070  # 5060 e 5061 são bloqueadas pelos navegadores
CONTAS = [('demo_admin@local.com', 'Demo Gestão', 'Administrador'), ('demo_aluno@local.com', 'Demo Aluno', 'Aluno')]

MINIMO_CARACTERES_SENHA_DEMO = 12  # senha guardada menor que isto é trocada por uma nova


def _senha_demo():
    """Senha das contas de demonstração (só existem na cópia do protótipo): PROTOTIPO_SENHA_DEMO no ambiente ou, sem
    ela, uma senha aleatória gerada uma vez e guardada em prototipo_ux/dados/senha_demo.txt (fora do Git). Os scripts
    de captura e de contraste importam a mesma senha daqui."""
    senha = (os.environ.get('PROTOTIPO_SENHA_DEMO') or '').strip()
    if senha:
        return senha
    arquivo = os.path.join(PASTA, 'dados', 'senha_demo.txt')
    try:
        with open(arquivo, encoding='utf-8') as f:
            senha = f.read().strip()
    except OSError:
        senha = ''
    if len(senha) < MINIMO_CARACTERES_SENHA_DEMO:
        import secrets
        senha = 'Demo@9' + secrets.token_urlsafe(12)  # atende à política de senha forte (maiúscula, número, símbolo)
        os.makedirs(os.path.dirname(arquivo), exist_ok=True)
        with open(arquivo, 'w', encoding='utf-8') as f:
            f.write(senha)
    return senha


SENHA_DEMO = _senha_demo()

if '--novo-banco' in sys.argv or not os.path.exists(BANCO):
    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    shutil.copyfile(os.path.join(RAIZ, 'instance', 'mentoria.db'), BANCO)
os.environ['DATABASE_URL'] = 'sqlite:///' + BANCO.replace('\\', '/')
os.environ['MENTORIA_SEM_EXECUCAO_AUTOMATICA'] = '1'  # CR de código aprovada na cópia nunca dispara o executor (ele mexe no git real)
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from app import app, db, bcrypt, VERSAO_TERMO_ATUAL  # noqa: E402  (precisa do DATABASE_URL acima)


def semear_contas():
    """Contas de demonstração prontas para entrar (termo aceito e perguntas de segurança feitas)."""
    from models import Usuario, TermoAceite, SegurancaUsuario
    with app.app_context():
        for email, nome, tipo in CONTAS:
            u = Usuario.query.filter_by(email=email).first()
            if not u:
                u = Usuario(nome=nome, email=email, tipo_usuario=tipo, status='Ativo')
                db.session.add(u)
            u.senha = bcrypt.generate_password_hash(SENHA_DEMO).decode()
            u.forcar_troca_senha, u.data_ultima_troca_senha, u.status = False, datetime.utcnow(), 'Ativo'
            db.session.commit()
            if not TermoAceite.query.filter_by(usuario_id=u.id, versao_termo=VERSAO_TERMO_ATUAL).first():
                db.session.add(TermoAceite(usuario_id=u.id, versao_termo=VERSAO_TERMO_ATUAL))
            if not SegurancaUsuario.query.filter_by(usuario_id=u.id).first():
                import secrets
                resposta = bcrypt.generate_password_hash(secrets.token_urlsafe(16)).decode()  # ninguém precisa recuperar a conta demo
                db.session.add(SegurancaUsuario(usuario_id=u.id, pergunta_1='Qual é a sua cor favorita?', resposta_1=resposta,
                                                pergunta_2='Em qual cidade você nasceu?', resposta_2=resposta,
                                                pergunta_3='Qual é o seu prato favorito?', resposta_3=resposta))
            db.session.commit()


def aplicar_tema():
    from jinja2 import ChoiceLoader, FileSystemLoader
    app.jinja_env.loader = ChoiceLoader([FileSystemLoader(os.path.join(PASTA, 'templates')), app.jinja_env.loader])
    app.jinja_env.cache = {}
    # tokens.css (paletas por tema, com contraste conferido por paletas.py) vem antes do tema que os usa. Lidos a cada
    # página: mudar a paleta ou o tema.css aparece no próximo F5, sem reiniciar o protótipo
    import importlib
    import paletas

    def cabeca():
        importlib.reload(paletas)
        ruins = paletas.conferir()
        if ruins:
            raise SystemExit('Paleta com contraste abaixo do mínimo:\n  ' + '\n  '.join(ruins))
        with open(os.path.join(PASTA, 'static', 'tema.css'), encoding='utf-8') as f:
            css = paletas.css() + f.read()
        return ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&'
                'family=Space+Grotesk:wght@500;600;700&display=swap"><style id="tema-prototipo">' + css + '</style></head>')
    cabeca()  # paleta reprovada: o protótipo nem sobe
    selo = '<div class="proto-selo">Protótipo de UX/UI · cópia do banco, não é produção</div></body>'

    @app.after_request
    def injetar_tema(resposta):
        if resposta.mimetype == 'text/html' and not resposta.direct_passthrough:
            html = resposta.get_data(as_text=True)
            if '</head>' in html:
                html = html.replace('</head>', cabeca(), 1)
                html = re.sub(r'<html(\s|>)', r'<html data-proto="ux"\1', html, count=1)
                html = html[::-1].replace('</body>'[::-1], selo[::-1], 1)[::-1]
                resposta.set_data(html)
        return resposta


if __name__ == '__main__':
    semear_contas()
    if not SEM_TEMA:
        aplicar_tema()
    print(f"{'Visual atual (antes)' if SEM_TEMA else 'Protótipo de UX/UI'} em http://127.0.0.1:{PORTA}  ·  banco: {BANCO}")
    app.run(port=PORTA, debug=False)
