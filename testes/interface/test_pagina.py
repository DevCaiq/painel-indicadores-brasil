"""Dados sintéticos restritos aos testes offline de apresentação."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from painel_indicadores.aplicacao import criar_aplicacao
from painel_indicadores.contratos import ConjuntoObservacoes
from painel_indicadores.graficos import criar_grafico
from painel_indicadores.indicadores import PanoramaIndicadores, criar_card
from painel_indicadores.pagina import resolver_filtros, subtrair_meses
from painel_indicadores.rotas import obter_servico

HOJE = date(2026, 11, 23)


def contexto(dados=None, parcial=False):
    historicos = {}
    for codigo, unidade in [(432, "% a.a."), (433, "% no mes"), (1, "BRL/USD")]:
        historicos[codigo] = ConjuntoObservacoes.model_validate(
            {
                "observacoes": dados
                if dados is not None
                else [
                    {"data": "2026-01-01", "valor": "0.000000"},
                    {"data": "2026-02-01", "valor": "-0.120000"},
                    {"data": "2026-03-01", "valor": "0.500000"},
                ],
                "meta": {
                    "camada": "core",
                    "versao_dados": 1,
                    "versao_core": 1,
                    "versao_gold": 1,
                    "codigo": codigo,
                    "unidade": unidade,
                    "de": "2020-01-01",
                    "ate": HOJE.isoformat(),
                },
                "consulta_completa": not parcial,
                "motivo": "Limite sintético de teste" if parcial else None,
            }
        )
    return PanoramaIndicadores(
        cards=tuple(
            criar_card(codigo, conjunto, HOJE)
            for codigo, conjunto in historicos.items()
        ),
        historicos=historicos,
    )


@pytest.fixture
def cliente():
    servico = Mock()
    servico.obter_contexto.return_value = contexto()
    servico.obter_ipca_12m.return_value = None
    servico.obter_frescor.return_value = None
    servico.obter_gold.return_value = None
    servico.verificar_processo.return_value = True
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_servico] = lambda: servico
    with TestClient(aplicacao) as http:
        yield http, servico


def test_calendario_e_padrao():
    assert subtrair_meses(date(2024, 5, 31), 3) == date(2024, 2, 29)
    filtros = resolver_filtros({}, HOJE)
    assert filtros.codigo == 432
    assert filtros.de == date(2025, 11, 23)
    assert filtros.ate == HOJE
    assert resolver_filtros({"periodo": "tudo", "codigo": "433"}, HOJE).de == date(
        2020, 1, 1
    )


def test_pagina_renderiza_cards_e_grafico_local(cliente):
    http, servico = cliente
    resposta = http.get("/?codigo=433&de=2026-01-01&ate=2026-02-01")
    assert resposta.status_code == 200
    assert '<html lang="pt-BR">' in resposta.text
    assert "Indicadores do Brasil" in resposta.text
    assert "0,50" in resposta.text  # último global
    assert "-0,12" in resposta.text  # último filtrado
    assert "Último dado disponível" in resposta.text
    assert "/estaticos/vendor/plotly.min.js" in resposta.text
    assert 'id="dados-grafico"' in resposta.text
    assert 'type="application/json"' in resposta.text
    assert 'name="de"' in resposta.text
    assert "/exportar.csv?" in resposta.text
    servico.obter_contexto.assert_called_once()


@pytest.mark.parametrize(
    "consulta",
    [
        "codigo=999",
        "de=2026-03-01&ate=2026-01-01",
        "de=2019-01-01",
        "ate=2099-01-01",
        "de=2026-01-01T00:00:00",
        "pagina=0",
        "periodo=inexistente",
    ],
)
def test_filtros_invalidos_retornam_html_sem_consulta(cliente, consulta):
    http, servico = cliente
    resposta = http.get("/?" + consulta)
    assert resposta.status_code == 422
    assert "text/html" in resposta.headers["content-type"]
    assert "Revise os filtros" in resposta.text
    servico.obter_contexto.assert_not_called()


def test_preserva_filtros_e_escapa_texto_invalido(cliente):
    http, _ = cliente
    resposta = http.get(
        "/",
        params={
            "de": "<script>alert(1)</script>",
            "ate": "2026-03-01",
            "codigo": "433",
        },
    )
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text
    assert 'value="2026-03-01"' in resposta.text


def test_vazio_sem_zero_fabricado(cliente):
    http, servico = cliente
    servico.obter_contexto.return_value = contexto(dados=[])
    resposta = http.get("/")
    assert "Não há dados para o período" in resposta.text
    assert "Indisponível" in resposta.text
    assert 'id="dados-grafico"' not in resposta.text


def test_falha_em_uma_serie_preserva_as_demais(cliente):
    http, servico = cliente
    dados = contexto()
    dados.historicos.pop(433)
    cards = tuple(
        card.model_copy(
            update={"valor": None, "aviso": "Consulta temporariamente indisponível"}
        )
        if card.codigo == 433
        else card
        for card in dados.cards
    )
    servico.obter_contexto.return_value = dados.model_copy(update={"cards": cards})
    resposta = http.get("/?codigo=433")
    assert resposta.status_code == 200
    assert "Consulta temporariamente indisponível" in resposta.text
    assert "0,50" in resposta.text
    assert 'id="dados-grafico"' not in resposta.text


def test_incompletude_visivel_e_tabela_paginada(cliente):
    from painel_indicadores.cliente_api import ErroDeConsulta

    http, servico = cliente
    servico.obter_historico.side_effect = ErroDeConsulta(
        "Recorte indisponível no teste"
    )
    dados = [
        {"data": f"2026-01-{dia:02d}", "valor": "1.000000"} for dia in range(1, 32)
    ]
    servico.obter_contexto.return_value = contexto(dados=dados, parcial=True)
    resposta = http.get("/?de=2026-01-01&ate=2026-01-31&pagina=2")
    assert "Consulta incompleta" in resposta.text
    assert "26–31 de 31" in resposta.text
    assert 'aria-current="page"' in resposta.text
    assert 'id="dados-grafico"' in resposta.text


def test_graficos_preservam_tipos_sinais_e_datas():
    historicos = contexto().historicos
    selic = criar_grafico(432, historicos[432].observacoes)
    ipca = criar_grafico(433, historicos[433].observacoes)
    dolar = criar_grafico(1, historicos[1].observacoes)
    assert selic["data"][0]["line"]["shape"] == "hv"
    assert ipca["data"][0]["type"] == "bar"
    assert ipca["data"][0]["y"][1] == float(Decimal("-0.12"))
    assert ipca["layout"]["yaxis"]["rangemode"] == "tozero"
    assert len(dolar["data"][0]["x"]) == 3
    assert dolar["data"][0]["connectgaps"] is False
    assert json.loads(json.dumps(ipca))["data"][0]["x"][0] == "2026-01-01"


def test_resumo_do_dolar_preserva_quatro_casas(cliente):
    http, servico = cliente
    servico.obter_contexto.return_value = contexto(
        dados=[{"data": "2026-03-01", "valor": "5.123400"}]
    )
    resposta = http.get("/?codigo=1&de=2026-03-01&ate=2026-03-01")
    assert "Primeiro valor: 5,1234 R$/US$; último: 5,1234 R$/US$" in resposta.text


def test_exibe_duracao_real_do_cache(cliente):
    http, _ = cliente
    http.app.state.configuracao.validade_cache_segundos = 60
    resposta = http.get("/")
    assert "Cache de até 60 segundos" in resposta.text


def test_api_indisponivel_nao_apaga_dados_validos_do_cache(cliente):
    http, servico = cliente
    servico.verificar_processo.return_value = False
    resposta = http.get("/")
    assert "API indisponível" in resposta.text
    assert "0,50" in resposta.text
    assert 'id="dados-grafico"' in resposta.text
