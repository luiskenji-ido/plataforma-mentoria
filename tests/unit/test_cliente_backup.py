"""cliente_backup: backup prévio pelo serviço privado (consulta, idempotência, recusas) e o interruptor do agendador."""

import pytest
import requests

import cliente_backup as cb


class Resposta:
    def __init__(self, status, corpo):
        self.status_code, self._corpo = status, corpo

    def json(self):
        return self._corpo


class Sessao:
    """Respostas na ordem; exceções na lista são levantadas."""

    def __init__(self, posts=(), gets=()):
        self.posts, self.gets, self.chamadas = list(posts), list(gets), []

    def _proxima(self, fila, metodo, url, kw):
        self.chamadas.append((metodo, url, kw))
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, **kw):
        return self._proxima(self.posts, "POST", url, kw)

    def get(self, url, **kw):
        return self._proxima(self.gets, "GET", url, kw)


@pytest.fixture(autouse=True)
def servico(monkeypatch):
    monkeypatch.setenv("BACKUP_SERVICO_URL", "https://backup.mentoria.interno:8443/")
    monkeypatch.setenv("BACKUP_SERVICO_PRAZO", "60")
    cb.esquecer_cache()


def test_espera_o_backup_terminar_consultando_o_estado():
    sessao = Sessao(
        posts=[Resposta(202, {"id": 7, "status": "Em andamento"})],
        gets=[Resposta(200, {"id": 7, "status": "Em andamento"}), Resposta(200, {"id": 7, "status": "Concluído", "arquivo": "x.sql.gz"})],
    )
    esperas = []
    execucao = cb.pedir_backup("pre_manutencao: otimizar", sessao=sessao, dormir=esperas.append)
    assert execucao["arquivo"] == "x.sql.gz" and esperas == [cb.INTERVALO_CONSULTA, cb.INTERVALO_CONSULTA]
    metodo, url, kw = sessao.chamadas[0]
    assert url == "https://backup.mentoria.interno:8443/api/v1/backups" and kw["headers"]["Idempotency-Key"].startswith("mentoria-")
    assert sessao.chamadas[1][1].endswith("/api/v1/backups/7")


def test_repete_o_post_so_em_erro_de_conexao_com_a_mesma_chave():
    sessao = Sessao(posts=[requests.ConnectionError(), Resposta(202, {"id": 1, "status": "Concluído"})])
    cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None)
    chaves = {kw["headers"]["Idempotency-Key"] for _, _, kw in sessao.chamadas}
    assert len(sessao.chamadas) == 2 and len(chaves) == 1  # a mesma chave: o serviço não duplica o backup


def test_inacessivel_depois_das_tentativas_recusa():
    sessao = Sessao(posts=[requests.ConnectionError()] * cb.TENTATIVAS_POST)
    with pytest.raises(cb.ErroServicoBackup, match="inacessível"):
        cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None)


def test_tempo_esgotado_na_leitura_nao_repete():
    sessao = Sessao(posts=[requests.ReadTimeout()])
    with pytest.raises(cb.ErroServicoBackup, match="não respondeu"):
        cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None)
    assert len(sessao.chamadas) == 1


@pytest.mark.parametrize("status, trecho", [(409, "ocupado"), (403, "HTTP 403"), (401, "HTTP 401")])
def test_recusas_do_servico(status, trecho):
    with pytest.raises(cb.ErroServicoBackup, match=trecho):
        cb.pedir_backup("x", sessao=Sessao(posts=[Resposta(status, {})]), dormir=lambda _: None)


def test_backup_que_falhou_recusa_com_o_motivo():
    sessao = Sessao(posts=[Resposta(202, {"id": 2, "status": "Falha", "detalhes": "Erro no backup: disco cheio"})])
    with pytest.raises(cb.ErroServicoBackup, match="disco cheio"):
        cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None)


def test_prazo_esgotado_recusa():
    relogio = iter([0, 30, 61, 62])
    sessao = Sessao(
        posts=[Resposta(202, {"id": 3, "status": "Em andamento"})], gets=[Resposta(200, {"id": 3, "status": "Em andamento"})] * 3
    )
    with pytest.raises(cb.ErroServicoBackup, match="não terminou"):
        cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None, relogio=lambda: next(relogio))


def test_consulta_com_erro_de_rede_continua_tentando():
    sessao = Sessao(
        posts=[Resposta(202, {"id": 4, "status": "Em andamento"})],
        gets=[requests.ConnectionError(), Resposta(200, {"id": 4, "status": "Verificado"})],
    )
    assert cb.pedir_backup("x", sessao=sessao, dormir=lambda _: None)["status"] == "Verificado"


def test_saude_converte_datas_guarda_em_cache_e_tolera_falha():
    sessao = Sessao(
        gets=[Resposta(200, {"situacao": "Saudável", "ultimo": "2026-11-22T03:00:01", "ultimo_verificado": None, "proximo": None})]
    )
    relogio = iter([100.0, 101.0, 130.0])
    primeira = cb.saude(sessao=sessao, relogio=lambda: next(relogio))
    assert primeira["ultimo"].year == 2026 and primeira["ultimo_verificado"] is None
    assert cb.saude(sessao=sessao, relogio=lambda: next(relogio)) is primeira and len(sessao.chamadas) == 1  # cache
    cb.esquecer_cache()
    assert cb.saude(sessao=Sessao(gets=[requests.ConnectTimeout()])) is None
    assert cb.saude(sessao=Sessao(gets=[Resposta(503, {})])) is None


def test_sem_url_o_cliente_fica_desligado(monkeypatch):
    monkeypatch.delenv("BACKUP_SERVICO_URL")
    assert not cb.configurado() and cb.saude() is None


@pytest.mark.parametrize("valor, no_monolito", [(None, True), ("monolito", True), ("servico", False), (" Servico ", False)])
def test_interruptor_do_agendador(monkeypatch, valor, no_monolito):
    if valor is None:
        monkeypatch.delenv("BACKUP_AGENDADOR", raising=False)
    else:
        monkeypatch.setenv("BACKUP_AGENDADOR", valor)
    assert cb.agendador_no_monolito() is no_monolito
