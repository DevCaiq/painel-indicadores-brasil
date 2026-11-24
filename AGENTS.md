# Convenções do painel

Seguir docs/plano-painel-indicadores-brasil.md. Código próprio, testes e documentação em português-BR, identificadores sem acentos. Preservar interfaces de terceiros.
Não acessar banco, alterar o produtor, executar ETL ou copiar credenciais. Testes automatizados usam MockTransport e amostras identificadas; não dependem da API ligada.
Validar com pytest, Ruff, mypy e construção npm. Não publicar recursos automaticamente.
