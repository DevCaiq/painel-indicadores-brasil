# Contrato conferido em 23/11/2026

Instância: `http://127.0.0.1:8000`. `/ready` respondeu HTTP 200, situação `pronto`, esquema `0010`.

OpenAPI e catálogo foram arquivados em `testes/amostras/`. Cada arquivo tem proveniência em `<nome>.origem.json`, com URL, instante UTC e SHA-256 dos bytes arquivados.

O catálogo retornou os códigos 1, 432 e 433. Envelope do catálogo: `data` e `meta`, sem `pagina`. O modelo aceita campos adicionais e exige os campos essenciais implementados. A consulta real pelo ClienteAPI foi executada separadamente dos testes offline.

Na P2, observações foram exercitadas com a API real para os três códigos, percorrendo todas as páginas do recorte 2020–23/11/2026. Registro separado em `docs/validacao-p2.json`. Conferimos envelope `data`/`pagina`/`meta`, paginação ascendente, filtros inclusivos, números com seis casas e geração core estável. `versao_gold` não define a geração das observações core.

Completude da consulta (todas as páginas obtidas) não equivale a cobertura completa da fonte. Os cards preservam `cobertura` inclusive quando desconhecida; cobertura explicitamente incompleta gera aviso. Limites, reinício de geração, 429/503 e falhas de contrato foram testados offline com dados sintéticos identificados.

Na P4, agregados mensais/anuais das três séries, IPCA em 12 meses e frescor foram exercitados separadamente contra a API real. `docs/validacao-p4.json` registra oito pedidos GET e seis exportações integrais conferidas. Fixtures reais adicionais, com origem/UTC/SHA-256, estão em `testes/amostras/`: agregados anuais de IPCA, mensais de Selic, IPCA12m e frescor.

Gold usa `versao_gold`/`versao_dados` para continuidade; `versao_core` pode diferir. `meta.desatualizado` e `motivo` são preservados, sem afirmar snapshot atômico entre rotas. `ultimo` representa Selic/dólar agregados; `variacao` representa IPCA, incluindo composto anual e 12 meses. Valores inválidos/incompletos da inflação permanecem nulos no gráfico e CSV.

Frescor não usa o envelope paginado temporal: valida `data` e `meta` sem exigir `pagina`. Timestamps precisam conter fuso e são normalizados para UTC. O cliente mede `consultado_em` na resposta validada; cache hits preservam esse instante. `meta.data_publicacao` continua sendo data. HTTP409 no frescor vira erro controlado, sem derrubar consultas de indicadores que funcionam.

Não pressupor que catálogo disponível, consulta paginada completa ou ausência de defasagem sinalizada significam cobertura completa da fonte.
