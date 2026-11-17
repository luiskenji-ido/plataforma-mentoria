"""
MASSA DE DADOS DO OMNITEST
==========================
Cria (ou remove) um cenário completo de teste, tudo marcado com "[OmniTest]":

  - grupo "[OmniTest] Grupo de Mentoria" com o Aluno e o Mentor de teste
  - TCC em andamento com banca agendada para daqui a 1 hora, escrito final e slides entregues,
    tendo o Avaliador Banca de teste como avaliador
  - TCC concluído, com banca realizada, avaliação completa e resultado publicado
    (gera certificados para o jovem, o mentor e o avaliador)
  - TCC de outro grupo, com banca e entrega, em que o avaliador de teste NÃO está escalado (isolamento)
  - horas de voluntariado do mentor e do avaliador ligadas a esses TCCs (alimentam os indicadores)

Os utilizadores de teste (logins *_ominitest@local.com) ficam: são os mesmos que os agentes usam.

Uso:
    python agentes_omnitest/massa_dados.py              # cria ou atualiza (pode rodar quantas vezes quiser)
    python agentes_omnitest/massa_dados.py --remover    # apaga tudo o que a massa criou
"""
import os
import sys
import argparse
from datetime import datetime, timedelta

from nucleo import preparar_usuario, PERFIS

GRUPO = "[OmniTest] Grupo de Mentoria"
PROJETO_ABERTO = "[OmniTest] TCC Educação Financeira"
PROJETO_CONCLUIDO = "[OmniTest] TCC Seguro para Jovens"
PROJETO_OUTRO = "[OmniTest] TCC de outro grupo"  # banca sem o avaliador de teste (isolamento)
MARCA_HORAS = "Massa OmniTest"
PDF_TESTE = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
PERFIS_DA_MASSA = ["administrador", "aluno", "mentor", "avaliador"]


def _usuarios():
    from models import Usuario
    return {chave: Usuario.query.filter_by(email=PERFIS[chave]["email"]).first() for chave in PERFIS_DA_MASSA}


def _salvar_pdf(pasta, nome):
    caminho = os.path.join(pasta, nome)
    if not os.path.exists(caminho):
        with open(caminho, "wb") as f:
            f.write(PDF_TESTE)
    return nome


def garantir_massa():
    """Cria o que faltar e deixa a banca em andamento sempre para daqui a 1 hora. Devolve um resumo."""
    for chave in PERFIS_DA_MASSA:
        preparar_usuario(chave)

    from app import app, db, PASTA_TCC
    from models import (Grupo, Projeto, Banca, EntregaTCC, AvaliacaoBanca, CheckinVoluntariado, PerfilAvaliador)

    criados = []
    with app.app_context():
        u = _usuarios()
        agora = datetime.now()

        if not PerfilAvaliador.query.filter_by(usuario_id=u["avaliador"].id).first():
            db.session.add(PerfilAvaliador(usuario_id=u["avaliador"].id, nome_completo="Avaliador OmniTest da Silva",
                                           empresa_origem="Parceiro B2B (teste)", area_atuacao="Riscos Corporativos",
                                           curriculo_minibio="Executivo de teste do OmniTest (15 anos em seguros)."))
            criados.append("perfil do avaliador")

        grupo = Grupo.query.filter_by(nome=GRUPO).first()
        if not grupo:
            grupo = Grupo(nome=GRUPO, descricao="Grupo de teste do OmniTest")
            db.session.add(grupo)
            criados.append("grupo")
        for membro in (u["aluno"], u["mentor"]):
            if membro not in grupo.membros:
                grupo.membros.append(membro)
        db.session.flush()

        # --- TCC em andamento: banca daqui a 1 hora (dentro da janela de check-in do avaliador)
        aberto = Projeto.query.filter_by(nome=PROJETO_ABERTO).first()
        if not aberto:
            aberto = Projeto(nome=PROJETO_ABERTO, grupo_id=grupo.id, status="Em Andamento",
                             descricao="Educação financeira para jovens do ensino médio (massa de teste).")
            db.session.add(aberto)
            db.session.flush()
            criados.append("TCC em andamento")
        banca = Banca.query.filter_by(projeto_id=aberto.id).first()
        if not banca:
            banca = Banca(projeto_id=aberto.id, criado_por_id=u["administrador"].id)
            db.session.add(banca)
            criados.append("banca agendada")
        banca.data_hora = (agora + timedelta(hours=1)).replace(second=0, microsecond=0)
        banca.local = "Auditório B2B (teste)"
        banca.status = "Agendada"
        banca.encerrada_em = None
        banca.prazo_entrega_escrito = agora + timedelta(days=2)
        banca.prazo_entrega_slides = agora + timedelta(days=2)
        banca.prazo_leitura_avaliadores = agora + timedelta(days=3)
        if u["avaliador"] not in banca.avaliadores:
            banca.avaliadores.append(u["avaliador"])
        db.session.flush()
        for tipo, sufixo in (("Escrito final", "escrito"), ("Slides da apresentação", "slides")):
            if not EntregaTCC.query.filter_by(projeto_id=aberto.id, tipo=tipo).first():
                nome = _salvar_pdf(PASTA_TCC, f"omnitest_massa_{aberto.id}_{sufixo}.pdf")
                db.session.add(EntregaTCC(projeto_id=aberto.id, tipo=tipo, arquivo=nome, nome_original=f"{sufixo}.pdf",
                                          versao=1, enviado_por_id=u["aluno"].id, entregue_no_prazo=True))
                criados.append(f"entrega ({sufixo})")

        # --- TCC concluído: banca realizada e resultado publicado
        concluido = Projeto.query.filter_by(nome=PROJETO_CONCLUIDO).first()
        if not concluido:
            concluido = Projeto(nome=PROJETO_CONCLUIDO, grupo_id=grupo.id, status="Concluído",
                                descricao="Seguro de vida explicado para jovens (massa de teste).",
                                nota_conteudo=9.0, nota_apresentacao=8.5, nota_visual=8.0, nota_final=8.6,
                                data_avaliacao=agora - timedelta(days=7), notas_publicadas=True,
                                data_publicacao_notas=agora - timedelta(days=6))
            db.session.add(concluido)
            db.session.flush()
            criados.append("TCC concluído")
        realizada = Banca.query.filter_by(projeto_id=concluido.id).first()
        if not realizada:
            realizada = Banca(projeto_id=concluido.id, criado_por_id=u["administrador"].id, local="Sala virtual (teste)",
                              data_hora=agora - timedelta(days=7), status="Realizada", encerrada_em=agora - timedelta(days=7))
            realizada.avaliadores.append(u["avaliador"])
            db.session.add(realizada)
            db.session.flush()
            criados.append("banca realizada")
        if not EntregaTCC.query.filter_by(projeto_id=concluido.id, tipo="Escrito final").first():
            nome = _salvar_pdf(PASTA_TCC, f"omnitest_massa_{concluido.id}_escrito.pdf")
            db.session.add(EntregaTCC(projeto_id=concluido.id, tipo="Escrito final", arquivo=nome, nome_original="escrito.pdf",
                                      versao=1, enviado_por_id=u["aluno"].id, data_envio=agora - timedelta(days=10)))
        if not AvaliacaoBanca.query.filter_by(projeto_id=concluido.id, avaliador_id=u["avaliador"].id).first():
            db.session.add(AvaliacaoBanca(projeto_id=concluido.id, banca_id=realizada.id, avaliador_id=u["avaliador"].id,
                                          nota_escrita=9.0, nota_apresentacao=8.5, nota_visual=8.0,
                                          feedback_jovens="Ótima pesquisa; caprichem nos exemplos práticos.",
                                          etapa_escrita_concluida_em=agora - timedelta(days=8),
                                          etapa_oral_concluida_em=agora - timedelta(days=7)))
            criados.append("avaliação da banca")

        # --- TCC de outro grupo: o avaliador de teste não pode abrir a banca nem baixar o arquivo
        outro_grupo = Grupo.query.filter_by(nome="[OmniTest] Outro grupo").first()
        if not outro_grupo:
            outro_grupo = Grupo(nome="[OmniTest] Outro grupo", descricao="Grupo sem os utilizadores de teste")
            db.session.add(outro_grupo)
            db.session.flush()
        outro = Projeto.query.filter_by(nome=PROJETO_OUTRO).first()
        if not outro:
            outro = Projeto(nome=PROJETO_OUTRO, grupo_id=outro_grupo.id, status="Em Andamento",
                            descricao="Projeto de outro grupo (massa de teste).")
            db.session.add(outro)
            db.session.flush()
            db.session.add(Banca(projeto_id=outro.id, criado_por_id=u["administrador"].id, local="Sala 2 (teste)",
                                 data_hora=(agora + timedelta(days=5)).replace(second=0, microsecond=0), status="Agendada"))
            nome = _salvar_pdf(PASTA_TCC, f"omnitest_massa_{outro.id}_escrito.pdf")
            db.session.add(EntregaTCC(projeto_id=outro.id, tipo="Escrito final", arquivo=nome, nome_original="escrito.pdf",
                                      versao=1, enviado_por_id=u["administrador"].id))
            criados.append("TCC de outro grupo")

        # --- Horas de voluntariado (indicadores e certificados)
        if not CheckinVoluntariado.query.filter_by(observacoes=MARCA_HORAS).first():
            base = agora - timedelta(days=9)
            for usuario, tipo, minutos, projeto_id, grupo_id in (
                    (u["avaliador"], "Leitura Assíncrona de TCC", 90, concluido.id, None),
                    (u["avaliador"], "Avaliação de Banca Ao Vivo", 40, concluido.id, None),
                    (u["mentor"], "Mentoria Extraordinária", 60, None, grupo.id)):
                db.session.add(CheckinVoluntariado(usuario_id=usuario.id, tipo_atividade=tipo, projeto_id=projeto_id, grupo_id=grupo_id,
                                                   categoria="Extra" if grupo_id else "Regular", data_hora_inicio=base,
                                                   data_hora_fim=base + timedelta(minutes=minutos), total_minutos=minutos,
                                                   observacoes=MARCA_HORAS))
            criados.append("horas de voluntariado")

        db.session.commit()
    return "criado: " + ", ".join(criados) if criados else "já existia (banca reagendada para daqui a 1 hora)"


def ids_da_massa():
    """(ids dos projetos, ids dos grupos) com o prefixo [OmniTest]."""
    from models import Grupo, Projeto
    projetos = [p.id for p in Projeto.query.filter(Projeto.nome.like("[OmniTest]%")).all()]
    grupos = [g.id for g in Grupo.query.filter(Grupo.nome.like("[OmniTest]%")).all()]
    return projetos, grupos


def remover_massa():
    """Apaga grupos e projetos [OmniTest] com tudo o que depende deles. Os utilizadores de teste ficam."""
    from app import app, db, PASTA_TCC, PASTA_ACERVO
    from models import (Grupo, Projeto, Banca, EntregaTCC, AvaliacaoBanca, CheckinVoluntariado, QABanca, HistoricoDataBanca,
                        EnvioFormularioBanca, CertificadoEmitido, TCCAcervo, PerfilAvaliador, Usuario)

    def apagar_arquivo(pasta, nome):
        if nome and os.path.exists(os.path.join(pasta, nome)):
            os.remove(os.path.join(pasta, nome))

    with app.app_context():
        projetos, grupos = ids_da_massa()
        contagem = {"projetos": len(projetos), "grupos": len(grupos)}
        if projetos:
            for e in EntregaTCC.query.filter(EntregaTCC.projeto_id.in_(projetos)).all():
                apagar_arquivo(PASTA_TCC, e.arquivo)
                db.session.delete(e)
            for a in TCCAcervo.query.filter(TCCAcervo.projeto_id.in_(projetos)).all():
                apagar_arquivo(PASTA_ACERVO, a.arquivo_pdf)
                apagar_arquivo(PASTA_ACERVO, a.arquivo_slides)
                db.session.delete(a)
            bancas = Banca.query.filter(Banca.projeto_id.in_(projetos)).all()
            ids_bancas = [b.id for b in bancas]
            if ids_bancas:
                HistoricoDataBanca.query.filter(HistoricoDataBanca.banca_id.in_(ids_bancas)).delete(synchronize_session=False)
                EnvioFormularioBanca.query.filter(EnvioFormularioBanca.banca_id.in_(ids_bancas)).delete(synchronize_session=False)
            for modelo in (AvaliacaoBanca, QABanca, CertificadoEmitido):
                modelo.query.filter(modelo.projeto_id.in_(projetos)).delete(synchronize_session=False)
            contagem["horas"] = CheckinVoluntariado.query.filter(CheckinVoluntariado.projeto_id.in_(projetos)).delete(synchronize_session=False)
            for b in bancas:
                b.avaliadores.clear()
                db.session.delete(b)
            db.session.flush()
        if grupos:
            contagem["horas"] = contagem.get("horas", 0) + CheckinVoluntariado.query.filter(
                CheckinVoluntariado.grupo_id.in_(grupos)).delete(synchronize_session=False)
        contagem["horas"] = contagem.get("horas", 0) + CheckinVoluntariado.query.filter_by(observacoes=MARCA_HORAS).delete(synchronize_session=False)
        for p in Projeto.query.filter(Projeto.id.in_(projetos)).all() if projetos else []:
            db.session.delete(p)
        for g in Grupo.query.filter(Grupo.id.in_(grupos)).all() if grupos else []:
            g.membros.clear()
            db.session.delete(g)
        avaliador = Usuario.query.filter_by(email=PERFIS["avaliador"]["email"]).first()
        if avaliador:
            PerfilAvaliador.query.filter_by(usuario_id=avaliador.id).delete(synchronize_session=False)
        db.session.commit()
    return (f"{contagem['projetos']} projeto(s), {contagem['grupos']} grupo(s) e "
            f"{contagem.get('horas', 0)} lançamento(s) de horas [OmniTest] apagados")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cria ou remove a massa de dados [OmniTest].")
    parser.add_argument("--remover", action="store_true", help="Apaga tudo o que a massa criou (os logins de teste ficam).")
    args = parser.parse_args()
    print(("🧹 " + remover_massa()) if args.remover else ("🌱 Massa de dados: " + garantir_massa()))
    sys.exit(0)
