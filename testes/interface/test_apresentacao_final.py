"""Regressões de legibilidade e acessibilidade da revisão P5."""

from html.parser import HTMLParser

# Reexporta a fixture intencionalmente para a descoberta do pytest.
from testes.interface.test_p4 import ambiente as ambiente  # noqa: PLC0414


class ElementosPorId(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elementos = {}

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if "id" in atributos:
            self.elementos[atributos["id"]] = atributos


def test_periodo_sem_valor_valido_preserva_tabela_sem_eixos_vazios(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-11-23")
    assert 'id="dados-grafico"' not in resposta.text
    assert "Não há valores completos" in resposta.text
    assert 'id="tabela"' in resposta.text
    assert "Indisponível % no ano" not in resposta.text


def test_erro_do_periodo_nao_marca_indicador_valido_como_invalido(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433&de=2026-03-01&ate=2026-01-01")
    elementos = ElementosPorId()
    elementos.feed(resposta.text)
    assert elementos.elementos["codigo"].get("aria-invalid") != "true"
    assert elementos.elementos["de"]["aria-describedby"] == "erro-de"
    assert elementos.elementos["ate"]["aria-describedby"] == "erro-ate"
    assert 'id="erro-de"' in resposta.text
    assert 'id="erro-ate"' in resposta.text


def test_visualizacao_invalida_tem_mensagem_junto_ao_campo(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?visualizacao=inexistente")
    elementos = ElementosPorId()
    elementos.feed(resposta.text)
    assert elementos.elementos["visualizacao"]["aria-invalid"] == "true"
    assert (
        elementos.elementos["visualizacao"]["aria-describedby"] == "erro-visualizacao"
    )
    assert "Escolha observações, agregado mensal ou agregado anual." in resposta.text


def test_motivo_tem_texto_compreensivel_na_tabela(ambiente):
    cliente, _ = ambiente
    resposta = cliente.get("/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-11-23")
    assert "Período em andamento" in resposta.text


def test_unidade_externa_nao_se_torna_html_no_grafico():
    from painel_indicadores.graficos import criar_grafico_linhas

    grafico = criar_grafico_linhas(432, (), '<img src="x" onerror="alert(1)">')
    assert "<img" not in grafico["data"][0]["hovertemplate"]
    assert "<img" not in grafico["layout"]["yaxis"]["title"]["text"]
