# Execução P4 — gold, frescor, atualização e CSV

Especificação: plano principal, seções 5–8 e etapa P4. Continuação autorizada da stack e do sistema de design existentes, sem alteração de pipeline, ETL ou publicação.

- [x] Contratos gold e frescor com Decimal, null, cobertura, versões e consulta UTC preservados; fixtures reais com origem/hash.
- [x] Generalizar paginação por rota/camada: geração core para observações, gold para agregados/IPCA12m; período/cursor/código/unidade estáveis, limites e reinício único da P2 preservados.
- [x] Cache tipado e limitado, incluindo consulta UTC original em hits; invalidação por chaves exatas, sem limpar outros recortes.
- [x] Serviço: agregados mês/ano, IPCA12m global e histórico separado, frescor independente e falha isolada. Escolher `ultimo` para Selic/dólar com rótulo explícito; `variacao` do produtor para IPCA, nunca soma/média de inflação.
- [x] UI: quarto card IPCA12m, visualização observações/mês/ano, gráfico separado IPCA12m, avisos de stale/parcial/nulo, tabela equivalente e metodologia com quatro referências de tempo distintas.
- [x] GET `/exportar.csv`: todas as linhas do recorte/visualização, UTF8 BOM, ponto decimal sem perda, separador `;`, proveniência e flags; sem exportação completa se paginação incompleta. Campos textuais protegidos contra fórmulas.
- [x] POST `/atualizar`: token CSRF assinado vinculado ao cookie, origem exata, intervalo de 30 s por processo; validar filtros e proteção antes de invalidar; redirect 303 para o mesmo filtro. Nunca chama ETL. Usar form-urlencoded da stdlib, sem dependência multipart.
- [x] Testes offline de contratos, paginação gold, frescor desconhecido, cache, nulls, CSV e POST seguro. Smoke real separado, navegador desktop/celular, revisão independente, pytest/Ruff/mypy/npm.

Interfaces: `ClienteAPI.buscar_agregados(codigo,de,ate,granularidade)` e `buscar_ipca_12m(de,ate)` retornam `ConjuntoAgregados`; `buscar_frescor()` retorna `RespostaFrescor`. `CacheHistoricos.obter_tipado(chave,carregar,tipo)` compartilha o orçamento de 64 entradas/16MiB; `invalidar(chaves)` é seletivo. `ServicoIndicadores.obter_gold(...)`, `obter_ipca_12m(...)`, `obter_frescor()`, `renovar(codigo,de,ate,visualizacao)`.

Representação: agregados são selecionados pela chave `periodo` entre datas inclusivas, como a API; não expandir o início do filtro para mês/ano silenciosamente. Para inflação composta, `completo != true`, `parcial=true` ou `variacao=null` vira lacuna com motivo, sem zero/substituição por período anterior. Selic/dólar mantêm último valor publicado e flags, sem afirmar calendário completo.

CSV gold inclui período, referência, unidade, valor selecionado, completo/parcial/motivo, versão e fonte. Datas sem horário não recebem conversão de fuso. Consulta do painel é UTC obtida no cliente e preservada pelo cache. Timestamps da pipeline devem conter fuso; exibir em America/Sao_Paulo. Snapshot entre rotas não é atômico.

Segurança e CSV são tarefas independentes delegadas conforme skill dispatching-parallel-agents; contratos/cliente/serviço/UI integrados pelo agente principal. Browser plugin ausente; usar Playwright já instalado, capturas temporárias fora do repositório. Aprovação do escopo já consta na conversa; não repetir rodada de desenho.

## Evidências e decisões finais

Fixtures oficiais foram arquivadas sem alterar arquivos anteriores; testes verificam seus hashes. Smoke separado em docs/validacao-p4.json conferiu os seis agregados (mês/ano para cada série), IPCA12m e frescor. O IPCA anual de 2026 permanece sem valor por período em andamento, sem zero ou substituição pelo ano anterior.

Playwright Chromium, em servidor próprio temporário na porta 8502 (API permanece 8000): quatro cards, agregados anuais iguais à API, dois gráficos com zoom independente por teclado, download CSV anual com 7 registros e IPCA12m com 82 registros, CSV de 31 observações quando tabela exibia 6 linhas, POST 303 preservando filtro, repetição 429 com Retry-After, origem externa 403 e ausência de overflow da página nas larguras 320/375/768/1024/1440. Sem erros JavaScript nos fluxos normais. Capturas temporárias desktop/celular inspecionadas fora do repositório. Nenhum export operacional versionado.

Revisão independente apontou conflito 409 de frescor escapando da interface de erro. Corrigido com regressão RED/GREEN e revisão posterior sem bloqueadores. Uma consulta global incompleta pode tentar apenas o recorte selecionado, mantendo o card global indisponível; se continuar incompleta, não afirmar que o período está vazio. Código Python e assets permanecem na stack aprovada, sem dependências novas nesta etapa.

Limites mantidos: um processo; cache/CSRF/limitador não coordenam réplicas; prazo de 30 s verificado entre operações/blocos não interrompe rigidamente I/O síncrono ou espera de trava. Leitor de tela e outros navegadores permanecem no refinamento P5. Nenhuma alteração no produtor, credencial copiada ou chamada de ETL.



Verificação final: 153 testes offline aprovados; Ruff check e format aprovados; mypy aprovado em 14 arquivos próprios; npm run construir e node --check frontend/painel.js aprovados. O aviso de depreciação Starlette/httpx já existente permanece registrado no README. P4 concluída no escopo documentado.
