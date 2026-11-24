"""Factory do painel e ciclo de vida do cliente HTTP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from painel_indicadores.cache import CacheHistoricos
from painel_indicadores.cliente_api import ClienteAPI
from painel_indicadores.configuracao import ConfiguracaoPainel
from painel_indicadores.indicadores import ServicoIndicadores
from painel_indicadores.rotas import roteador
from painel_indicadores.seguranca import ProtecaoAtualizacao


def criar_aplicacao() -> FastAPI:
    configuracao = ConfiguracaoPainel()

    @asynccontextmanager
    async def ciclo_de_vida(aplicacao: FastAPI) -> AsyncIterator[None]:
        with httpx.Client(
            base_url=str(configuracao.url_base_api),
            timeout=httpx.Timeout(
                configuracao.tempo_leitura_segundos,
                connect=configuracao.tempo_conexao_segundos,
            ),
            follow_redirects=False,
            trust_env=False,
        ) as cliente:
            aplicacao.state.cliente_api = ClienteAPI(
                cliente,
                prazo_consulta=configuracao.prazo_consulta_segundos,
                limite_paginas=configuracao.limite_paginas,
            )
            aplicacao.state.indicadores = ServicoIndicadores(
                aplicacao.state.cliente_api,
                CacheHistoricos(
                    validade=configuracao.validade_cache_segundos,
                    maximo_entradas=configuracao.limite_entradas_cache,
                    maximo_bytes=configuracao.limite_bytes_cache,
                ),
            )
            yield

    aplicacao = FastAPI(title="Indicadores do Brasil", lifespan=ciclo_de_vida)
    aplicacao.state.configuracao = configuracao
    aplicacao.state.protecao_atualizacao = ProtecaoAtualizacao(
        configuracao.intervalo_atualizacao_segundos
    )
    aplicacao.mount(
        "/estaticos",
        StaticFiles(directory=Path(__file__).parent / "estaticos", check_dir=False),
        name="estaticos",
    )
    aplicacao.include_router(roteador)

    @aplicacao.get("/health")
    def saude() -> dict[str, str]:
        return {"situacao": "ativo"}

    return aplicacao
