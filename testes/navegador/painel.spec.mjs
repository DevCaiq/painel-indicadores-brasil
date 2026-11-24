import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const recorte = "/?codigo=432&de=2026-01-01&ate=2026-03-31";
const pastaCapturas = path.join(tmpdir(), "painel-p5-capturas");

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (erro) => { throw erro; });
});

test("carrega quatro cards e preserva lacuna no gráfico composto", async ({ page }) => {
  const resposta = await page.goto(recorte);
  expect(resposta.status()).toBe(200);
  expect(resposta.headers()["x-dados-teste"]).toBe("sinteticos");
  await expect(page.getByRole("status", { name: "Ambiente de testes" })).toContainText("dados sintéticos");
  await expect(page).toHaveTitle(/Indicadores do Brasil/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Indicadores do Brasil");
  await expect(page.locator(".card-indicador")).toHaveCount(4);
  const arvore = await page.locator("#conteudo").ariaSnapshot();
  expect(arvore).toContain('region "Panorama econômico"');
  expect(arvore).toContain('combobox "Indicador"');
  expect(arvore).toContain('button "Aplicar filtros"');
  await expect(page.locator("main")).not.toContainText("CORE_NOVO");
  await expect(page.locator("main")).not.toContainText("SEM_CALENDARIO");
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
  expect(await page.locator("#grafico-ipca12").evaluate((grafico) => grafico.data[0].y)).toEqual([4, null, 4.5]);
  expect(await page.locator("#grafico-ipca12").evaluate((grafico) => grafico.data[0].connectgaps)).toBe(false);
});

test("filtros mudam o gráfico sem alterar os últimos globais", async ({ page }) => {
  await page.goto(recorte);
  const valores = await page.locator(".valor-card").allTextContents();
  await page.getByLabel("Indicador", { exact: true }).selectOption("433");
  await page.getByLabel("Data final", { exact: true }).fill("2026-02-28");
  expect(page.url()).toContain("codigo=432");
  await page.getByRole("button", { name: "Aplicar filtros", exact: true }).click();
  await expect(page).toHaveURL(/codigo=433/);
  await expect(page.locator("#grafico")).toHaveClass(/js-plotly-plot/);
  expect(await page.locator(".valor-card").allTextContents()).toEqual(valores);
  expect(await page.locator("#grafico").evaluate((grafico) => grafico.data[0].y)).toEqual([0, -0.12]);
  await page.goBack();
  await expect(page.locator("#aplicar-filtros")).toBeEnabled();
});

test("CSV contém o recorte inteiro apesar da página da tabela", async ({ page }) => {
  await page.goto("/?codigo=432&de=2026-01-01&ate=2026-01-31&pagina=2");
  await expect(page.locator(".tabela-dados tbody tr")).toHaveCount(6);
  const promessa = page.waitForEvent("download");
  await page.getByRole("link", { name: "Baixar CSV completo", exact: true }).click();
  const download = await promessa;
  const conteudo = await readFile(await download.path());
  expect([...conteudo.subarray(0, 3)]).toEqual([239, 187, 191]);
  expect(conteudo.toString("utf8").trimEnd().split("\r\n")).toHaveLength(32);
  expect(conteudo.toString("utf8")).toContain("2026-01-31");
});

test("períodos parciais mantêm tabela sem desenhar eixos vazios", async ({ page }) => {
  await page.goto("/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-03-31");
  await expect(page.locator("#dados-grafico")).toHaveCount(0);
  await expect(page.getByText("Não há valores completos para desenhar neste recorte. Consulte a condição dos períodos na tabela.", { exact: true })).toBeVisible();
  await expect(page.locator(".tabela-dados")).toContainText("Período em andamento");
  await expect(page.locator(".tabela-dados")).toContainText("Indisponível");
});

test("resumo de erro recebe foco e relaciona os campos corretos", async ({ page }) => {
  const resposta = await page.goto("/?codigo=433&de=2026-03-01&ate=2026-01-01");
  expect(resposta.status()).toBe(422);
  await expect(page.locator("#erros-filtro")).toBeFocused();
  await expect(page.locator("#codigo")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#de")).toHaveAttribute("aria-describedby", "erro-de");
  await page.locator('#erros-filtro a[href="#de"]').click();
  await expect(page.locator("#de")).toBeFocused();
});

test("teclado opera zoom independente e link de pular conteúdo", async ({ page }) => {
  await page.goto(recorte);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Pular para o conteúdo", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#conteudo")).toBeFocused();
  await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
  const principal = await page.locator("#grafico").evaluate((grafico) => grafico._fullLayout.xaxis.range);
  const secundario = await page.locator("#grafico-ipca12").evaluate((grafico) => grafico._fullLayout.xaxis.range);
  await page.getByRole("button", { name: "Aproximar gráfico de IPCA em 12 meses", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => page.locator("#grafico-ipca12").evaluate((grafico) => grafico._fullLayout.xaxis.range)).not.toEqual(secundario);
  expect(await page.locator("#grafico").evaluate((grafico) => grafico._fullLayout.xaxis.range)).toEqual(principal);
  await page.locator(".detalhes-ipca summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Tabela de IPCA em 12 meses", exact: true })).toBeVisible();
});

test("acessibilidade automatizada de conteúdo e validação", async ({ page }) => {
  for (const endereco of [recorte, "/?codigo=433&visualizacao=ano&de=2026-01-01&ate=2026-03-31", "/?de=2026-03-01&ate=2026-01-01"]) {
    await page.goto(endereco);
    const auditoria = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(auditoria.violations).toEqual([]);
  }
});

test("layout e texto ampliado não criam rolagem horizontal da página", async ({ page }, informacoes) => {
  await mkdir(pastaCapturas, { recursive: true });
  for (const largura of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width: largura, height: 1000 });
    await page.goto(recorte);
    await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if ([375, 1440].includes(largura)) {
      await page.screenshot({ path: path.join(pastaCapturas, `${informacoes.project.name}-${largura}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 320, height: 1000 });
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("sem JavaScript ou Plotly os valores continuam acessíveis", async ({ page, browser }) => {
  await page.route("**/vendor/plotly.min.js", (rota) => rota.abort());
  await page.goto(recorte);
  await expect(page.locator("#erro-grafico")).toBeVisible();
  await expect(page.locator(".tabela-dados table")).toBeVisible();
  const contexto = await browser.newContext({ javaScriptEnabled: false });
  const semJavaScript = await contexto.newPage();
  await semJavaScript.goto("http://127.0.0.1:8503" + recorte);
  await expect(semJavaScript.locator(".tabela-dados table")).toBeVisible();
  await expect(semJavaScript.locator("noscript p").first()).toBeVisible();
  await contexto.close();
});

test("POST de atualização é limitado e mantém o filtro", async ({ page, browserName }) => {
  test.skip(browserName !== "chromium", "A reserva é por processo; o fluxo POST completo é verificado uma vez.");
  await page.goto(recorte);
  let promessa = page.waitForResponse((resposta) => resposta.url().endsWith("/atualizar"));
  await page.getByRole("button", { name: "Atualizar dados", exact: true }).click();
  expect((await promessa).status()).toBe(303);
  await expect(page.locator("#de")).toHaveValue("2026-01-01");
  await expect(page.locator("#atualizar-dados")).toBeEnabled();
  promessa = page.waitForResponse((resposta) => resposta.url().endsWith("/atualizar"));
  await page.getByRole("button", { name: "Atualizar dados", exact: true }).click();
  expect((await promessa).status()).toBe(429);
  await expect(page.getByText("Aguarde alguns instantes antes de atualizar os dados novamente.", { exact: true })).toBeVisible();
});
