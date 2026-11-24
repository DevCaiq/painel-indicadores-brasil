# Execução P3 — página interativa

Referências: plano principal, P3 e `docs/sistema-de-design.md`. Execução já autorizada no workspace local, sem publicação. Usar diretamente o sistema de design definido na P1: HTML/CSS nativos, sem imagens decorativas ou novo desenho que o substitua.

- [x] Testes offline de filtros de calendário, gráficos e HTML com serviço substituído; observar falha antes de implementar.
- [x] `pagina.py`: filtros estritos, atalhos de meses-calendário (mesmo dia, limitado ao último dia do mês), modelos de apresentação, paginação da tabela de 25 linhas e composição com orçamento da P2.
- [x] `graficos.py`: dados Plotly locais, degraus Selic, barras IPCA com zero, linha dólar, pt-BR e lacunas sem preenchimento.
- [x] `rotas.py`, templates e assets: GET `/`, query string compartilhável, três cards globais, gráfico selecionado, métricas e tabela equivalentes; 422 HTML com campos preservados, erros por série, vazio e incompletude visível. Assets com autoescape e tojson.
- [x] JavaScript: feedback durante envio, proteção contra envio duplicado, recuperação após voltar, zoom/restauração operáveis por teclado, renderização responsiva e fallback se gráfico falhar.
- [x] Build, suíte Python, Ruff, mypy e navegador desktop/celular; comparar com API real. Revisão independente antes de concluir.

Interfaces: `obter_servico(Request) -> ServicoIndicadores` substituível nos testes; `ServicoIndicadores.obter_contexto(hoje) -> PanoramaIndicadores` com cards e históricos já consultados, sem repetir falhas na mesma página; `criar_grafico(codigo, observacoes) -> dict` serializável; `FiltrosPagina` com código, datas e página da tabela.

Decisões: padrão Selic/últimos 12 meses, limites 2020–hoje; gráfico de observações em P3. Integração visual de agregados gold será feita junto de frescor e IPCA 12m em P4; não expor controle sem implementação. CSV e atualização manual também permanecem em P4. Datas do IPCA exibidas como mês/ano, outras como dia/mês/ano. Consulta do painel não será rotulada como atualização da fonte.

Navegador: plugin Browser ausente (nenhuma ferramenta/skill disponível); fallback Playwright conforme skill frontend-testing-debugging. @playwright/test apenas como dependência de desenvolvimento. Capturas e scripts temporários de QA fora do repositório.

Revisar segurança do JSON embutido, entradas inválidas, perda de estados no histórico do navegador, tabela em celular e falha isolada dos gráficos. Sem teste externo na suíte automatizada Python. Validação visual não equivale a auditoria completa com leitor de tela.

## Verificação da entrega

88 testes Python offline aprovados, incluindo HTML, 422, paginação, vazio, falha isolada, precisão dólar e cache configurável. Ruff, mypy e build npm aprovados. Revisão independente sem bloqueadores; seus achados de precisão/TTL corrigidos com regressões RED/GREEN.

Playwright Chromium: fluxo aplicar filtros com feedback de carregamento, voltar com botão habilitado, cards globais preservados, gráfico IPCA comparado com resposta real da API, zoom/restauração por teclado, paginação 26–31/31, resumo de erro com foco, período vazio, script Plotly bloqueado com tabela preservada e modo sem JavaScript. Inspeção de capturas desktop/celular coerente com o sistema de design. Sem erros JavaScript nos fluxos normais; HTTP422 e falha de script provocados intencionalmente nos cenários correspondentes. Sem rolagem horizontal da página em 320/375/768/1024/1440 px, além de ampliação de texto em 200% (640 e 320 px).

Sondagem do produtor consulta apenas status/cabeçalhos de /health, sem baixar corpo nem inferir frescor. P3 concluída no escopo registrado. Agregados, frescor, IPCA12m, CSV e atualização manual seguem em P4. Não houve alteração do produtor ou execução de ETL. O servidor temporário de QA será encerrado; inicialização documentada no README.


Checagem final de JavaScript: sintaxe aprovada por node --check; fluxo Playwright repetido com locale pt-BR e timezone America/Sao_Paulo. Datas do eixo interpretadas como UTC também nos controles de zoom.
