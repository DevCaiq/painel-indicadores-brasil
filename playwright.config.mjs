import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import path from "node:path";

export default defineConfig({
  globalSetup: "./testes/navegador/iniciar-servidor.mjs",
  testDir: "./testes/navegador",
  testMatch: "**/*.spec.mjs",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 30000,
  expect: { timeout: 7000 },
  reporter: "line",
  outputDir: path.join(tmpdir(), "painel-indicadores-playwright", String(process.pid)),
  use: {
    baseURL: "http://127.0.0.1:8503",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "firefox", use: { browserName: "firefox" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
});
