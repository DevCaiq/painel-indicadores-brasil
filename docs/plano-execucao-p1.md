# Execução P1

Especificação: [plano aprovado](plano-painel-indicadores-brasil.md).

Objetivo: preparar Python/npm independentes, registrar o contrato real e entregar cliente de catálogo testado. Execução local nesta pasta nova, sem repositório anterior a isolar e sem alterações no produtor.

- [x] Arquivar OpenAPI e catálogo com origem, UTC e SHA-256.
- [x] Gerar locks Python e npm e construção local Tailwind/Plotly.
- [x] Escrever testes offline de catálogo, configuração e falhas; observar falha antes da implementação.
- [x] Implementar ConfiguracaoPainel, ClienteAPI e factory FastAPI com GET /health.
- [x] Verificar testes, lint, tipos, build e consulta real separada.
- [x] Documentar inicialização e pendência da UI UX Pro Max.

Interfaces: ClienteAPI(httpx.Client).buscar_catalogo() retorna Catalogo; falhas HTTP, transporte e validação viram ErroDeConsulta sanitizado. O cliente HTTP pertence ao chamador; a factory administra seu ciclo de vida.

Foco da revisão: URL sem credenciais/query, timeout positivo, metadados essenciais ausentes, JSON incompatível e erros sem payload externo. Esses casos entram nos testes de P1. Paginação, cache e interface ficam nas próximas etapas.

Decisão: manter FastAPI/Jinja2/Tailwind conforme autorização existente; não criar uma nova rodada de aprovação do desenho já fornecido. Inicialmente a UI UX Pro Max estava ausente; após instalação pelo responsável, a skill foi lida e executada para concluir a preparação visual.

- [x] Consultar UI UX Pro Max e registrar sistema de design com componentes, estados, responsividade e contraste calculado em `docs/sistema-de-design.md`.

## Evidências

11 testes offline aprovados; Ruff e mypy sem erros. uv sync --frozen, npm ci e npm run construir concluídos na entrega técnica. Consulta real de catálogo retornou 1, 432 e 433. UI UX Pro Max consultada e sistema de design registrado na conclusão da P1, com 14 pares de contraste calculados. P1 concluída; testes de interface renderizada continuam previstos em P3/P5. Nenhum repositório remoto, ETL ou recurso externo foi criado.
