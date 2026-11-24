"""Proteção local da atualização do cache, sem chamadas externas."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from painel_indicadores.seguranca import ErroDeAtualizacao, ProtecaoAtualizacao


def test_token_assinado_aceita_mesma_origem_normalizada() -> None:
    protecao = ProtecaoAtualizacao()
    token = protecao.emitir_token()
    protecao.validar(token, token, "HTTP://LOCALHOST:80", "http://localhost")


@pytest.mark.parametrize(
    "origem",
    [
        None,
        "null",
        "https://outro.test",
        "https://painel.test/",
        "https://painel.test?a=1",
        "https://usuario@painel.test",
        "https://painel.test#x",
        "https://painel.test:444",
        " https://painel.test",
    ],
)
def test_rejeita_origens_ausentes_ou_invalidas(origem: str | None) -> None:
    protecao = ProtecaoAtualizacao()
    token = protecao.emitir_token()
    with pytest.raises(ErroDeAtualizacao) as erro:
        protecao.validar(token, token, origem, "https://painel.test")
    assert erro.value.status == 403


@pytest.mark.parametrize("cookie", [None, "", "adulterado"])
def test_exige_cookie_igual_ao_formulario(cookie: str | None) -> None:
    protecao = ProtecaoAtualizacao()
    with pytest.raises(ErroDeAtualizacao) as erro:
        protecao.validar(
            protecao.emitir_token(), cookie, "http://local", "http://local"
        )
    assert erro.value.status == 403


def test_rejeita_token_falso_mesmo_com_cookie_igual() -> None:
    protecao = ProtecaoAtualizacao()
    for token in ["falso", "1.abc.def", "á", "", "1.a.b.c"]:
        with pytest.raises(ErroDeAtualizacao):
            protecao.validar(token, token, "http://local", "http://local")


def test_token_expira_em_duas_horas_e_rejeita_data_futura() -> None:
    agora = [10000.0]
    protecao = ProtecaoAtualizacao(relogio_utc=lambda: agora[0])
    token = protecao.emitir_token()
    for instante in [9999.0, 17200.0]:
        agora[0] = instante
        with pytest.raises(ErroDeAtualizacao):
            protecao.validar(token, token, "http://local", "http://local")


def test_chave_de_assinatura_compartilhada_no_processo() -> None:
    token = ProtecaoAtualizacao().emitir_token()
    ProtecaoAtualizacao().validar(token, token, "http://local", "http://local")


def test_reserva_bloqueia_ate_intervalo_e_separa_conjuntos() -> None:
    agora = [0.0]
    protecao = ProtecaoAtualizacao(relogio=lambda: agora[0])
    protecao.reservar("ipca")
    protecao.reservar("selic")
    agora[0] = 29.9
    with pytest.raises(ErroDeAtualizacao) as erro:
        protecao.reservar("ipca")
    assert erro.value.status == 429
    assert erro.value.mensagem
    agora[0] = 30.0
    protecao.reservar("ipca")


def test_reservas_concorrentes_so_permite_uma() -> None:
    protecao = ProtecaoAtualizacao()

    def reservar(_: int) -> bool:
        try:
            protecao.reservar("conjunto")
        except ErroDeAtualizacao:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reservar, range(20))) == 1


def test_limite_de_memoria_preserva_reservas_ativas() -> None:
    agora = [0.0]
    protecao = ProtecaoAtualizacao(relogio=lambda: agora[0])
    for indice in range(128):
        protecao.reservar(str(indice))
    with pytest.raises(ErroDeAtualizacao) as erro:
        protecao.reservar("novo")
    assert erro.value.status == 429
    with pytest.raises(ErroDeAtualizacao):
        protecao.reservar("0")
    agora[0] = 30.0
    protecao.reservar("novo")
