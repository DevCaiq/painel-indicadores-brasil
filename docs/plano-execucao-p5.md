# Execução P5 — revisão final e CI

Escopo autorizado: concluir o painel conforme plano principal, etapa P5, preservando stack, sistema de design, dados e contratos das entregas anteriores. Sem publicar repositório, executar ETL, alterar o produtor ou acessar PostgreSQL.

- [x] Auditoria da apresentação: teclado, foco e nomes acessíveis, mensagens de validação, nulls, gráficos sem valores completos, contraste automatizado e reflow.
- [x] Testes permanentes Playwright com app de apoio e MockTransport, explicitamente identificados como dados sintéticos, sem depender de API externa ou instância local da pipeline.
- [x] Checar Chromium, Firefox e WebKit; axe para regras WCAG automatizáveis, árvore acessível e ampliação de texto. Resultado: 28 aprovados e 2 ignorados intencionalmente (POST compartilhado verificado uma vez). Sem teste com leitor de tela humano nem dispositivo físico.
- [x] Construção reproduzível pelos locks; conferir wheel instalado em ambiente temporário, incluindo templates, CSS, JS e licença Plotly.
- [x] Workflow GitHub Actions próprio preparado para Python3.12/Node24/uv0.13.9, lint/tipos/testes/build/pacote/navegadores. Sem secrets, serviços de banco ou publicação. Actions verificadas em fontes oficiais e fixadas em commit.
- [ ] Execução remota do workflow: depende de envio autorizado ao GitHub; não realizada nesta etapa.
- [x] README e instruções de operação/limites/aceite atualizados; revisão independente e execução final de pytest (161 aprovados), Ruff, mypy, npm e navegador. Evidências e limitações em [aceite-mvp.md](aceite-mvp.md).

Responsabilidade separada: CI e empacotamento delegados em arquivos exclusivos; interface, testes de navegador e documentação integrados pelo agente principal. Sem repositório Git neste workspace: nenhuma execução remota de Actions será afirmada sem evento real no GitHub. Validar os comandos equivalentes localmente e registrar a pendência remota, respeitando a proibição de publicação automática.

Interface de QA: `testes.apoio.servidor:criar_aplicacao_teste`, app local na porta8503, com transportes simulados e aviso visível de testes. `npm run verificar:navegador` usa playwright.config.mjs, projetos chromium/firefox/webkit, workers1; diretório de artefatos temporário ou ignorado. A instalação de navegadores é restrita aos binários Playwright, sem alterar componentes do Windows.

Critério: corrigir falhas observadas ou lacunas concretas do plano, sem redesenho nem novos recursos de produto. Evidência local não substitui CI remoto, leitor de tela humano ou validação em dispositivos físicos.
