# Execução P2 — históricos e panorama

Especificação: `docs/plano-painel-indicadores-brasil.md`, seções 5, 6, 8 e etapa P2. Stack e execução local já autorizadas. Sem alteração no produtor.

Objetivo: obter históricos coerentes das séries 1, 432 e 433 e produzir modelos de cards com últimos valores globais, reutilizando cache básico.

## Entregas

- [x] Contratos em `contratos.py`: filtros explícitos, observação Decimal finita, página e conjunto imutável com completude da consulta separada da cobertura da fonte.
- [x] Cliente em `cliente_api.py`: `buscar_observacoes(codigo, de, ate)` com cursores opacos, filtros preservados, geração core estável, reinício único em 409/mudança de geração, limites e prazo compartilhado. Erros sanitizados; repetição transitória no máximo uma por pedido.
- [x] `cache.py`: TTL monotônico de 300 s, 64 entradas, limite de bytes, concorrência controlada e não armazenamento de erro/conjunto parcial. Chave inclui servidor, rota, filtros e versão de transformação.
- [x] `indicadores.py` e `formatacao.py`: último global só com consulta completa do recorte 2020–hoje; métricas do período separadas, comparação em pp ou R$, formatação pt-BR e isolamento de falha por série.
- [x] Integrar serviço ao ciclo de vida da aplicação, testar sem rede e executar smoke real separado. Página HTML pertence a P3, sem adicionar rota pública provisória.

## Interfaces

`ClienteAPI.buscar_observacoes(codigo: int, de: date, ate: date) -> ConjuntoObservacoes`.
`CacheHistoricos.obter(chave: str, carregar: Callable[[], ConjuntoObservacoes]) -> ConjuntoObservacoes`.
`ServicoIndicadores.obter_panorama(hoje: date | None = None) -> tuple[CardIndicador, ...]`.
`calcular_metricas(conjunto, de, ate) -> MetricasPeriodo` e `formatar_decimal(valor, casas=2)`.

## Testes e revisão

Observar falha antes de implementar, depois aprovar casos de: várias páginas; cursor repetido/incoerente; duplicatas; metadados de período/código inválidos; geração core alterada (gold independente); 409 repetido; prazo/limites; 422/404 sem repetição; 429/503/timeouts; JSON e números inválidos; datas invertidas/futuras; cache expirado/isolado/concorrente e sem erro; último global independente do filtro; ausência/zero/IPCA negativo e comparação com datas não consecutivas. Incompletude de consulta nunca equivale a cobertura oficial completa.

Decisões: cache de no máximo 16 MiB além do limite de entradas; espera automática de Retry-After no máximo 1 s, acima disso pedir nova tentativa; relógio e transporte injetáveis. Não adicionar média genérica, exportação ou UI em P2. Não criar repositório remoto nem modificar ETL.

Comandos: `.venv/Scripts/python -m pytest -q`, Ruff e mypy sobre código próprio, `npm run construir`. Não varrer código de terceiros em `.agents` com lint do projeto.

## Decisões verificadas durante a execução

- Prazo de 30 s também compartilhado pelo panorama, reduzindo o orçamento das séries seguintes. Streaming verifica o relógio entre blocos e rejeita sucesso tardio; corpo limitado a 4 MiB por página. Uma operação síncrona de I/O já pendente continua sujeita ao timeout da fase, sem promessa de cancelamento rígido em 30 s. Espera pelo bloqueio do cache não possui deadline independente; antes de múltiplos usuários, rever espera e deduplicação por chave em P3/P4.
- Cache armazena bytes JSON, retornando novos modelos na leitura; o limite de 16 MiB cobre chaves e payloads, não o overhead total do processo. Cargas são serializadas neste processo inicial, sem paralelismo ilimitado.
- Contrato numérico: seis casas e até 14 dígitos inteiros, compatível com NUMERIC(24,10) do produtor. Recusar expoentes, underscores e extremos antes de calcular ou formatar.
- Validação de unidade estável entre páginas, período, código, ordem, datas duplicadas, cursor e geração. Cobertura da fonte acompanha o card e não é confundida com completude da consulta.
- Modelos dos três cards validados com dados reais; a apresentação HTML permanece em P3. Não adicionada rota provisória para expor esses modelos.

## Revisão

Revisão independente somente leitura identificou prazo de resposta em gotejamento e extremos Decimal. Ambos receberam regressões observadas falhando antes da correção. A revisão posterior não encontrou bloqueadores nas correções. Acrescentado ainda teste do orçamento compartilhado do panorama.

## Evidência final

68 testes offline aprovados; Ruff check e format aprovados; mypy aprovado em oito arquivos próprios; build npm concluído. Smoke real em docs/validacao-p2.json: 4.329 observações em seis pedidos, repetição atendida sem novas chamadas. P2 concluída no escopo de dados e modelos dos cards. Sem alteração no produtor, ETL ou publicação. As limitações de I/O síncrono e espera pelo cache estão explicitadas acima.
