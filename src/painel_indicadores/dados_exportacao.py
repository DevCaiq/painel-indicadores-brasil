"""CSV do recorte completo, com proveniência e flags das linhas gold."""

from painel_indicadores.contratos import ConjuntoAgregados, ConjuntoObservacoes
from painel_indicadores.exportacao import CelulaCSV, gerar_csv
from painel_indicadores.indicadores import valor_agregado


def exportar_conjunto(
    codigo: int, conjunto: ConjuntoObservacoes | ConjuntoAgregados, visualizacao: str
) -> bytes:
    if not conjunto.consulta_completa:
        raise ValueError("Consulta incompleta; reduza o período antes de exportar.")
    meta = conjunto.meta
    fonte = "IBGE; distribuição BCB/SGS" if codigo == 433 else "BCB/SGS"
    colunas = (
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
        "versao_gold",
        "data_publicacao",
        "consulta_painel_utc",
        "filtro_de",
        "filtro_ate",
    )
    linhas: list[tuple[CelulaCSV, ...]] = []
    if isinstance(conjunto, ConjuntoObservacoes):
        for item in conjunto.observacoes:
            if meta.de <= item.data <= meta.ate:
                linhas.append(
                    (
                        codigo,
                        item.data,
                        item.valor,
                        meta.unidade,
                        fonte,
                        visualizacao,
                        item.data,
                        meta.cobertura.completa if meta.cobertura else None,
                        False,
                        meta.cobertura.motivo if meta.cobertura else None,
                        meta.desatualizado,
                        meta.versao_core,
                        meta.versao_gold,
                        meta.data_publicacao,
                        conjunto.consultado_em,
                        meta.de,
                        meta.ate,
                    )
                )
    else:
        for agregado in conjunto.agregados:
            if meta.de <= agregado.periodo <= meta.ate:
                linhas.append(
                    (
                        codigo,
                        agregado.periodo,
                        valor_agregado(codigo, agregado),
                        agregado.unidade,
                        fonte,
                        visualizacao,
                        agregado.data_referencia,
                        agregado.completo,
                        agregado.parcial,
                        agregado.motivo,
                        meta.desatualizado,
                        meta.versao_core,
                        meta.versao_gold,
                        meta.data_publicacao,
                        conjunto.consultado_em,
                        meta.de,
                        meta.ate,
                    )
                )
    return gerar_csv(colunas, linhas)
