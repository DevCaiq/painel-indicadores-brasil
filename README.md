# Indicadores do Brasil

Painel Python independente da pipeline: cards globais, históricos, agregados mensais/anuais, IPCA em 12 meses, frescor, cache e exportação CSV. P1–P4 implementadas; refinamento e automação local da P5 entregues, com execução remota do CI pendente. [Sistema de design](docs/sistema-de-design.md) e [aceite](docs/aceite-mvp.md).

## Preparar

Python 3.12, uv, Node.js e npm. Na raiz, execute cada comando separadamente:

```powershell
uv sync --frozen
npm ci
npm run construir
```

Configuração opcional em `.env`, seguindo `.env.example`. Nunca copiar credenciais do produtor. A URL padrão é `http://127.0.0.1:8000`.

## Executar

No terminal do produtor já configurado:

```powershell
cd D:\pipeline-etl
docker compose --env-file .env.banco up -d --wait banco
uv run --frozen pipeline-etl servir
```

Em outro terminal:

```powershell
cd D:\painel-indicadores-brasil
uv run --frozen uvicorn painel_indicadores.aplicacao:criar_aplicacao --factory --host 127.0.0.1 --port 8501
```

Acessar **http://127.0.0.1:8501/**. O padrão é Meta Selic nos últimos 12 meses; os cards continuam mostrando o último dado global, independentemente do filtro. Atalhos de 3/6/12 meses usam meses-calendário e preservam o dia quando possível. A tabela tem 25 registros por página e os filtros ficam na URL.

O indicador “API respondendo” verifica apenas `/health` do produtor e não comprova banco, cobertura ou frescor. O painel mantém seu próprio `/health` para saúde do processo.

## Dados e exportação

- **Observações:** os filtros selecionam datas inclusivas, sem preencher datas ausentes.
- **Agregados:** a seleção usa a chave de período (primeiro dia do mês/ano). Selic e dólar mostram o último valor publicado no período; IPCA usa a inflação composta enviada pela API. Períodos sem valor completo de IPCA são preservados como lacunas.
- **IPCA em 12 meses:** card global independente do filtro, com gráfico e tabela separados no mesmo recorte. O indicador vem pronto da gold; não é recalculado no painel.
- **Frescor:** referência, consulta da pipeline, publicação e consulta pelo painel são distintas. O cache preserva o instante UTC original da consulta. Timestamps são exibidos em Brasília; datas sem horário permanecem datas. Falha do frescor não apaga gráficos disponíveis.
- **CSV:** exporta todo o recorte e a visualização, mesmo quando a tabela exibe outra página. UTF-8 com BOM, separador `;`, ponto decimal e seis casas preservadas. Ao importar em planilhas, selecionar o ponto como separador decimal. Inclui fonte, referência, unidade, filtros, versões, flags e consulta UTC; ausências ficam vazias. Textos são protegidos contra fórmulas. Não há download apresentado como completo quando a consulta atingiu limite.
- **Atualizar dados:** POST local, protegido por token CSRF assinado, cookie SameSite e verificação de origem. Renova somente as chaves necessárias à página aplicada, sem disparar ETL. Intervalo padrão de 30 s, compartilhado pelo processo; repetição retorna 429 com Retry-After. O formulário não aplica alterações de filtros ainda não enviadas.

Se alterar código Python durante o desenvolvimento, reiniciar o servidor; para alterações em `frontend/`, executar novamente `npm run construir` e recarregar a página. Não usar `--reload` em produção.

## Verificar

```powershell
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
npm run construir
npx playwright install chromium firefox webkit
npm run verificar:navegador
uv run --frozen python scripts/verificar_pacote.py
```

Testes offline. Amostras públicas reais em `testes/amostras`, com arquivos de origem, UTC e SHA-256. Não confundir essas amostras com dados atuais da interface.

Os comandos de navegador e pacote acima pertencem à verificação. O servidor de testes usa a porta 8503, dados sintéticos identificados e MockTransport; não consulta a API. Recusa uma porta ocupada e encerra somente o processo que iniciou. Capturas e traces ficam no diretório temporário do sistema. Construir os assets antes de verificar o pacote: o script instala o wheel em ambiente temporário fora do código-fonte e confere páginas, templates, CSS, JS e licença Plotly.

O workflow próprio em `.github/workflows/qualidade.yml` executa instalação pelos locks, testes, lint, tipos, build, navegadores e pacote em Python 3.12/Node 24. Não usa banco, credenciais ou publicação. Sua execução no GitHub depende de envio autorizado a um repositório; os comandos locais não substituem esse evento remoto.

## Limites e próximos passos

- UI UX Pro Max instalada e consultada. Suíte Playwright para Chromium, Firefox e WebKit em 320, 375, 768, 1024 e 1440 px, incluindo filtros, zoom por teclado, CSV, validação, gráfico indisponível e funcionamento sem JavaScript. Browser plugin ausente nesta sessão, por isso usado Playwright.
- A suíte Python é offline. A comparação real com a API foi feita separadamente, inclusive equivalência de datas/valores do gráfico IPCA. Axe e inspeção automatizada da árvore acessível não substituem leitor de tela humano; WebKit não equivale a Safari em dispositivo físico. Essas revisões manuais permanecem pendentes.
- Cliente consulta catálogo, observações, agregados, IPCA12m e frescor; temporais percorrem cursores e validam a geração da própria camada (core ou gold), com um reinício em conflito. Não é snapshot atômico entre rotas. Resultados parciais não alimentam cards globais nem o cache. Quando possível, um recorte explícito é consultado mesmo se o acervo global ficou incompleto, sem promover seu último valor a card global.
- Cache local por processo: TTL de 300 s, até 64 entradas e 16 MiB de chaves/corpos serializados; cargas serializadas para evitar rajadas. O orçamento não representa o consumo total de memória do processo. Usar um processo inicialmente: cache, limites de atualização e chave CSRF não são coordenados entre réplicas.
- Prazo compartilhado de 30 s para o panorama, com verificação entre pedidos/blocos da resposta. Uma operação de rede síncrona já pendente depende do timeout de conexão/leitura; não é cancelamento rígido em tempo real. Espera pelo bloqueio do cache também não tem prazo independente nesta etapa.
- Medidas são validadas como decimais de seis casas, com até 14 dígitos inteiros, coerentes com o armazenamento NUMERIC(24,10) do produtor. Não são convertidas em float para regras de apresentação.
- Evidências das consultas reais em [validacao-p2.json](docs/validacao-p2.json) e [validacao-p4.json](docs/validacao-p4.json); contagens e valores desses relatórios são históricos, não constantes da interface. Amostras gold/frescor em testes/amostras têm origem UTC e SHA-256 verificados nos testes.
- Assets locais são gerados pelo build, incluindo licença do Plotly, e ignorados no versionamento.
- TestClient emite aviso de depreciação da integração httpx na versão instalada de Starlette. A integração segue funcionando; reavaliar na próxima atualização de dependências.
- Nenhum ETL, acesso direto a banco ou publicação é feito pelo painel.
