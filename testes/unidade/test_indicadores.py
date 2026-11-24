"""Regras de apresentação usando conjuntos sintéticos de teste."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import httpx
import pytest

from painel_indicadores.cache import CacheHistoricos
from painel_indicadores.cliente_api import ClienteAPI, ErroDeConsulta
from painel_indicadores.contratos import ConjuntoObservacoes
from painel_indicadores.formatacao import formatar_decimal
from painel_indicadores.indicadores import (
    ServicoIndicadores,
    calcular_metricas,
    criar_card,
)


def conjunto(codigo=433, completa=True, dados=None):
    return ConjuntoObservacoes.model_validate(
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
                "unidade": "% no mes",
                "de": "2020-01-01",
                "ate": "2026-11-23",
            },
            "consulta_completa": completa,
            "motivo": None if completa else "Teste de limite",
        }
    )


def test_ultimo_global_independente_das_metricas_filtradas():
    dados = conjunto()
    card = criar_card(433, dados, date(2026, 11, 23))
    metricas = calcular_metricas(dados, date(2026, 1, 1), date(2026, 2, 1))
    assert card.valor == Decimal("0.5")
    assert card.referencia == date(2026, 3, 1)
    assert card.diferenca == Decimal("0.62")
    assert card.unidade_diferenca == "p.p."
    assert card.referencia_anterior == date(2026, 2, 1)
    assert metricas.ultimo == Decimal("-0.12")
    assert metricas.primeiro == Decimal(0)
    assert metricas.minimo == Decimal("-0.12")
    assert metricas.maximo == Decimal(0)
    assert metricas.observacoes == 2


@pytest.mark.parametrize(
    "dados",
    [
        conjunto(completa=False),
        conjunto(dados=[]),
        conjunto().model_copy(
            update={"meta": conjunto().meta.model_copy(update={"de": date(2026, 1, 1)})}
        ),
    ],
)
def test_nao_apresenta_ultimo_parcial_como_global(dados):
    card = criar_card(433, dados, date(2026, 11, 23))
    assert card.valor is None
    assert card.aviso


def test_dolar_sem_ontem_inventado():
    dados = conjunto(
        1,
        dados=[
            {"data": "2026-01-02", "valor": "5.000000"},
            {"data": "2026-01-05", "valor": "5.100000"},
        ],
    )
    card = criar_card(1, dados, date(2026, 11, 23))
    assert card.diferenca == Decimal("0.1")
    assert card.unidade_diferenca == "R$"
    assert card.referencia_anterior == date(2026, 1, 2)


def test_metricas_vazias_nao_viram_zero():
    metricas = calcular_metricas(conjunto(), date(2026, 7, 1), date(2026, 7, 2))
    assert metricas.observacoes == 0
    assert metricas.minimo is None
    assert metricas.ultimo is None


@pytest.mark.parametrize(
    "valor,esperado",
    [
        (Decimal("1234.56"), "1.234,56"),
        (Decimal("-0.12"), "-0,12"),
        (Decimal(0), "0,00"),
        (None, "Indisponível"),
    ],
)
def test_formatacao_pt_br(valor, esperado):
    assert formatar_decimal(valor) == esperado


def test_cache_expira_e_isola_chaves():
    instante = [0.0]
    cache = CacheHistoricos(validade=300, relogio=lambda: instante[0])
    chamadas = []

    def carregar():
        chamadas.append(1)
        return conjunto()

    cache.obter("servidor-a", carregar)
    cache.obter("servidor-a", carregar)
    cache.obter("servidor-b", carregar)
    assert len(chamadas) == 2
    instante[0] = 300
    cache.obter("servidor-a", carregar)
    assert len(chamadas) == 3


def test_cache_nao_compartilha_objetos_mutaveis():
    cache = CacheHistoricos()
    resultado = cache.obter("a", conjunto)
    resultado.meta.__dict__["unidade"] = "adulterado"
    assert cache.obter("a", conjunto).meta.unidade != "adulterado"


def test_cache_nao_armazena_erro_ou_parcial():
    cache = CacheHistoricos()
    chamadas = []

    def carregar():
        chamadas.append(1)
        raise ErroDeConsulta("falha")

    for _ in range(2):
        with pytest.raises(ErroDeConsulta):
            cache.obter("erro", carregar)
    assert len(chamadas) == 2
    cache.obter("parcial", lambda: conjunto(completa=False))
    assert cache.obter("parcial", conjunto).consulta_completa


def test_cache_limita_entradas_e_bytes():
    chamadas = []

    def carregar():
        chamadas.append(1)
        return conjunto()

    cache = CacheHistoricos(maximo_entradas=1)
    for chave in ("a", "b", "a"):
        cache.obter(chave, carregar)
    assert len(chamadas) == 3
    cache = CacheHistoricos(maximo_bytes=1)
    cache.obter("a", carregar)
    cache.obter("a", carregar)
    assert len(chamadas) == 5


def test_cache_concorrente_carrega_uma_vez():
    cache = CacheHistoricos()
    barreira = Barrier(4)
    chamadas = []

    def carregar():
        chamadas.append(1)
        return conjunto()

    def consultar(_):
        barreira.wait(timeout=5)
        return cache.obter("mesma-chave", carregar)

    with ThreadPoolExecutor(max_workers=4) as executor:
        resultados = list(executor.map(consultar, range(4)))
    assert len(resultados) == 4
    assert len(chamadas) == 1


def test_panorama_isola_falha_e_reutiliza_historico():
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        codigo = int(pedido.url.path.split("/")[4])
        if codigo == 433:
            return httpx.Response(404)
        dados = conjunto(codigo).model_dump(mode="json")
        return httpx.Response(
            200,
            json={
                "data": dados["observacoes"],
                "meta": dados["meta"],
                "pagina": {"limite": 1000, "tem_mais": False, "proximo_cursor": None},
            },
        )

    with httpx.Client(
        base_url="http://api", transport=httpx.MockTransport(responder)
    ) as http:
        servico = ServicoIndicadores(ClienteAPI(http), CacheHistoricos())
        cards = servico.obter_panorama(date(2026, 11, 23))
        servico.obter_historico(432, date(2020, 1, 1), date(2026, 11, 23))
    assert [card.codigo for card in cards] == [432, 433, 1]
    assert cards[0].valor == Decimal("0.5")
    assert cards[1].valor is None
    assert cards[2].valor == Decimal("0.5")
    assert len(pedidos) == 3


def test_card_preserva_cobertura_incompleta_da_fonte():
    from painel_indicadores.contratos import Cobertura

    dados = conjunto()
    dados = dados.model_copy(
        update={
            "meta": dados.meta.model_copy(
                update={
                    "cobertura": Cobertura(
                        inicio=date(2020, 1, 1),
                        fim=date(2026, 3, 1),
                        observacoes=3,
                        unidade_contagem="observacoes",
                        completa=False,
                        motivo="LACUNAS_CONHECIDAS",
                    )
                }
            )
        }
    )
    card = criar_card(433, dados, date(2026, 11, 23))
    assert card.valor == Decimal("0.5")
    assert card.cobertura.completa is False
    assert card.aviso


def test_panorama_nao_multiplica_prazo_pelas_tres_series():
    instante = [0.0]
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        instante[0] += 31
        return httpx.Response(404)

    with httpx.Client(
        base_url="http://api", transport=httpx.MockTransport(responder)
    ) as http:
        servico = ServicoIndicadores(
            ClienteAPI(http), CacheHistoricos(), relogio=lambda: instante[0]
        )
        cards = servico.obter_panorama(date(2026, 11, 23))
    assert len(pedidos) == 1
    assert len(cards) == 3
    assert all(card.aviso for card in cards)
