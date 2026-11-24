"""Servidor sintético exercita aplicação e exportação reais, sempre sem rede."""

import csv
import importlib.util
import io
from pathlib import Path

from fastapi.testclient import TestClient


def criar_cliente():
    caminho = Path(__file__).parents[1] / "apoio" / "servidor.py"
    assert caminho.exists(), "Factory sintética ainda não implementada"
    especificacao = importlib.util.spec_from_file_location("servidor_teste", caminho)
    assert especificacao is not None and especificacao.loader is not None
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return TestClient(modulo.criar_aplicacao_teste())


def test_servidor_identifica_dados_sinteticos_e_quatro_cards():
    with criar_cliente() as cliente:
        resposta = cliente.get("/?de=2026-01-01&ate=2026-03-31")
        assert resposta.status_code == 200
        assert resposta.headers["X-Dados-Teste"] == "sinteticos"
        assert 'role="status"' in resposta.text
        assert (
            "Ambiente de testes: dados sintéticos, sem consulta às fontes."
            in resposta.text
        )
        for codigo in (432, 433, 1, 1212):
            assert f'id="titulo-card-{codigo}"' in resposta.text
        assert (
            cliente.app.state.cliente_sintetico._transport.__class__.__name__
            == "MockTransport"
        )
    assert cliente.app.state.cliente_sintetico.is_closed


def test_exportacao_preserva_31_observacoes_e_lacuna_anual():
    with criar_cliente() as cliente:
        resposta = cliente.get(
            "/exportar.csv?codigo=432&de=2026-01-01&ate=2026-01-31&pagina=2"
        )
        linhas = list(
            csv.DictReader(
                io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";"
            )
        )
        assert len(linhas) == 31
        assert linhas[-1]["referencia"] == "2026-01-31"
        assert linhas[0]["valor"] == "14.000001"
        assert {
            "codigo",
            "referencia",
            "valor",
            "unidade",
            "fonte",
            "visualizacao",
            "data_referencia",
            "completo",
            "parcial",
            "motivo",
            "desatualizado",
            "versao_core",
        } <= linhas[0].keys()
        resposta = cliente.get(
            "/exportar.csv?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-03-31"
        )
        linhas = list(
            csv.DictReader(
                io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";"
            )
        )
        assert len(linhas) == 1
        assert linhas[0]["valor"] == ""
        assert linhas[0]["parcial"] == "sim"
        assert linhas[0]["completo"] == "nao"


def test_csv_ipca_12_meses_preserva_lacuna_entre_valores_completos():
    with criar_cliente() as cliente:
        resposta = cliente.get(
            "/exportar.csv?tipo=ipca12m&codigo=433&de=2026-01-01&ate=2026-03-31"
        )
        assert resposta.status_code == 200
        linhas = list(
            csv.DictReader(
                io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";"
            )
        )
        assert [linha["valor"] for linha in linhas] == ["4.000000", "", "4.500000"]
        assert linhas[1]["parcial"] == "sim"
        assert linhas[1]["completo"] == "nao"
