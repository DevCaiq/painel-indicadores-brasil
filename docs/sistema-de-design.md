# Sistema de design — Indicadores do Brasil

Definido em 23/11/2026 para FastAPI, Jinja2, Tailwind CSS 4 e Plotly.js. Referência de implementação para P3; não representa uma interface já renderizada ou aprovada em navegador.

## Origem e decisões

Skill efetivamente lida e executada: `.agents/skills/ui-ux-pro-max/SKILL.md`. Consultas locais realizadas com Python, sem enviar dados do projeto a serviços externos:

```powershell
python .agents/skills/ui-ux-pro-max/scripts/search.py "economic indicators dashboard accessible" --design-system -p "Indicadores do Brasil"
python .agents/skills/ui-ux-pro-max/scripts/search.py "public data analytics dashboard light" --design-system -p "Indicadores do Brasil"
python .agents/skills/ui-ux-pro-max/scripts/search.py "responsive form dashboard" --stack html-tailwind
python .agents/skills/ui-ux-pro-max/scripts/search.py "responsive" --stack html-tailwind
python .agents/skills/ui-ux-pro-max/scripts/search.py "time series missing data" --domain chart
python .agents/skills/ui-ux-pro-max/scripts/search.py "bar comparison negative" --domain chart
```

As consultas de sistema recomendaram Minimalism & Swiss Style e Data-Dense Dashboard, com hierarquia tipográfica, cards, gráficos e tabela. Adotamos a clareza do primeiro e os componentes do segundo, com espaço confortável. A segunda consulta trouxe fundo #F8FAFC, superfície branca, azul #1E40AF e texto secundário #475569, coerentes com o plano.

Os padrões de landing page comercial (hero, vendas, logos e CTA comercial) retornados não correspondem ao produto e foram descartados. A primeira paleta escura e o verde associado a alta positiva também foram descartados: o plano exige fundo claro e neutralidade econômica. Não persistimos a saída automática como fonte de verdade; este documento contém apenas recomendações conferidas e decisões adaptadas ao projeto.

As duas buscas html-tailwind não retornaram resultados, incluindo a tentativa mais ampla. Não há orientação específica dessa base confirmada para a stack; as decisões abaixo seguem o plano e as regras gerais da skill. A busca de barras trouxe comparação categórica; sua sugestão de ordenar por valor não se aplica à cronologia do IPCA. As recomendações de outras bibliotecas não substituem Plotly.js.

## Direção e organização

Dashboard público em português-BR, sóbrio e legível, com dados como prioridade. Sem hero promocional, navegação lateral, gradientes decorativos ou animação de valores. Uma página, nesta ordem:

1. Cabeçalho com título, contexto, link do produtor e disponibilidade técnica.
2. Três cards: Selic, IPCA mensal e dólar; nota visível de que mostram o último dado global disponível, independente do filtro.
3. Formulário de filtros e botão primário “Aplicar filtros”.
4. Histórico da série selecionada, seguido das métricas do período.
5. Tabela equivalente e ação secundária “Baixar CSV”.
6. Fontes, referências, frescor e metodologia.

“Atualizar dados” é ação secundária e não pode prometer nova coleta. IPCA 12m entra posteriormente sem reorganizar a prioridade das três séries principais.

## Tokens de cor e contraste

Valores opacos, sem redução por opacity para texto. Contrastes calculados com Python pela luminância relativa sRGB: linearizar os canais, ponderar por 0,2126/0,7152/0,0722 e aplicar `(Lmaior + 0,05) / (Lmenor + 0,05)`. Valores arredondados a duas casas. Meta: texto normal >=4,5:1 e controles/dados significativos >=3:1. Não é declaração de conformidade da página futura.

| Token semântico | Cor | Par validado | Contraste |
|---|---|---|---:|
| fundo | #F8FAFC | texto principal #0F172A | 17,06:1 |
| superficie | #FFFFFF | texto principal #0F172A | 17,85:1 |
| texto-secundario | #475569 | branco / fundo | 7,58:1 / 7,24:1 |
| acao / foco | #1E40AF | texto branco / fundo branco | 8,72:1 |
| acao-hover | #1E3A8A | texto branco | 10,36:1 |
| borda-controle | #64748B | branco | 4,76:1 |
| serie-selic | #1D4ED8 | branco | 6,70:1 |
| serie-ipca | #7E22CE | branco | 6,98:1 |
| serie-dolar | #0F766E | branco | 5,47:1 |
| aviso-texto / aviso-fundo | #92400E / #FFFBEB | entre si | 6,84:1 |
| erro-texto / erro-fundo | #991B1B / #FEF2F2 | entre si | 7,60:1 |
| disponivel-texto / disponivel-fundo | #166534 / #F0FDF4 | entre si | 6,81:1 |
| informacao-texto / informacao-fundo | #1E40AF / #EFF6FF | entre si | 8,01:1 |

Divisórias decorativas: #E2E8F0, sem carregar informação ou delimitar sozinhas campos. Controles usam borda-controle. Gráficos sempre em superfície branca. Disponibilidade verde significa resposta técnica da API, nunca melhoria econômica ou dados completos. Variações econômicas usam texto neutro, sinal e unidade; nunca somente cor.

Na implementação, mapear tokens a variáveis CSS com nomes sem acentos; usar `@theme`/variáveis compatíveis com Tailwind 4 e classes completas nos templates. Não adicionar cores arbitrárias por componente.

## Tipografia, espaço e dimensões

A skill sugeriu Fira Sans/Fira Code. Decisão para o MVP: usar `system-ui, -apple-system, "Segoe UI", sans-serif`, sem fontes remotas ou nova dependência. Valores usam `font-variant-numeric: tabular-nums`; monospace apenas em identificadores técnicos quando necessário.

Corpo 16 px, entrelinha 1,5; auxiliares 14 px; títulos de seção 20–24 px; título da página 28–36 px; valores dos cards 28–36 px, com quebra responsiva. Peso 400 no corpo, 600 em rótulos/títulos, 700 nos valores. Textos explicativos até 70 caracteres por linha.

Escala de espaçamento: 4, 8, 12, 16, 24, 32 e 48 px. Cards com padding de 24 px, raio de 12 px e borda decorativa; inputs/botões com raio de 8 px. Sem sombra pesada. Controles com altura mínima de 44 CSS px e distância de pelo menos 8 px entre alvos.

Conteúdo centralizado, largura máxima de 1280 px. Margens laterais de 16 px no celular, 24 px a partir de 768 px e 32 px a partir de 1024 px. Cards em uma coluna abaixo de 768 px, duas até 1023 px e três a partir de 1024 px. Quarto card futuro permite quatro colunas somente a partir de 1280 px. Formulário empilhado no celular e com quebra de linha no desktop.

## Componentes e estados

| Componente | Especificação |
|---|---|
| Card | Nome, valor, unidade, referência e nota “Último dado disponível”. Ausência vira “Indisponível”, nunca zero. Incompletude aparece no próprio card. |
| Filtros | Labels visíveis associados aos campos. Datas e série preservadas após erro. Validação inline; resumo com links para campos quando houver vários erros. Não consultar a cada alteração. |
| Botões | Primário azul com texto branco, hover azul escuro; secundário branco com texto azul e borda visível. Foco com contorno de 3 px e offset de 2 px sobre superfície clara. |
| Carregamento | No envio do formulário, feedback textual “Consultando dados…” e proteção contra envio repetido. Sem dados fictícios. Na primeira resposta SSR, não prometer skeleton antes do HTML; placeholder só em consultas posteriores implementadas por JS. |
| Vazio | “Não há dados para o período”, com orientação para ajustar o filtro; sem eixos vazios ou zeros artificiais. |
| Erro | Aviso próximo à área afetada e nova tentativa explícita. Não apagar séries independentes nem exibir payload bruto, stack trace ou cursor. |
| Incompleto | Aviso âmbar persistente antes do gráfico/tabela; explicar limite ou motivo. Não rotular último valor parcial como global. |
| Frescor desconhecido | Texto “Atualização da fonte desconhecida”. A disponibilidade técnica continua separada. |
| Tabela | Caption, cabeçalhos semânticos, data legível, unidade explícita e valores alinhados à direita. Paginação da tabela não limita silenciosamente o CSV. |

Atualizações de estado por JS usam região `role="status"` apropriada, sem mover foco a cada resposta; falhas de formulário podem focar o resumo após envio. Não tornar o card inteiro clicável sem finalidade.

## Gráficos e dados

Preservar Plotly.js local. Títulos e eixos com unidade, tooltip em pt-BR, ordenação cronológica e tabela acessível equivalente. Uma unidade por gráfico; rótulo textual identifica a série independentemente da cor.

- Selic: linha em degraus, sem suavização que invente metas intermediárias.
- IPCA mensal: barras, zero visível e valores negativos preservados; não ordenar por valor.
- Dólar: linha nas datas observadas, sem criar observações de fins de semana/feriados.
- IPCA 12m: gráfico separado; lacunas nos períodos inválidos, sem conectar sobre valores nulos.

Não confundir dias sem publicação com falhas conhecidas: não inferir calendário homologado. Não interpolar IPCA nem transformar ausência em zero. Alertas de cobertura vêm do contrato.

Altura alvo de 320 px no celular e 400 px no desktop, ajustável para rótulos. Reduzir ticks no celular sem descartar silenciosamente registros. Não aplicar automaticamente a recomendação genérica da skill de amostragem acima de mil pontos; preservar o conjunto validado e avaliar desempenho antes de introduzir redução visual explícita. Tabela e CSV mantêm o recorte completo.

Zoom/restauração devem ter alternativa operável por teclado; detalhes essenciais disponíveis na tabela, sem depender de hover ou dos controles internos do Plotly. Animações de entrada dos gráficos desativadas.

## Responsividade e acessibilidade a verificar na P3/P5

Planejar viewport em 375, 768, 1024 e 1440 px, além de reflow em 320 CSS px e zoom de 200%. Nenhuma rolagem horizontal da página; a tabela pode ter região própria identificada caso não caiba. Unidades, mensagens e botões não podem ser cortados.

HTML semântico com `lang="pt-BR"`, link “Pular para o conteúdo”, um h1, hierarquia de títulos, labels, foco visível e navegação por teclado. Ícones SVG consistentes, decorativos com `aria-hidden`; controles mantêm nome acessível. Não usar emoji como ícone.

Transições opcionais somente de cor/opacity, até 150 ms e desativadas com `prefers-reduced-motion`. Sem contagem animada de números, parallax ou alteração automática do período.

Critérios de P3/P5: validar teclado, feedback acessível, contraste dos estados compostos, tabela/CSV equivalentes e ausência de erros de execução no navegador com CSS de produção. A suíte P5 cobre Chromium, Firefox e WebKit, com CSS de produção em 320, 375, 768, 1024 e 1440 px, texto a 200%, axe e inspeção da árvore acessível. Leitor de tela humano e dispositivos físicos permanecem pendentes; WebKit automatizado não equivale a Safari físico.

## Situação da P1

Skill consultada e sistema de design registrado com contrastes calculados. Pendência de instalação encerrada. P1 concluída no escopo de preparação; implementação e validação visual pertencem a P3/P5. IPCA 12m, atualização manual e CSV continuam nas etapas previstas no plano principal.

## Integração P4

Quarto card IPCA em 12 meses na mesma família visual, identificado como composto (não inventar código SGS). Grade de quatro colunas a partir de 1280 px, duas em tablet, uma no celular. Falha da gold mantém o card indisponível e os demais indicadores preservados.

Filtros incluem observações/agregado mensal/anual; o gráfico anual de IPCA identifica a inflação composta e mantém períodos inválidos como lacunas. O gráfico de IPCA12m fica em seção separada com controles de zoom e tabela próprios. Tabelas gold mostram condição e motivo de cada período; a rolagem horizontal fica restrita à região identificada da tabela quando necessária no celular.

“Atualizar dados” é ação secundária POST para renovar a página aplicada, com proteção de origem/CSRF e intervalo mínimo. Downloads CSV são ações secundárias de cada conjunto completo; dados incompletos não oferecem download como completo. Fonte, referência, última consulta/publicação da pipeline, consulta do painel e geração da página ficam diferenciadas.
