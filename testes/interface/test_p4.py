"""Cenários sintéticos P4, sem rede ou dados operacionais."""

import csv
import io
from datetime import date
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from painel_indicadores.aplicacao import criar_aplicacao
from painel_indicadores.contratos import (
    ConjuntoAgregados,
    ConjuntoObservacoes,
    RespostaFrescor,
)
from painel_indicadores.indicadores import PanoramaIndicadores, criar_card
from painel_indicadores.rotas import obter_servico

HOJE = date(2026, 11, 23)


def gold(**alteracoes):
    return ConjuntoAgregados.model_validate(
        {
            "agregados": [
                {
                    "periodo": "2026-01-01",
                    "unidade": "% no ano",
                    "observacoes": 10,
                    "variacao": None,
                    "completo": False,
                    "parcial": True,
                    "motivo": "PERIODO_EM_ANDAMENTO",
                    "data_referencia": "2026-11-23",
                }
            ],
            "meta": {
                "camada": "gold",
                "versao_dados": 2,
                "versao_core": 3,
                "versao_gold": 2,
                "codigo": 433,
                "unidade": "% no ano",
                "de": "2026-01-01",
                "ate": "2026-11-23",
                "data_publicacao": "2026-11-23",
                "desatualizado": True,
                "motivo": "CORE_NOVO",
            },
            "consulta_completa": True,
            "consultado_em": "2026-11-23T01:00:00Z",
            **alteracoes,
        }
    )


@pytest.fixture
def ambiente():
    historicos = {}
    for codigo in (432, 433, 1):
        historicos[codigo] = ConjuntoObservacoes.model_validate(
            {
                "observacoes": [
                    {"data": f"2026-01-{dia:02d}", "valor": "1.000000"}
                    for dia in range(1, 32)
                ],
                "meta": {
                    "camada": "core",
                    "versao_dados": 3,
                    "versao_core": 3,
                    "versao_gold": 2,
                    "codigo": codigo,
                    "unidade": "% a.a.",
                    "de": "2020-01-01",
                    "ate": str(HOJE),
                },
                "consulta_completa": True,
                "consultado_em": "2026-11-23T01:00:00Z",
            }
        )
    servico = Mock()
    servico.obter_contexto.return_value = PanoramaIndicadores(
        cards=tuple(
            criar_card(codigo, dados, HOJE) for codigo, dados in historicos.items()
        ),
        historicos=historicos,
    )
    servico.obter_gold.return_value = gold()
    servico.obter_ipca_12m.return_value = gold().model_copy(
        update={
            "meta": gold().meta.model_copy(
                update={"de": date(2020, 1, 1), "unidade": "% no periodo"}
            )
        }
    )
    servico.obter_historico.return_value = historicos[432]
    servico.obter_frescor.return_value = RespostaFrescor.model_validate(
        {
            "data": [
                {
                    "codigo": 433,
                    "unidade": "% no mes",
                    "cobertura": None,
                    "ultima_consulta": "2026-11-23T00:30:00Z",
                    "ultima_referencia": "2026-10-01",
                    "ultima_publicacao": "2026-11-23T01:00:00Z",
                    "defasado": None,
                    "politica": "TESTE",
                    "calendario_homologado": False,
                    "motivo": "SEM_CALENDARIO",
                }
            ],
            "meta": {
                "camada": "gold",
                "versao_dados": 2,
                "versao_core": 3,
                "versao_gold": 2,
            },
            "consultado_em": "2026-11-23T01:30:00Z",
        }
    )
    servico.verificar_processo.return_value = True
    app = criar_aplicacao()
    app.dependency_overrides[obter_servico] = lambda: servico
    with TestClient(app) as cliente:
        yield cliente, servico


def test_gold_preserva_lacuna_e_avisos(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-11-23")
    assert resposta.status_code == 200
    assert "Gold desatualizada" in resposta.text
    assert "PERIODO_EM_ANDAMENTO" in resposta.text
    assert "IPCA em 12 meses" in resposta.text
    assert "Publicação gold" in resposta.text
    assert "23/11/2026" in resposta.text
    assert 'name="visualizacao"' in resposta.text
    assert "SGS 1212" not in resposta.text


def test_frescor_utc_e_datas_nao_se_confundem(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433")
    assert "22/11/2026 às 21:30" in resposta.text
    assert "10/2026" in resposta.text
    assert "Desconhecido" in resposta.text
    assert "Consulta pelo painel" in resposta.text


def test_falha_frescor_preserva_grafico(ambiente):
    from painel_indicadores.cliente_api import ErroDeConsulta

    cliente, servico = ambiente
    servico.obter_frescor.side_effect = ErroDeConsulta(
        "Frescor temporariamente indisponível"
    )
    resposta = cliente.get("/?de=2026-01-01&ate=2026-01-31")
    assert resposta.status_code == 200
    assert 'id="dados-grafico"' in resposta.text
    assert "Frescor temporariamente indisponível" in resposta.text


def test_falha_ipca12_preserva_quarto_card_indisponivel(ambiente):
    from painel_indicadores.cliente_api import ErroDeConsulta

    cliente, servico = ambiente
    servico.obter_ipca_12m.side_effect = ErroDeConsulta("Indicador indisponível")
    resposta = cliente.get("/")
    assert 'id="titulo-card-1212"' in resposta.text
    assert 'id="dados-grafico"' in resposta.text


def test_ipca_anual_nao_e_rotulado_como_mensal_no_historico(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-11-23")
    assert '<h2 id="titulo-historico">IPCA</h2>' in resposta.text


def test_csv_exporta_todo_recorte_nao_pagina_tabela(ambiente):
    cliente, servico = ambiente
    resposta = cliente.get(
        "/exportar.csv?codigo=432&de=2026-01-01&ate=2026-01-31&pagina=2"
    )
    assert resposta.status_code == 200
    assert "attachment" in resposta.headers["content-disposition"]
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    linhas = list(
        csv.DictReader(io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";")
    )
    assert len(linhas) == 31
    assert linhas[0]["valor"] == "1.000000"
    assert linhas[-1]["referencia"] == "2026-01-31"
    assert linhas[0]["fonte"]
    servico.obter_historico.assert_called_once()


def test_csv_null_e_parcial_nao_viram_zero(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get(
        "/exportar.csv?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-11-23"
    )
    linhas = list(
        csv.DictReader(io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";")
    )
    assert linhas[0]["valor"] == ""
    assert linhas[0]["parcial"] == "sim"
    assert linhas[0]["completo"] == "nao"
    assert linhas[0]["motivo"] == "PERIODO_EM_ANDAMENTO"


def test_csv_recusa_paginacao_incompleta(ambiente):
    cliente, servico = ambiente
    servico.obter_historico.return_value = (
        servico.obter_historico.return_value.model_copy(
            update={"consulta_completa": False}
        )
    )
    resposta = cliente.get("/exportar.csv?codigo=432&de=2026-01-01&ate=2026-01-31")
    assert resposta.status_code == 409
    assert "attachment" not in resposta.headers


def test_atualizacao_exige_csrf_origem_e_limita_frequencia(ambiente):
    cliente, servico = ambiente
    cliente.get("/")
    token = cliente.cookies["csrf_painel"]
    dados = {
        "csrf": token,
        "codigo": "432",
        "de": "2026-01-01",
        "ate": "2026-01-31",
        "visualizacao": "mes",
    }
    rota = "/atualizar"
    assert (
        cliente.post(
            rota,
            content=urlencode(dados),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "http://outro",
            },
        ).status_code
        == 403
    )
    servico.renovar.assert_not_called()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "http://testserver",
    }
    resposta = cliente.post(
        rota, content=urlencode(dados), headers=headers, follow_redirects=False
    )
    assert resposta.status_code == 303
    assert "visualizacao=mes" in resposta.headers["location"]
    servico.renovar.assert_called_once_with(
        432, date(2026, 1, 1), date(2026, 1, 31), "mes"
    )
    assert (
        cliente.post(rota, content=urlencode(dados), headers=headers).status_code == 429
    )


def test_get_atualizacao_nao_altera_cache(ambiente):
    cliente, servico = ambiente
    assert cliente.get("/atualizar").status_code == 405
    servico.renovar.assert_not_called()


def test_post_invalido_nao_invalida_nem_consome_reserva(ambiente):
    cliente, servico = ambiente
    cliente.get("/")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "http://testserver",
    }
    dados = {
        "csrf": cliente.cookies["csrf_painel"],
        "codigo": "432",
        "de": "2099-01-01",
        "ate": "2099-01-02",
    }
    assert (
        cliente.post(
            "/atualizar", content=urlencode(dados), headers=headers
        ).status_code
        == 422
    )
    servico.renovar.assert_not_called()
    dados.update(de="2026-01-01", ate="2026-01-31")
    assert (
        cliente.post(
            "/atualizar",
            content=urlencode({**dados, "csrf": "forjado"}),
            headers=headers,
        ).status_code
        == 403
    )
    servico.renovar.assert_not_called()
    assert (
        cliente.post(
            "/atualizar",
            content=urlencode(dados),
            headers=headers,
            follow_redirects=False,
        ).status_code
        == 303
    )


def test_csv_falha_controlada_nao_vira_download(ambiente):
    from painel_indicadores.cliente_api import ErroDeConsulta

    cliente, servico = ambiente
    servico.obter_historico.side_effect = ErroDeConsulta(
        "Histórico temporariamente indisponível"
    )
    resposta = cliente.get("/exportar.csv")
    assert resposta.status_code == 503
    assert "attachment" not in resposta.headers


def test_historico_global_parcial_permite_consulta_do_recorte_sem_inventar_card(
    ambiente,
):
    cliente, servico = ambiente
    panorama = servico.obter_contexto.return_value
    parcial = panorama.historicos[432].model_copy(
        update={"consulta_completa": False, "motivo": "LIMITE_PAGINAS"}
    )
    servico.obter_contexto.return_value = panorama.model_copy(
        update={
            "historicos": {**panorama.historicos, 432: parcial},
            "cards": tuple(
                criar_card(codigo, parcial if codigo == 432 else dados, HOJE)
                for codigo, dados in panorama.historicos.items()
            ),
        }
    )
    resposta = cliente.get("/?codigo=432&de=2026-01-01&ate=2026-01-31")
    servico.obter_historico.assert_called_once()
    assert "Acervo incompleto para determinar o último dado global" in resposta.text
    assert 'id="dados-grafico"' in resposta.text
