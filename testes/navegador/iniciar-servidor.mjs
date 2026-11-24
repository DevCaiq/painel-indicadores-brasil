import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { setTimeout as esperar } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

export default async function iniciarServidor() {
  const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
  const python = path.join(raiz, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  // Não reutilizar nem encerrar um processo que já pertence ao usuário.
  await new Promise((resolver, rejeitar) => {
    const sondagem = createServer();
    sondagem.once("error", rejeitar);
    sondagem.listen(8503, "127.0.0.1", () => sondagem.close(resolver));
  });
  // Spawn direto evita um cmd intermediário que deixa o Python órfão no Windows.
  const processo = spawn(python, ["-m", "uvicorn", "testes.apoio.servidor:criar_aplicacao_teste", "--factory", "--host", "127.0.0.1", "--port", "8503"], {
    cwd: raiz, shell: false, windowsHide: true,
    env: { ...process.env, URL_BASE_API: "http://127.0.0.1:9" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let saida = "";
  let erroInicial = null;
  processo.on("error", (erro) => { erroInicial = erro; });
  for (const canal of [processo.stdout, processo.stderr]) {
    canal.on("data", (dados) => { saida = (saida + dados.toString()).slice(-8192); });
  }
  async function encerrar() {
    if (processo.exitCode !== null || processo.signalCode !== null) return;
    const encerrado = new Promise((resolver) => processo.once("exit", () => resolver(true)));
    processo.kill("SIGTERM");
    if (!await Promise.race([encerrado, esperar(2000, false, { ref: false })])) {
      processo.kill("SIGKILL");
      await encerrado;
    }
  }
  try {
    const limite = Date.now() + 20000;
    while (Date.now() < limite) {
      if (erroInicial) throw erroInicial;
      if (processo.exitCode !== null) throw new Error(`Servidor de teste encerrou: ${saida}`);
      try {
        const resposta = await fetch("http://127.0.0.1:8503/health", { signal: AbortSignal.timeout(500) });
        await resposta.arrayBuffer();
        if (resposta.ok && resposta.headers.get("x-dados-teste") === "sinteticos") return encerrar;
      } catch { /* O processo ainda pode estar iniciando. */ }
      await esperar(100);
    }
    throw new Error(`Servidor de teste não iniciou no prazo: ${saida}`);
  } catch (erro) {
    await encerrar();
    throw erro;
  }
}
