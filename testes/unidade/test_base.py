import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from painel_indicadores.aplicacao import criar_aplicacao
from painel_indicadores.cliente_api import ClienteAPI, ErroDeConsulta
from painel_indicadores.configuracao import ConfiguracaoPainel


def test_catalogo_real_arquivado():
    dados = json.loads(
        (Path(__file__).parents[1] / "amostras/catalogo.json").read_text(
            encoding="utf-8"
        )
    )

    def responder(pedido):
        assert pedido.url.path == "/api/v1/series"
        return httpx.Response(200, json=dados)

    with httpx.Client(
        base_url="http://api", transport=httpx.MockTransport(responder)
    ) as http:
        catalogo = ClienteAPI(http).buscar_catalogo()
    assert {serie.codigo for serie in catalogo.data} == {1, 432, 433}
    assert catalogo.meta.camada == "core"


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(503, text="segredo"),
        httpx.Response(200, text="invalido"),
        httpx.Response(200, json={"data": []}),
    ],
)
def test_falhas_sanitizadas(resposta):
    with (
        httpx.Client(
            base_url="http://api",
            transport=httpx.MockTransport(lambda pedido: resposta),
        ) as http,
        pytest.raises(ErroDeConsulta) as erro,
    ):
        ClienteAPI(http).buscar_catalogo()
    assert "segredo" not in str(erro.value)


def test_timeout_controlado():
    def responder(pedido):
        raise httpx.ReadTimeout("segredo")

    with (
        httpx.Client(
            base_url="http://api", transport=httpx.MockTransport(responder)
        ) as http,
        pytest.raises(ErroDeConsulta),
    ):
        ClienteAPI(http).buscar_catalogo()


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/api",
        "http://usuario:senha@api",
        "http://api?segredo=1",
        "http://api/#fragmento",
    ],
)
def test_url_invalida(url):
    with pytest.raises(ValidationError):
        ConfiguracaoPainel(_env_file=None, url_base_api=url)


def test_timeout_positivo():
    with pytest.raises(ValidationError):
        ConfiguracaoPainel(_env_file=None, tempo_leitura_segundos=0)


def test_saude_independe_da_api():
    with TestClient(criar_aplicacao()) as cliente:
        assert cliente.get("/health").json() == {"situacao": "ativo"}


@pytest.mark.parametrize("status,esperado", [(200, True), (503, False)])
def test_sondagem_processo_nao_confunde_com_disponibilidade_dos_dados(status, esperado):
    def responder(pedido):
        assert pedido.url.path == "/health"
        return httpx.Response(status, json={"situacao": "ativo"})

    with httpx.Client(
        base_url="http://api", transport=httpx.MockTransport(responder)
    ) as http:
        assert ClienteAPI(http).verificar_processo() is esperado


def test_sondagem_nao_baixa_corpo_desnecessario():
    class CorpoNaoConsumivel(httpx.SyncByteStream):
        def __iter__(self):
            raise AssertionError("A sondagem deve usar somente status/cabeçalhos.")
            yield b""  # pragma: no cover

    with httpx.Client(
        base_url="http://api",
        transport=httpx.MockTransport(
            lambda pedido: httpx.Response(200, stream=CorpoNaoConsumivel())
        ),
    ) as http:
        assert ClienteAPI(http).verificar_processo()
