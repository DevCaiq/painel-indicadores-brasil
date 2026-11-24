# Aceite técnico do MVP

Registro local de 23/11/2026, conforme o plano principal. P1–P4 implementadas; P5 com refinamento, testes e workflow preparados. O encerramento integral do critério “workflow executado” depende de uma execução real no GitHub, após publicação autorizada. Nenhum repositório ou recurso foi publicado nesta entrega.

## Evidências

| Verificação | Resultado local |
|---|---|
| Python | 161 testes aprovados, sem depender da API ligada |
| Ruff | Lint e formatação aprovados |
| mypy | 14 arquivos de código aprovados |
| Instalação | `uv sync --frozen` e `npm ci` aprovados |
| Assets | Construção Tailwind, JavaScript e Plotly locais aprovada |
| Wheel instalado | Saúde, HTML, templates, CSS, JS, Plotly e licença aprovados em ambiente temporário fora do repositório |
| Navegadores | 28 cenários aprovados e 2 ignorados intencionalmente, em Chromium, Firefox e WebKit |
| Acessibilidade automatizada | Nenhuma violação axe nos três estados auditados de cada navegador; árvore acessível, teclado e reflow aprovados |

As verificações de navegador são executadas por `npm run verificar:navegador`, com três projetos (Chromium, Firefox e WebKit). O cenário POST é executado uma vez em Chromium porque o limitador é compartilhado pelo servidor; nas outras duas execuções é ignorado explicitamente. O servidor é exclusivamente de testes, com aviso visível de dados sintéticos, transporte MockTransport e encerramento automático do processo criado.

A suíte verifica quatro cards, independência entre valores globais e filtros, zero e negativo legítimos, lacunas, CSV completo apesar da paginação, validação de campos, foco, teclado, zoom independente, fallback sem Plotly/JavaScript, árvore acessível e axe. Confere reflow em 320/375/768/1024/1440 px e texto ampliado a 200%. Capturas e traces ficam no diretório temporário do sistema.

O refinamento corrigiu mensagens de erro ligadas aos campos, motivos conhecidos em linguagem compreensível, períodos sem valores completos preservados em tabela sem eixos vazios e escape de unidade externa nos gráficos. O resumo de erros transfere foco ao campo de data também no Firefox; o atalho de pular conteúdo entra explicitamente na sequência de Tab também no WebKit. Capturas de 375 e 1440 px foram inspecionadas visualmente. O empacotamento inclui explicitamente os assets gerados, mesmo quando ignorados pelo versionamento.

## Operação e limites

Inicialização, construção e comandos de verificação estão no [README](../README.md). Usar inicialmente um processo: cache, chave CSRF e limitação de atualização não são coordenados entre réplicas. A atualização renova consultas, sem coletar dados ou disparar ETL. Falhas e incompletude permanecem explícitas; o painel não preenche datas ausentes ou converte valores nulos em zero.

As consultas reais das etapas anteriores estão registradas em [P2](validacao-p2.json) e [P4](validacao-p4.json). São evidências históricas; não representam os dados atuais nem os dados sintéticos dos testes. Nesta etapa não foi necessário acessar banco ou alterar o produtor.

Pendências de validação externa: execução remota do workflow, revisão com leitor de tela humano e dispositivos físicos. Axe e árvore acessível fornecem evidência automatizada parcial; WebKit não equivale a Safari físico. A aprovação técnica local não afirma essas validações externas.

O TestClient emite aviso conhecido de depreciação da integração httpx/Starlette; não houve falha nos testes. A instalação npm informou script opcional de `@parcel/watcher` sem aprovação, mas o build foi concluído sem liberar scripts adicionais. No ambiente gerenciado desta sessão, Firefox precisou de execução de ferramenta fora do sandbox de processos; nenhuma proteção do aplicativo ou preferência de segurança do navegador foi desativada.
