"""Servidor da aplicação real com produtor sintético inteiramente offline."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import httpx
from fastapi import FastAPI, Request
from starlette.responses import Response

from painel_indicadores.aplicacao import criar_aplicacao
from painel_indicadores.cache import CacheHistoricos
from painel_indicadores.cliente_api import ClienteAPI
from painel_indicadores.indicadores import ServicoIndicadores
from painel_indicadores.rotas import obter_servico

AVISO = "Ambiente de testes: dados sintéticos, sem consulta às fontes."
UNIDADES = {432: "% a.a.", 1: "BRL/USD", 433: "% no mes"}


def responder_produtor(requisicao: httpx.Request) -> httpx.Response:
    """Rotas desconhecidas falham fechadas, sem qualquer transporte de rede."""
    assert requisicao.url.host == "produtor-sintetico.invalid"
    assert requisicao.method == "GET"
    rota = requisicao.url.path
    parametros = requisicao.url.params
    meta: dict[str, Any] = {
        "camada": "core",
        "versao_dados": 2,
        "versao_core": 2,
        "versao_gold": 1,
        "data_publicacao": "2026-01-01",
    }
    if rota == "/health":
        return httpx.Response(200, json={"situacao": "sintetico"})
    if rota == "/api/v1/pipeline/frescor":
        return httpx.Response(
            200,
            json={
                "meta": meta,
                "data": [
                    {
                        "codigo": codigo,
                        "unidade": unidade,
                        "cobertura": None,
                        "ultima_consulta": "2026-01-01T00:30:00Z",
                        "ultima_publicacao": "2026-01-01T00:30:00Z",
                        "ultima_referencia": "2026-01-01",
                        "defasado": None if codigo == 433 else False,
                        "politica": "AMOSTRA_SINTETICA",
                        "calendario_homologado": False,
                        "motivo": "SEM_CALENDARIO" if codigo == 433 else None,
                    }
                    for codigo, unidade in UNIDADES.items()
                ],
            },
        )
    partes = rota.split("/")
    indicador = rota == "/api/v1/indicadores/ipca-12m"
    if not indicador and not (
        len(partes) == 6 and partes[1:4] == ["api", "v1", "series"]
    ):
        raise AssertionError(f"Rota não prevista: {rota}")
    codigo = 433 if indicador else int(partes[4])
    unidade = UNIDADES[codigo]
    gold = indicador or partes[-1] == "agregados"
    registros: list[dict[str, Any]]
    if not gold:
        if codigo == 433:
            registros = [
                {"data": f"2026-{mes:02d}-01", "valor": valor}
                for mes, valor in enumerate(("0.000000", "-0.120000", "0.500000"), 1)
            ]
        else:
            base = Decimal("14.000000" if codigo == 432 else "5.000000")
            registros = [
                {
                    "data": f"2026-01-{dia:02d}",
                    "valor": format(base + Decimal(dia) / Decimal(1000000), ".6f"),
                }
                for dia in range(1, 32)
            ]
        campo_data = "data"
    else:
        anual = parametros.get("granularidade") == "ano"
        if codigo == 433:
            unidade = (
                "% no periodo" if indicador else "% no ano" if anual else "% no mes"
            )
        valores: tuple[str | None, ...]
        if indicador:
            valores = ("4.000000", None, "4.500000")
        elif codigo == 433:
            valores = ("0.000000", "-0.120000", None)
        else:
            valores = (
                ("14.000000", "14.100000", "14.200000")
                if codigo == 432
                else ("5.000000", "5.100000", "5.200000")
            )
        if anual:
            valores = (None,) if codigo == 433 else (valores[-1],)
        registros = []
        for mes, valor in enumerate(valores, 1):
            parcial = valor is None or anual
            registros.append(
                {
                    "periodo": f"2026-{mes:02d}-01",
                    "unidade": unidade,
                    "observacoes": 1,
                    "ultimo": valor if codigo != 433 else None,
                    "variacao": valor if codigo == 433 else None,
                    "completo": not parcial,
                    "parcial": parcial,
                    "motivo": "PERIODO_EM_ANDAMENTO" if parcial else None,
                    "data_referencia": f"2026-{mes:02d}-01",
                }
            )
        campo_data = "periodo"
        meta.update(
            camada="gold", versao_dados=1, desatualizado=True, motivo="CORE_NOVO"
        )
    de = parametros.get("de", "2020-01-01")
    ate = parametros.get("ate", "2026-12-31")
    registros = [item for item in registros if de <= item[campo_data] <= ate]
    limite = int(parametros.get("limite", "1000"))
    inicio = int(parametros.get("cursor", "0"))
    proximo = inicio + limite
    tem_mais = proximo < len(registros)
    meta.update(codigo=codigo, unidade=unidade, de=de, ate=ate)
    return httpx.Response(
        200,
        json={
            "data": registros[inicio:proximo],
            "meta": meta,
            "pagina": {
                "limite": limite,
                "tem_mais": tem_mais,
                "proximo_cursor": str(proximo) if tem_mais else None,
            },
        },
    )


def criar_aplicacao_teste() -> FastAPI:
    """Preserva rotas e assets reais e fecha o MockTransport ao encerrar."""
    aplicacao = criar_aplicacao()
    cliente = httpx.Client(
        base_url="http://produtor-sintetico.invalid",
        transport=httpx.MockTransport(responder_produtor),
        trust_env=False,
    )
    servico = ServicoIndicadores(ClienteAPI(cliente), CacheHistoricos())
    aplicacao.state.cliente_sintetico = cliente
    aplicacao.dependency_overrides[obter_servico] = lambda: servico

    @asynccontextmanager
    async def ciclo_sintetico(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            cliente.close()

    aplicacao.router.lifespan_context = ciclo_sintetico

    @aplicacao.middleware("http")
    async def identificar_amostra(requisicao: Request, proxima: Any) -> Response:
        resposta = await proxima(requisicao)
        resposta.headers["X-Dados-Teste"] = "sinteticos"
        if "text/html" not in resposta.headers.get("content-type", ""):
            return resposta  # type: ignore[no-any-return]
        corpo = b"".join([bloco async for bloco in resposta.body_iterator])
        aviso = (
            f'<aside role="status" aria-label="Ambiente de testes" '
            f'style="padding:12px;background:#fff3cd;color:#332701">{AVISO}</aside>'
        ).encode()
        posicao = corpo.find(b">", corpo.find(b"<body")) + 1
        corpo = corpo[:posicao] + aviso + corpo[posicao:]
        cabecalhos = dict(resposta.headers)
        cabecalhos.pop("content-length", None)
        return Response(
            corpo,
            status_code=resposta.status_code,
            headers=cabecalhos,
            background=resposta.background,
        )

    return aplicacao
