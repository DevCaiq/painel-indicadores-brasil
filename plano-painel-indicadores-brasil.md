# Plano do painel de indicadores do Brasil

Documento de transição para implementação em **`D:\painel-indicadores-brasil`**.
Preparado em 23/11/2026. Stack e escolhas abaixo são propostas recomendadas para
o primeiro protótipo; nenhum frontend foi implementado por este documento.

## 1. Objetivo e contexto

Criar uma aplicação web simples, interativa e em português-BR, que transforme os
dados da pipeline em cards, gráficos e explicações compreensíveis. O foco é
portfólio de engenharia de dados e desenvolvimento Python, evidenciando consumo
de API, qualidade, rastreabilidade e tratamento de falhas.

Projeto produtor: `D:\pipeline-etl`.
Repositório: https://github.com/DevCaiq/pipeline-etl-indicadores-brasil
Branch atual: `principal`. Commit de referência inicial: `35b1d2d`.

O painel terá repositório, ambiente virtual e lock próprios. Ele consulta a API;
não acessa PostgreSQL, não executa ETL e não consulta BCB/IBGE diretamente.
Infraestrutura, credenciais e dados operacionais do produtor não serão copiados.

## 2. Tecnologias recomendadas

| Item | Escolha | Finalidade |
|---|---|---|
| Linguagem | Python 3.12 | Alinhamento ao projeto produtor |
| Servidor web | FastAPI + Uvicorn, handlers síncronos | Páginas e composição em Python |
| Templates | Jinja2 | HTML semântico renderizado pelo servidor |
| Frontend | HTML + Tailwind CSS 4 + JavaScript | Layout responsivo, estilos e interações |
| Processo de design | Skill UI UX Pro Max | Direção visual, componentes e revisão de UX |
| Gráficos | Plotly.js, versão fixada e distribuição local | Hover, zoom e navegação histórica |
| Dados de apresentação | Python e Decimal | pandas não é obrigatório no MVP |
| HTTP | httpx síncrono | Cliente da API com timeouts e tratamento de erros |
| Contratos | Pydantic | Validar respostas e configurações |
| Configuração | pydantic-settings e arquivo `.env` local | URL e limites sem caminhos fixos |
| Dependências | uv, `pyproject.toml`, `uv.lock` | Ambiente independente e instalação reproduzível |
| Qualidade | pytest, Ruff e mypy | Testes offline, estilo e tipos |
| Teste das páginas | TestClient do FastAPI + pytest | HTML e respostas com cliente simulado |
| Construção frontend | Node.js LTS + npm e `package-lock.json` | Compilar Tailwind e preparar assets |
| Navegador | Playwright, na validação visual | Desktop, celular, navegação e downloads |
| Versionamento | Git e GitHub Actions | Revisão e CI próprio |

Fixar no lock versões compatíveis com Python 3.12 após instalação e testes; não
copiar automaticamente o lock da pipeline. Bibliotecas que só forem usadas na
etapa visual ou de exportação entram nessa etapa, evitando dependências desnecessárias.

A revisão solicitada adota Tailwind diretamente nos templates. Python cuida de
contratos, paginação, regras e renderização; JavaScript cuida dos gráficos e da
interação visual. O FastAPI do painel serve páginas e downloads, com responsabilidade
distinta da API produtora. Não duplicar ETL, banco ou regras gold. Node/npm são
ferramentas de construção; não é necessário servidor Node em produção.

### UI UX Pro Max: disponibilidade e aplicação

A skill foi solicitada, mas **não foi encontrada instalada no ambiente desta sessão**.
Ela não foi executada nesta revisão documental. Referência de origem localizada:
[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
Antes da etapa visual, conferir origem/versão, disponibilizar a skill no ambiente
do novo projeto e ler seu `SKILL.md`. Usar os comandos da versão instalada, sem
presumir caminhos. Se continuar indisponível, registrar a pendência da etapa visual;
não afirmar que o design foi produzido com a skill.

Registrar em `docs/sistema-de-design.md`: direção de dashboard, paleta com contraste
verificado, tipografia, espaçamento, componentes e estados de carregamento, vazio
e erro. A skill orienta o desenvolvimento; não é biblioteca carregada pelo navegador.
Suas recomendações devem respeitar as regras de dados e acessibilidade deste plano.

## 3. Arquitetura e comunicação

```text
Navegador
    │ página e interações
    ▼
Painel FastAPI + Jinja2 :8501 — HTML / Tailwind / Plotly.js
    │ HTTP GET, executado pelo servidor Python
    ▼
API FastAPI da pipeline :8000 ou :8001
    │ leitura controlada
    ▼
PostgreSQL / dados publicados pela pipeline
```

O consumo ocorre no servidor Python do painel, portanto CORS da API não é necessário
nesse fluxo. Se futuramente o navegador chamar FastAPI diretamente, rever CORS
com origens explícitas. Não habilitar `*` preventivamente. O navegador recebe
HTML e dados de apresentação da mesma origem, sem credenciais do produtor.

Rotas próprias propostas: `GET /` com filtros, `GET /exportar.csv` com o mesmo
recorte validado e `GET /health` para o processo do painel. Assets em `/estaticos`.
Renovação explícita do cache, se implementada, usa POST próprio com validação de
origem/CSRF e limite de frequência. Nenhuma rota do painel pode disparar ETL.

No host local, usar `http://127.0.0.1:8000` como padrão configurável. A composição
Docker já usada no produtor pode disponibilizar `http://127.0.0.1:8001`; confirmar
a porta real antes de executar. Não trocar de porta silenciosamente no cliente.
Em containers distintos, `127.0.0.1` aponta para o próprio container: usar o nome
do serviço/rede apropriado na futura composição.

## 4. Fontes do contrato: precedência

1. OpenAPI da instância da API escolhida: `/openapi.json` e `/docs`.
2. Código atual em `src/pipeline_etl/api/`, especialmente `aplicacao.py`,
   `esquemas.py`, `filtros.py` e `ibge.py`.
3. Documentação `docs/api.md` e documentos posteriores de IBGE/cache/frescor.

`docs/api.md` contém histórico do M1, com referências antigas a esquema `0006`,
ausência de IBGE/Redis e portas. Não interpretar esses trechos como estado atual.
O produtor já possui entrega técnica M2 e migração `0010` verificadas, mas a
instância usada pelo painel deve ser conferida. Não fixar contagens e valores
históricos da sessão como dados atuais da interface.

Antes de implementar, obter uma cópia do OpenAPI sem credenciais e guardar uma
fixture versionável do contrato no painel. Registrar origem, instante UTC e SHA-256.
Não gerar fixtures apresentadas como oficiais a partir de dados inventados.

## 5. Rotas necessárias

Todas as consultas abaixo são GET e não disparam coleta, carga ou publicação.

| Rota | Uso no painel |
|---|---|
| `/health` | Diagnóstico de processo; não prova banco ou dados disponíveis |
| `/ready` | Disponibilidade técnica; não prova existência de histórico ou gold |
| `/api/v1/series` | Catálogo, unidades, periodicidade e cobertura |
| `/api/v1/series/{codigo}` | Informações de uma série |
| `/api/v1/series/{codigo}/observacoes` | Valores históricos da série |
| `/api/v1/series/{codigo}/agregados` | Resumos gold mensais/anuais |
| `/api/v1/indicadores/ipca-12m` | IPCA acumulado composto em doze meses |
| `/api/v1/pipeline/frescor` | Referência, consulta, publicação e indicadores de frescor |
| `/api/v1/pipeline/execucoes` | Diagnóstico opcional, não necessário à página pública inicial |

Não usar `/metrics` para alimentar os gráficos. É rota de monitoramento interno,
deve permanecer restrita e não faz parte do contrato de indicadores do painel.

### Parâmetros das listas temporais

| Parâmetro | Contrato |
|---|---|
| `de`, `ate` | Datas inclusivas no formato estrito `YYYY-MM-DD` |
| `limite` | Padrão 100, mínimo 1, máximo 1000 |
| `cursor` | Opaco, retornado pela API; nunca criar ou decodificar no painel |
| `granularidade` | Somente agregados: `mes` ou `ano` |

Recorte público BCB desde `2020-01-01`. Rejeitar período invertido, futuro ou acima
do limite contratual de 3.660 dias inclusivos. Se o histórico ultrapassar esse limite
no futuro, dividir em janelas explícitas e reconciliar as fronteiras, sem descartar
dados. O apoio IPCA de 2019 é interno ao produtor e não deve ser solicitado como
observações públicas.

Exemplo de consulta, sem fixar valores de resposta:

```http
GET /api/v1/series/432/observacoes?de=2020-01-01&ate=2026-11-23&limite=1000
```

As respostas de listas usam `data`, `pagina` e `meta`:

- `data`: registros; observação tem `data` e `valor`.
- `pagina`: `limite`, `tem_mais`, `proximo_cursor`.
- `meta`: camada, `versao_dados`, `versao_core`, `versao_gold`, `data_publicacao`,
  `desatualizado`, `motivo`, período resolvido e cobertura quando aplicáveis.
- `cobertura`: `inicio`, `fim`, `observacoes`, `unidade_contagem`, `completa`, `motivo`.

Os campos por rota devem ser validados com o OpenAPI, sem supor um envelope idêntico
para probes e erros. Permitir campos adicionais compatíveis, mas recusar a ausência
de campos essenciais e valores numéricos inválidos.

## 6. Regras dos indicadores

| Indicador | Série SGS | Unidade | Significado do card |
|---|---:|---|---|
| Meta Selic | 432 | `% a.a.` | Última meta disponível; não é Selic efetiva diária |
| IPCA mensal | 433 | `% a.m.` | Variação do último mês disponível; pode ser negativa |
| Dólar comercial venda | 1 | `R$/US$` | Última observação disponível; não é cotação em tempo real |
| IPCA 12 meses, adicional | Endpoint próprio | `% em 12 meses` | Campo `variacao` do último período, quando completo |

Os três cards principais mostram **o último dado disponível do acervo público**,
independentemente do filtro do gráfico. Exibir essa regra junto aos cards.
Se só parte do acervo tiver sido obtida, não apresentar seu último item como último
dado global. A API ordena observações crescentemente e não oferece aqui um parâmetro
`ordem=desc` ou rota `/ultimo`: obter todas as páginas do recorte público suportado
para determinar os últimos valores, reutilizando a consulta em cache.

Métricas do período filtrado ficam separadas: primeiro/último valor observado,
mínimo, máximo e número de observações. Só mostrar média quando fizer sentido para
a série, com rótulo explícito. Não tratar média mensal de IPCA como inflação acumulada.

Variação entre últimas observações, se implementada:

- Selic/IPCA: diferença em **pontos percentuais**, com datas de comparação.
- Dólar: diferença absoluta em R$; variação percentual opcional, com base não nula.
- Não dizer "ontem" se as observações não forem de dias consecutivos.
- Cor de alta/queda deve ser neutra; alta não é automaticamente melhoria econômica.

Medidas chegam como strings decimais com seis casas. Usar `Decimal` para cálculos
e formatação; converter para float apenas no limite de renderização do Plotly.
Formatar em português-BR: vírgula decimal, ponto de milhar e unidade explícita.
Não substituir ausência, `null` ou incompletude por zero. Não preencher fins de
semana/feriados nem interpolar IPCA. Preservar incerteza de calendário/cobertura.

IPCA acumulado em doze meses será consumido da gold; não somar percentuais mensais
nem reconstruir o indicador no frontend. `variacao=null`, `completo=false`,
`parcial=true` e `motivo` exigem comunicação de limitação. Ler cada sinal segundo
o contrato; `PRONTA` ou `desatualizado=false` não comprovam cobertura completa.

## 7. Página proposta

### Cabeçalho

Título "Indicadores do Brasil", subtítulo sobre o projeto, link para o repositório
produtor e indicador discreto de disponibilidade da API.

### Cards de panorama

Selic, IPCA e dólar, com unidade, referência e nota "último dado disponível".
IPCA 12 meses pode entrar como quarto card depois do fluxo básico aprovado.
Não mostrar valores fictícios enquanto carrega; usar indicador de carregamento.

### Filtros

- Data inicial e final; padrão de gráfico: últimos doze meses, respeitando 2020+.
- Atalhos: 3 meses, 6 meses, 1 ano, desde 2020; definir meses-calendário.
- Série selecionada e visualização: observações, agregado mensal ou anual, quando aplicável.
- Botão "Aplicar filtros", usando formulário para evitar chamadas a cada alteração.
- Botão "Atualizar dados", que renova consultas do painel sem disparar ETL.

### Gráficos históricos

- Selic: linha em degraus, representando alterações da meta.
- IPCA mensal: barras com zero visível, preservando valores negativos.
- Dólar: linha de observações por data, sem inventar valores em dias sem publicação.
- IPCA 12 meses: linha separada, com lacunas visíveis quando o indicador for inválido.

Mostrar série, unidade, recorte e referência; ordenar pontos antes de desenhar.
Não sobrepor unidades distintas no mesmo eixo. Não usar gráfico de pizza para
séries temporais nem adicionar comparação em base 100 na primeira entrega.

### Tabela e exportação

Tabela dos dados do período, com datas e valores formatados, e download CSV.
CSV deve refletir o conjunto completo do filtro, com referência, unidade e fonte;
não exportar apenas uma página sem avisar. Proteger campos textuais contra fórmulas
ao abrir em planilhas. O arquivo exportado pelo usuário não será versionado.
Valores sintéticos de testes nunca devem aparecer como dados oficiais.

### Fontes, atualização e metodologia

Exibir fonte por indicador: BCB/SGS; para IPCA, produtor IBGE e distribuição BCB.
Separar claramente:

1. **Referência:** data ou mês medido (`ultima_referencia` ou data da observação).
2. **Última consulta da pipeline:** `ultima_consulta`, quando informada.
3. **Última publicação:** `ultima_publicacao` do frescor; gold também possui
   `meta.data_publicacao`, que é data e não deve ganhar horário inventado.
4. **Consulta pelo painel:** instante UTC medido pelo cliente ao obter a resposta;
   não rotular esse instante como atualização da fonte.

Converter timestamps UTC para `America/Sao_Paulo` apenas na exibição. Referências
sem horário continuam datas, sem conversão de fuso. Indicar defasagem e incerteza:
`defasado=null` não significa "atualizado". Na indisponibilidade do frescor, manter
o gráfico se suas próprias consultas funcionarem e mostrar status desconhecido.

## 8. Paginação, cache e falhas

Implementar uma função reutilizável de paginação para as rotas temporais:

1. Resolver período explícito e enviar primeira página.
2. Reutilizar filtros e limite nas páginas seguintes; preservar `meta.de/ate`.
3. Seguir `proximo_cursor` enquanto houver mais páginas.
4. Conferir geração estável por conjunto/rota, ausência de datas duplicadas,
   progresso do cursor e coerência da paginação.
5. Em 409, descartar o conjunto incompleto e reiniciar uma única vez.
6. Se houver nova mudança, interromper com aviso, sem concatenar gerações.

Versões entre rotas core e gold podem diferir; não impor igualdade global entre
camadas. Consultas independentes não formam snapshot atômico do painel inteiro.
Informar `meta.desatualizado` nas visualizações gold.

Configuração inicial proposta: conexão 3 s, leitura 10 s, prazo total de consulta
de 30 s, no máximo 10 páginas/10.000 registros por conjunto. Ao atingir limite,
exibir aviso de resultado incompleto e pedir recorte menor; não declarar card global
ou exportação completa. Não executar consultas paralelas ilimitadas.

Cache em memória no servidor Python com TTL inicial de 300 s e máximo de 64 entradas;
chave inclui URL base, rota, parâmetros e versão de transformação. Usar apenas
dados públicos validados. Não armazenar erro como resposta válida ou retornar
dados antigos silenciosamente. Atualização manual invalida somente os conjuntos
do painel necessários, sem apagar indiscriminadamente cache de outros usuários.

Reutilizar resultados entre cards e gráficos. Não consultar a API em cada hover
ou alteração de controle antes de aplicar o formulário. O limitador atual é por endereço de conexão/processo; usuários
do painel compartilham a identidade de saída do servidor perante a API.
O limite padrão do produtor é 100 requisições/minuto, não uma cota por usuário web.

| Situação | Comportamento |
|---|---|
| 200 vazio | "Não há dados para o período"; sem zero ou exceção de interface |
| 304 | Só usar representação local existente; primeira entrega pode não enviar ETag |
| 404 | Informar recurso/série não encontrado; sem repetição automática |
| 409 | Reinício limitado da paginação, como acima |
| 422 | Mostrar orientação de filtro/contrato, sem repetir pedido inválido |
| 429 | Respeitar `Retry-After`, mostrar aviso e evitar loop |
| 503 / timeout | Indisponibilidade temporária; permitir nova tentativa explícita |
| JSON inválido / contrato incompatível | Erro controlado, sem exibir payload bruto |

No máximo uma repetição de falha transitória por pedido, dentro do prazo total.
Não bloquear a sessão com esperas longas; se `Retry-After` exceder o prazo, orientar
nova tentativa posterior. Erros sanitizados podem mostrar `requisicao_id` para suporte;
nunca mostrar stack trace, credenciais ou cursor completo.

## 9. Estrutura sugerida

```text
painel-indicadores-brasil/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── package.json                    # Scripts npm e dependências frontend
├── package-lock.json
├── frontend/
│   ├── estilos.css                 # Entrada Tailwind
│   └── painel.js                   # JS próprio e inicialização dos gráficos
├── README.md
├── AGENTS.md                       # Convenção pt-BR e operação
├── docs/
│   ├── plano-painel-indicadores-brasil.md
│   ├── contrato-api.md
│   └── sistema-de-design.md        # Decisões verificadas com UI UX Pro Max
├── src/painel_indicadores/
│   ├── __init__.py
│   ├── configuracao.py
│   ├── aplicacao.py                # Factory FastAPI e ciclo de vida do cliente
│   ├── rotas.py                    # Página HTML, CSV, atualização e saúde
│   ├── cliente_api.py               # HTTP, paginação, prazos e erros
│   ├── contratos.py                 # Respostas essenciais tipadas
│   ├── indicadores.py               # Regras puras, Decimal e referências
│   ├── formatacao.py
│   ├── graficos.py
│   ├── pagina.py                   # Modelo de apresentação
│   ├── templates/
│   │   ├── base.html
│   │   ├── painel.html
│   │   └── componentes/            # Cards, filtros, tabela e avisos
│   └── estaticos/                  # CSS/JS gerados e vendor local
├── testes/
│   ├── unidade/
│   ├── interface/
│   └── amostras/                   # Respostas sanitizadas e sua proveniência
└── .github/workflows/qualidade.yml
```

Não criar todas as camadas vazias antecipadamente; introduzir os módulos junto das
entregas correspondentes. Exemplos de identificadores: `ClienteAPI`,
`ConfiguracaoPainel`, `ErroDeConsulta`, `buscar_observacoes`, `percorrer_paginas`,
`obter_ultimo_valor`, `formatar_percentual`, `criar_grafico_selic`.

Todo código próprio, testes, comentários e mensagens em português-BR; identificadores
sem acentos. Manter nomes convencionais e interfaces de terceiros, como `test_`,
classes Tailwind, API Plotly.js, campos JSON, `package.json`, `pyproject.toml`
e `Dockerfile`. JavaScript próprio também usa identificadores em português-BR.

## 10. Configuração e comandos futuros

Exemplo público de `.env.example`, sem segredos:

```dotenv
URL_BASE_API=http://127.0.0.1:8000
TEMPO_CONEXAO_SEGUNDOS=3
TEMPO_LEITURA_SEGUNDOS=10
PRAZO_CONSULTA_SEGUNDOS=30
VALIDADE_CACHE_SEGUNDOS=300
LIMITE_PAGINAS=10
```

Validar HTTP/HTTPS, URL confiável e limites positivos. URL não será controlada por
campo livre na página pública, evitando requisições arbitrárias do servidor.
Não copiar `URL_BANCO_API`, senhas SQL ou `SEGREDO_CURSOR`. O cliente apenas repassa
cursores opacos; não precisa da chave que os assina.

Comandos de referência **após implementar o pacote e sua configuração**:

```powershell
cd D:\painel-indicadores-brasil
uv sync --frozen
npm ci
npm run construir
uv run --frozen uvicorn painel_indicadores.aplicacao:criar_aplicacao --factory --host 127.0.0.1 --port 8501
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
```

Os dois locks serão gerados durante a implementação; `--frozen` e `npm ci`
pressupõem que existam. Configurar a instalação Python do pacote em `src/`. Comandos acima não criam o projeto por si só. Antes, iniciar ou verificar
a API no diretório produtor; não reiniciar seus containers nem regenerar credenciais
automaticamente a partir do painel.

Ignorar `.env`, `.venv/`, `node_modules/`, caches, exports operacionais e logs.
Versionar `.env.example`, fontes CSS/JS e os dois locks; gerar assets no CI/imagem. Arquivos
exportados e amostras reais terão políticas distintas: exportação não vira fixture.

### Construção do frontend e segurança

Instalar `tailwindcss` e `@tailwindcss/cli` em versões compatíveis fixadas no lock.
A entrada CSS usa `@import "tailwindcss";`. Conferir detecção dos templates Jinja e
fontes JS; escrever classes condicionais completas, sem concatenação dinâmica que
escape à geração do CSS. Adotar tokens compatíveis com a versão 4 instalada, sem
copiar configurações antigas da versão 3 automaticamente.

O script npm `construir` gera CSS minificado, copia o JS próprio e prepara a
distribuição Plotly.js fixada para `/estaticos`, preservando licenças. Servir assets
localmente; não depender de CDN ou compilador Tailwind no navegador em produção.
Não é preciso React/Next.js para esta primeira entrega centrada em Python.

Manter autoescape do Jinja. Usar serialização `tojson` apropriada ao contexto dos
dados gráficos; não interpolar payload externo em JS nem usar `safe` para texto
da API. Mensagens externas entram via texto, não `innerHTML`. Nunca incluir segredos
no HTML, JavaScript ou CSS.

O cache Python deve ter controle de concorrência, expiração por relógio monotônico
e limites de memória. Um processo inicialmente; cache e limites em memória não são
globais entre réplicas. O botão de atualização renova dados públicos do painel
com proteção contra chamadas repetidas, sem interferir na pipeline.

## 11. Aparência, acessibilidade e responsividade

Proposta visual inicial: fundo claro, bom contraste, azul para Selic, roxo para
IPCA e verde-azulado para dólar; cores são propostas, verificar contraste na execução.
Evitar depender só de cor: usar rótulos, unidades, símbolos e notas.

Cards em três/quatro colunas no desktop e empilhados no celular. Gráficos com
altura legível, títulos claros, tooltip em pt-BR e tabela equivalente. Filtros
com rótulos visíveis; avisos concisos e compreensíveis. Conferir teclado, zoom,
ausência de rolagem horizontal da página e contraste de texto e controles.
Não esconder o estado de incompletude em tooltip ou em rodapé distante.

## 12. Testes e critérios de aceite

Testes automatizados não dependem de API externa, de PostgreSQL ou da API local
ligada. Usar `httpx.MockTransport`, fixtures identificadas e cliente substituível
na interface. Dados sintéticos de falha ficam explicitamente identificados como
teste, sem sobrescrever resposta oficial arquivada.

Cobrir os seguintes cenários:

- Conversão Decimal, formatação pt-BR e diferenças em pontos percentuais.
- Última observação distinta do fim do filtro; mês IPCA e feriados do dólar.
- IPCA negativo, valor zero legítimo, ausência, `null` e período sem dados.
- Mais de uma página, cursor repetido, mudança de geração e reinício limitado.
- Vazio, JSON inválido, 409, 422, 429 com `Retry-After`, 503 e timeout.
- IPCA 12m incompleto, gold desatualizada e cobertura desconhecida.
- Filtros invertidos/futuros e prazo/paginação máximos.
- Falha em uma série sem apagar as demais; falha de frescor sem inventar status.
- Cache por parâmetros/servidor e atualização manual sem nova coleta ETL.
- CSV completo, proveniência e proteção contra fórmulas em campos textuais.
- Página com todos os dados, carregamento, vazio e falha por TestClient, complementada por Playwright no navegador.

Smoke manual separado, com API real: catálogo, três séries, paginação, IPCA 12m,
frescor, filtros e download, sem alterar dados da pipeline. Registrar data, versão
do contrato e resultado; não afirmar equivalência com teste offline.

Aceite da primeira entrega:

- [ ] Três cards corretos com unidade e referência explícitas.
- [ ] Gráficos históricos e filtros funcionais, sem dados fabricados.
- [ ] Últimos valores globais e métricas filtradas claramente separados.
- [ ] Fonte, consulta do painel e frescor distinguíveis.
- [ ] Paginação completa ou incompletude comunicada, nunca silenciosa.
- [ ] Falhas tratadas, sem segredos ou stack trace.
- [ ] CSV reproduz o filtro aplicado.
- [ ] Layout Tailwind conferido no desktop e no celular, incluindo CSS de produção.
- [ ] UI UX Pro Max efetivamente consultada e sistema de design registrado.
- [ ] Build npm reproduzível; assets locais e sem credenciais no HTML/JS.
- [ ] Testes, lint e tipos aprovados; instalação reproduzida pelo lock.
- [ ] Nenhum acesso direto ao banco, escrita ou disparo de ETL.
- [ ] README documenta inicialização dos dois projetos e limites conhecidos.

## 13. Etapas de execução

Estimativa inicial para dedicação de 2–4 horas semanais; ajustar após a primeira
entrega. Não são datas prometidas. Cada etapa encerra com demonstração verificável.

| Etapa | Trabalho | Evidência | Esforço proposto |
|---|---|---|---|
| P1 | Ambiente Python/npm, catálogo e preparação da UI UX Pro Max | Locks reproduzíveis; cliente testado; sistema de design registrado após executar a skill | 3–5 h |
| P2 | Cliente paginado, contratos e regras dos cards | Testes de múltiplas páginas, Decimal e falhas; três cards reais | 3–5 h |
| P3 | Templates Tailwind, Plotly.js, filtros e estados | TestClient, Playwright e comparação com a API | 4–6 h |
| P4 | Frescor, cache, IPCA 12m e CSV | Incompletude, invalidação e exportação testadas | 3–5 h |
| P5 | Responsividade, documentação e CI próprio | Navegador desktop/celular e workflow executado | 2–4 h |

Total orientativo revisado: 15–25 horas, aproximadamente 4–13 semanas no ritmo informado.
Escrever regressões para falhas importantes antes da implementação, executar
verificações da etapa e fazer commits pequenos com mensagens em português.
Não publicar repositório ou criar recursos de nuvem automaticamente.

## 14. Evoluções opcionais

Depois da primeira entrega: seção de população IBGE, comparação territorial,
gráficos exportáveis e narrativas descritivas. Rotas já existentes incluem
`/api/v1/ufs`, `/api/v1/regioes`, `/api/v1/municipios`,
`/api/v1/municipios/{codigo_ibge}/populacao` e `/api/v1/populacao/brasil`.
Conferir filtros e contratos próprios em `ibge.py`/OpenAPI; não reutilizar parâmetros
BCB por suposição. Preservar lacunas de 2022/2023 no agregado populacional usado,
marcadores, revisões territoriais e totais derivados incompletos.

Exportação PNG/PDF de infográficos será uma etapa distinta; só adicionar ferramentas
como Kaleido após validar dependências de renderização e disponibilidade do navegador.
O MVP entrega visualização interativa e CSV, sem prometer exportação estática.

Na futura Oracle Cloud, validar orçamento e memória considerando API, PostgreSQL,
orquestração, monitoramento e servidor do painel na mesma infraestrutura.
Construir CSS/JS antes da execução; configurar HTTPS, proxy, limites e acesso privado. Não expor
a porta 8501 ou painéis de infraestrutura diretamente sem desenho de publicação.
A API local não fica acessível a uma hospedagem externa por usar `localhost`.

## 15. Instrução para iniciar outra sessão

Copiar este arquivo para `D:\painel-indicadores-brasil\docs\` e abrir a nova pasta
como workspace. A pasta da pipeline permanece sendo o projeto produtor.

> Implemente o painel conforme `docs/plano-painel-indicadores-brasil.md`, começando
> pela etapa P1. Use Python 3.12, FastAPI, Jinja2, Tailwind CSS 4, Plotly.js e httpx
> síncrono, com uv e npm e locks próprios. Disponibilize e leia a skill UI UX Pro Max
> antes da etapa visual; se ela estiver ausente, registre o impedimento sem simular uso.
> Consulte o OpenAPI da API existente, sem copiar credenciais ou acessar PostgreSQL.
> Todo código próprio e documentação devem seguir português-BR. Preserve cursores,
> Decimals, cobertura e datas conforme o contrato. Não modifique a pipeline nem
> publique recursos automaticamente. Valide cada entrega antes de declará-la pronta.

## 16. Referências técnicas

- [FastAPI: templates Jinja2](https://fastapi.tiangolo.com/advanced/templates/).
- [Tailwind CSS: construção pela CLI](https://tailwindcss.com/docs/installation/tailwind-cli).
- [Plotly.js: instalação e uso](https://plotly.com/javascript/getting-started/).
- [UI UX Pro Max: projeto de origem](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
- Contrato produtor: `D:\pipeline-etl\src\pipeline_etl\api\` e OpenAPI da instância escolhida.

As políticas numéricas de cache, timeouts, paginação e esforço deste plano são
decisões propostas do projeto, não garantias ou limites oficiais das bibliotecas.
