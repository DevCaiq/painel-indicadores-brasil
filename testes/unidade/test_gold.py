"""Amostras sintéticas de teste para gold, frescor e geração independente."""

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from painel_indicadores.cache import CacheHistoricos
from painel_indicadores.cliente_api import ClienteAPI, ErroDeConsulta
from painel_indicadores.contratos import Agregado, ConjuntoAgregados, Frescor
from painel_indicadores.indicadores import criar_card_ipca_12m, valor_agregado

DE = date(2026, 1, 1)
ATE = date(2026, 11, 23)


def item(periodo="2026-01-01", **alteracoes):
    return {
        "periodo": periodo,
        "unidade": "% no periodo",
        "observacoes": 12,
        "media": None,
        "minimo": None,
        "maximo": None,
        "ultimo": None,
        "variacao": "4.500000",
        "completo": True,
        "parcial": False,
        "motivo": None,
        "data_referencia": "2026-11-23",
        **alteracoes,
    }


def pagina(dados=None, cursor=None, versao=2, **alteracoes):
    return {
        "data": [item()] if dados is None else dados,
        "pagina": {"limite": 1000, "tem_mais": bool(cursor), "proximo_cursor": cursor},
        "meta": {
            "camada": "gold",
            "versao_dados": versao,
            "versao_core": 9,
            "versao_gold": versao,
            "codigo": 433,
            "unidade": "% no periodo",
            "data_publicacao": "2026-11-23",
            "desatualizado": False,
            "motivo": None,
            "de": str(DE),
            "ate": str(ATE),
            **alteracoes,
        },
    }


def consultar(respostas):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        resposta = respostas.pop(0)
        return (
            resposta
            if isinstance(resposta, httpx.Response)
            else httpx.Response(200, json=resposta)
        )

    http = httpx.Client(base_url="http://api", transport=httpx.MockTransport(responder))
    return http, ClienteAPI(http), pedidos


def conjunto(dados=None, **alteracoes):
    p = pagina(dados)
    return ConjuntoAgregados.model_validate(
        {
            "agregados": p["data"],
            "meta": p["meta"],
            "consulta_completa": True,
            **alteracoes,
        }
    )


def test_gold_usa_geracao_gold_e_preserva_stale():
    http, cliente, pedidos = consultar(
        [
            pagina(cursor="opaco", desatualizado=True, motivo="CORE_NOVO"),
            pagina([item("2026-02-01")], versao_core=10),
        ]
    )
    with http:
        dados = cliente.buscar_ipca_12m(DE, ATE)
    assert len(dados.agregados) == 2
    assert dados.meta.versao_gold == 2
    assert dados.meta.desatualizado
    assert dados.meta.motivo == "CORE_NOVO"
    assert pedidos[1].url.params["cursor"] == "opaco"
    assert dados.consultado_em.tzinfo == UTC


def test_gold_reinicia_conflito_sem_misturar():
    http, cliente, pedidos = consultar(
        [
            pagina(cursor="velho"),
            httpx.Response(409),
            pagina([item("2026-03-01")], versao=3),
        ]
    )
    with http:
        dados = cliente.buscar_ipca_12m(DE, ATE)
    assert len(dados.agregados) == 1
    assert dados.meta.versao_gold == 3
    assert "cursor" not in pedidos[-1].url.params


def test_agregados_preservam_granularidade():
    http, cliente, pedidos = consultar(
        [pagina([item(unidade="% no mes")], unidade="% no mes")]
    )
    with http:
        cliente.buscar_agregados(433, DE, ATE, "mes")
    assert pedidos[0].url.path.endswith("/433/agregados")
    assert pedidos[0].url.params["granularidade"] == "mes"


@pytest.mark.parametrize(
    "alteracoes", [{"completo": False}, {"parcial": True}, {"variacao": None}]
)
def test_ipca_invalido_vira_lacuna_e_card_sem_valor(alteracoes):
    dados = conjunto([item("2026-01-01"), item("2026-02-01", **alteracoes)])
    dados = dados.model_copy(
        update={"meta": dados.meta.model_copy(update={"de": date(2020, 1, 1)})}
    )
    card = criar_card_ipca_12m(dados, ATE)
    assert card.valor is None
    assert card.referencia == date(2026, 2, 1)
    assert card.aviso
    assert valor_agregado(433, dados.agregados[-1]) is None


def test_selic_dolar_ultimo_com_cobertura_desconhecida_nao_vira_inflacao():
    agregado = Agregado.model_validate(
        item(
            ultimo="13.750000",
            variacao=None,
            completo=None,
            motivo="CALENDARIO_NAO_HOMOLOGADO",
        )
    )
    assert valor_agregado(432, agregado) == Decimal("13.75")
    assert valor_agregado(433, agregado) is None


def test_cache_tipado_preserva_instante_e_invalida_so_chave_pedida():
    cache = CacheHistoricos()
    chamadas = []
    dados = conjunto(consultado_em=datetime(2026, 11, 23, tzinfo=UTC))

    def carregar():
        chamadas.append(1)
        return dados

    cache.obter_tipado("a", carregar, ConjuntoAgregados)
    cache.obter_tipado("b", carregar, ConjuntoAgregados)
    assert (
        cache.obter_tipado("a", carregar, ConjuntoAgregados).consultado_em
        == dados.consultado_em
    )
    cache.invalidar(["a"])
    cache.obter_tipado("b", carregar, ConjuntoAgregados)
    cache.obter_tipado("a", carregar, ConjuntoAgregados)
    assert len(chamadas) == 3


def test_renovar_preserva_outro_recorte_em_cache():
    from unittest.mock import Mock

    from painel_indicadores.contratos import ConjuntoObservacoes
    from painel_indicadores.indicadores import ServicoIndicadores

    cliente = Mock(servidor="http://api")

    def carregar(codigo, de, ate, **opcoes):
        return ConjuntoObservacoes.model_validate(
            {
                "observacoes": [],
                "meta": {
                    "camada": "core",
                    "versao_dados": 1,
                    "versao_core": 1,
                    "versao_gold": 1,
                    "codigo": codigo,
                    "unidade": "% a.a.",
                    "de": str(de),
                    "ate": str(ate),
                },
                "consulta_completa": True,
            }
        )

    cliente.buscar_observacoes.side_effect = carregar
    servico = ServicoIndicadores(cliente, CacheHistoricos())
    fim_a, fim_b = date(2026, 1, 31), date(2026, 2, 28)
    servico.obter_historico(432, DE, fim_a)
    servico.obter_historico(432, DE, fim_b)
    servico.renovar(432, DE, fim_a, "observacoes")
    servico.obter_historico(432, DE, fim_b)
    assert cliente.buscar_observacoes.call_count == 2
    servico.obter_historico(432, DE, fim_a)
    assert cliente.buscar_observacoes.call_count == 3


def frescor(**alteracoes):
    return {
        "codigo": 433,
        "unidade": "% no mes",
        "cobertura": None,
        "ultima_consulta": "2026-11-23T00:30:00Z",
        "ultima_referencia": "2026-10-01",
        "ultima_publicacao": "2026-11-23T01:00:00Z",
        "defasado": None,
        "politica": "TESTE",
        "calendario_homologado": False,
        "motivo": "DESCONHECIDO",
        **alteracoes,
    }


def test_frescor_nao_exige_envelope_paginado():
    p = pagina()
    http, cliente, _ = consultar([{"data": [frescor()], "meta": p["meta"]}])
    with http:
        resposta = cliente.buscar_frescor()
    assert resposta.data[0].defasado is None
    assert resposta.data[0].ultima_consulta.tzinfo == UTC


def test_frescor_timestamp_sem_fuso_e_rejeitado():
    with pytest.raises(ValidationError):
        Frescor.model_validate(frescor(ultima_consulta="2026-11-23T00:30:00"))


def test_gold_recusa_unidade_do_item_divergente():
    http, cliente, _ = consultar([pagina([item(unidade="R$/US$")])])
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_ipca_12m(DE, ATE)


def test_conflito_no_frescor_e_erro_controlado():
    http, cliente, _ = consultar([httpx.Response(409)])
    with http, pytest.raises(ErroDeConsulta):
        cliente.buscar_frescor()


@pytest.mark.parametrize(
    "nome,modelo",
    [
        ("agregados-ipca-ano.json", "PaginaAgregados"),
        ("agregados-selic-mes.json", "PaginaAgregados"),
        ("ipca-12m.json", "PaginaAgregados"),
        ("frescor.json", "RespostaFrescor"),
    ],
)
def test_amostras_reais_arquivadas_preservam_contrato_e_hash(nome, modelo):
    import hashlib
    import json
    from pathlib import Path

    from painel_indicadores import contratos

    caminho = Path(__file__).parents[1] / "amostras" / nome
    conteudo = caminho.read_bytes()
    origem = json.loads(
        caminho.with_name(nome + ".origem.json").read_text(encoding="utf-8")
    )
    assert hashlib.sha256(conteudo).hexdigest() == origem["sha256"]
    resposta = getattr(contratos, modelo).model_validate_json(conteudo)
    assert resposta.data
