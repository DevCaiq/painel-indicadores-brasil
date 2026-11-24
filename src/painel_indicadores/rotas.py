"""Páginas, downloads e renovação seletiva de dados públicos."""

from datetime import UTC, date, datetime
from math import ceil
from pathlib import Path
from time import monotonic
from typing import Annotated, cast
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from painel_indicadores.cliente_api import ErroDeConsulta
from painel_indicadores.contratos import (
    ConjuntoAgregados,
    ConjuntoObservacoes,
    hoje_brasil,
)
from painel_indicadores.dados_exportacao import exportar_conjunto
from painel_indicadores.formatacao import formatar_decimal, motivo_legivel
from painel_indicadores.indicadores import SERIES, ServicoIndicadores
from painel_indicadores.pagina import montar_pagina, resolver_filtros
from painel_indicadores.seguranca import ErroDeAtualizacao, ProtecaoAtualizacao

roteador = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["decimal_br"] = formatar_decimal
templates.env.filters["motivo_br"] = motivo_legivel


def formatar_data(valor: date | datetime | None) -> str:
    if valor is None:
        return "Não informado"
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            return "Horário sem fuso informado"
        return (
            valor.astimezone(ZoneInfo("America/Sao_Paulo")).strftime(
                "%d/%m/%Y às %H:%M"
            )
            + " · Brasília"
        )
    return valor.strftime("%d/%m/%Y")


templates.env.filters["data_br"] = formatar_data


def obter_servico(requisicao: Request) -> ServicoIndicadores:
    return cast(ServicoIndicadores, requisicao.app.state.indicadores)


def _tipo_data(valor: str) -> str:
    try:
        return "date" if date.fromisoformat(valor).isoformat() == valor else "text"
    except ValueError:
        return "text"


def _erro(requisicao: Request, status: int, mensagem: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=requisicao,
        name="erro.html",
        context={"mensagem": mensagem, "codigo_erro": status},
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


@roteador.get("/", response_class=HTMLResponse)
def painel(
    requisicao: Request, servico: Annotated[ServicoIndicadores, Depends(obter_servico)]
) -> HTMLResponse:
    hoje = hoje_brasil()
    parametros = dict(requisicao.query_params)
    padrao = resolver_filtros({}, hoje)
    valores = {
        "codigo": parametros.get("codigo", str(padrao.codigo))[:128],
        "de": parametros.get("de", padrao.de.isoformat())[:128],
        "ate": parametros.get("ate", hoje.isoformat())[:128],
        "visualizacao": parametros.get("visualizacao", "observacoes")[:32],
    }
    pagina = None
    erro = None
    erros_campos: dict[str, str] = {}
    status = 200
    status_api = None
    configuracao = requisicao.app.state.configuracao
    fim = monotonic() + configuracao.prazo_consulta_segundos
    try:
        filtros = resolver_filtros(parametros, hoje)
    except ValueError as falha:
        erros_campos = getattr(falha, "campos", {})
        erro = "Use uma série e visualização disponíveis e datas válidas entre 01/01/2020 e hoje, com início anterior ou igual ao fim."
        status = 422
    else:
        valores = {
            "codigo": str(filtros.codigo),
            "de": filtros.de.isoformat(),
            "ate": filtros.ate.isoformat(),
            "visualizacao": filtros.visualizacao,
        }
        panorama = servico.obter_contexto(hoje)
        avisos = []
        global_selecionado = panorama.historicos.get(filtros.codigo)
        if (
            filtros.visualizacao == "observacoes"
            and global_selecionado is not None
            and not global_selecionado.consulta_completa
            and (
                global_selecionado.meta.de != filtros.de
                or global_selecionado.meta.ate != filtros.ate
            )
        ):
            try:
                recorte = servico.obter_historico(
                    filtros.codigo,
                    filtros.de,
                    filtros.ate,
                    prazo_consulta=max(0, fim - monotonic()),
                )
                # O card continua indisponível: completar um filtro não completa o acervo global.
                panorama = panorama.model_copy(
                    update={
                        "historicos": {**panorama.historicos, filtros.codigo: recorte}
                    }
                )
            except ErroDeConsulta as falha:
                avisos.append(str(falha))
        gold = None
        if filtros.visualizacao != "observacoes":
            try:
                gold = servico.obter_gold(
                    filtros.codigo,
                    filtros.de,
                    filtros.ate,
                    filtros.visualizacao,
                    prazo_consulta=max(0, fim - monotonic()),
                )
            except ErroDeConsulta as falha:
                avisos.append(str(falha))
        ipca = None
        try:
            ipca = servico.obter_ipca_12m(
                date(2020, 1, 1), hoje, prazo_consulta=max(0, fim - monotonic())
            )
        except ErroDeConsulta as falha:
            avisos.append("IPCA em 12 meses: " + str(falha))
        frescor = None
        try:
            frescor = servico.obter_frescor(prazo_consulta=max(0, fim - monotonic()))
        except ErroDeConsulta as falha:
            avisos.append("Atualização da fonte desconhecida. " + str(falha))
        pagina = montar_pagina(
            filtros,
            panorama,
            gold=gold,
            ipca_12m=ipca,
            frescor=frescor,
            avisos_extras=avisos,
        )
        status_api = servico.verificar_processo()
    protecao = cast(ProtecaoAtualizacao, requisicao.app.state.protecao_atualizacao)
    token = requisicao.cookies.get("csrf_painel")
    partes = urlsplit(str(requisicao.url))
    origem = f"{partes.scheme}://{partes.netloc}"
    try:
        protecao.validar(token or "", token, origem, origem)
    except ErroDeAtualizacao:
        token = protecao.emitir_token()
    resposta = templates.TemplateResponse(
        request=requisicao,
        name="painel.html",
        context={
            "p": pagina,
            "status_api": status_api,
            "valores": valores,
            "erro_filtro": erro,
            "erros_campos": erros_campos,
            "tipos_datas": {
                campo: _tipo_data(valores[campo]) for campo in ("de", "ate")
            },
            "series": SERIES,
            "hoje": hoje.isoformat(),
            "gerada_em": formatar_data(datetime.now(UTC)),
            "ano": hoje.year,
            "validade_cache": configuracao.validade_cache_segundos,
            "csrf": token,
        },
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )
    resposta.set_cookie(
        "csrf_painel",
        token or "",
        max_age=7200,
        httponly=True,
        secure=requisicao.url.scheme == "https",
        samesite="strict",
    )
    return resposta


@roteador.get("/exportar.csv")
def exportar(
    requisicao: Request, servico: Annotated[ServicoIndicadores, Depends(obter_servico)]
) -> Response:
    try:
        filtros = resolver_filtros(dict(requisicao.query_params), hoje_brasil())
        tipo = requisicao.query_params.get("tipo", "historico")
        if tipo not in ("historico", "ipca12m"):
            raise ValueError("Tipo de exportação inválido.")
        codigo = 433 if tipo == "ipca12m" else filtros.codigo
        conjunto: ConjuntoAgregados | ConjuntoObservacoes
        if tipo == "ipca12m":
            conjunto = servico.obter_ipca_12m(filtros.de, filtros.ate)
            modo = "ipca12m"
        elif filtros.visualizacao == "observacoes":
            conjunto = servico.obter_historico(codigo, filtros.de, filtros.ate)
            modo = filtros.visualizacao
        else:
            conjunto = servico.obter_gold(
                codigo, filtros.de, filtros.ate, filtros.visualizacao
            )
            modo = filtros.visualizacao
        if not conjunto.consulta_completa:
            return _erro(
                requisicao,
                409,
                "Consulta incompleta; reduza o período antes de exportar.",
            )
        conteudo = exportar_conjunto(codigo, conjunto, modo)
    except ValueError:
        return _erro(requisicao, 422, "Revise os filtros antes de exportar.")
    except ErroDeConsulta as falha:
        return _erro(requisicao, 503, str(falha))
    nome = f"indicadores-{codigo}-{modo}-{filtros.de}-{filtros.ate}.csv"
    return Response(
        conteudo,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@roteador.post("/atualizar")
async def atualizar(
    requisicao: Request, servico: Annotated[ServicoIndicadores, Depends(obter_servico)]
) -> Response:
    if (
        requisicao.headers.get("content-type", "").split(";")[0]
        != "application/x-www-form-urlencoded"
    ):
        return _erro(requisicao, 415, "Envie a atualização pelo formulário do painel.")
    corpo = bytearray()
    async for bloco in requisicao.stream():
        corpo.extend(bloco)
        if len(corpo) > 4096:
            return _erro(requisicao, 413, "Formulário excedeu o limite permitido.")
    try:
        campos = parse_qs(
            corpo.decode("utf-8"),
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=12,
        )
        if any(len(valores) != 1 for valores in campos.values()) or set(campos) - {
            "csrf",
            "codigo",
            "de",
            "ate",
            "visualizacao",
        }:
            raise ValueError("Campos inválidos.")
        dados = {campo: valores[0] for campo, valores in campos.items()}
        protecao = cast(ProtecaoAtualizacao, requisicao.app.state.protecao_atualizacao)
        partes = urlsplit(str(requisicao.url))
        protecao.validar(
            dados.get("csrf", ""),
            requisicao.cookies.get("csrf_painel"),
            requisicao.headers.get("origin"),
            f"{partes.scheme}://{partes.netloc}",
        )
        filtros = resolver_filtros(dados, hoje_brasil())
        protecao.reservar("painel")
        await run_in_threadpool(
            servico.renovar,
            filtros.codigo,
            filtros.de,
            filtros.ate,
            filtros.visualizacao,
        )
    except ErroDeAtualizacao as falha:
        resposta = _erro(requisicao, falha.status, falha.mensagem)
        if falha.status == 429:
            resposta.headers["Retry-After"] = str(
                ceil(requisicao.app.state.configuracao.intervalo_atualizacao_segundos)
            )
        return resposta
    except ValueError:
        return _erro(requisicao, 422, "Revise os filtros antes de atualizar.")
    destino = "/?" + urlencode(
        {
            "codigo": filtros.codigo,
            "de": filtros.de.isoformat(),
            "ate": filtros.ate.isoformat(),
            "visualizacao": filtros.visualizacao,
        }
    )
    return RedirectResponse(destino, status_code=303)
