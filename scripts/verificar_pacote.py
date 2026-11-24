"""Valida o wheel instalado fora do repositório, sem consultar a API produtora."""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

RECURSOS = (
    "painel.css",
    "painel.js",
    "vendor/plotly.min.js",
    "vendor/plotly.LICENSE",
)


def verificar_instalacao() -> None:
    """Usa apenas o pacote instalado e um serviço sintético substituído."""
    from unittest.mock import Mock, patch

    import httpx
    from fastapi.testclient import TestClient

    import painel_indicadores
    from painel_indicadores.aplicacao import criar_aplicacao
    from painel_indicadores.indicadores import (
        SERIES,
        CardIndicador,
        PanoramaIndicadores,
    )
    from painel_indicadores.rotas import obter_servico

    assert "site-packages" in str(painel_indicadores.__file__)
    servico = Mock()
    servico.obter_contexto.return_value = PanoramaIndicadores(
        cards=tuple(
            CardIndicador(codigo=codigo, nome=nome, unidade=unidade)
            for codigo, (nome, unidade) in SERIES.items()
        ),
        historicos={},
    )
    servico.obter_ipca_12m.return_value = None
    servico.obter_frescor.return_value = None
    servico.verificar_processo.return_value = False
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_servico] = lambda: servico
    # Nenhum transporte HTTP real pode ser usado durante a verificação offline.
    with patch.object(
        httpx.HTTPTransport,
        "handle_request",
        side_effect=AssertionError("Acesso externo proibido no smoke offline"),
    ):
        cliente = TestClient(aplicacao)
        assert cliente.get("/health").json() == {"situacao": "ativo"}
        pagina = cliente.get("/")
        assert pagina.status_code == 200
        assert '<html lang="pt-BR">' in pagina.text
        assert "Indicadores do Brasil" in pagina.text
        for recurso in RECURSOS:
            resposta = cliente.get("/estaticos/" + recurso)
            assert resposta.status_code == 200, recurso
            assert resposta.content, recurso
        cliente.close()
    print("Wheel instalado: saúde, HTML, CSS, JS, Plotly e licença aprovados offline.")


def executar() -> None:
    raiz = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="painel-wheel-") as temporario:
        pasta = Path(temporario)
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(pasta)],
            cwd=raiz,
            check=True,
        )
        wheel = next(pasta.glob("*.whl"))
        with ZipFile(wheel) as pacote:
            for recurso in RECURSOS:
                nome = "painel_indicadores/estaticos/" + recurso
                assert nome in pacote.namelist(), f"Recurso ausente no wheel: {nome}"
                assert pacote.read(nome), f"Recurso vazio: {nome}"
            assert "painel_indicadores/templates/painel.html" in pacote.namelist()
        ambiente = pasta / "ambiente"
        subprocess.run(
            ["uv", "venv", "--python", sys.executable, str(ambiente)], check=True
        )
        python = ambiente / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        requisitos = pasta / "requisitos.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(requisitos),
            ],
            cwd=raiz,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "-r", str(requisitos)],
            check=True,
        )
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
            check=True,
        )
        subprocess.run(
            [str(python), "-I", str(Path(__file__).resolve()), "--smoke"],
            cwd=pasta,
            check=True,
        )


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke"]:
        verificar_instalacao()
    else:
        executar()
