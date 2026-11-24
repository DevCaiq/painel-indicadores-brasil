"use strict";

const formulario = document.getElementById("formulario-filtros");
const aplicar = document.getElementById("aplicar-filtros");
const estado = document.getElementById("estado-consulta");

function restaurarFormulario() {
  if (!formulario || !aplicar || !estado) return;
  formulario.removeAttribute("aria-busy");
  aplicar.disabled = false;
  aplicar.textContent = "Aplicar filtros";
  estado.textContent = "";
}

formulario?.addEventListener("submit", (evento) => {
  if (formulario.getAttribute("aria-busy") === "true") {
    evento.preventDefault();
    return;
  }
  formulario.setAttribute("aria-busy", "true");
  aplicar.disabled = true;
  aplicar.textContent = "Consultando…";
  estado.textContent = "Consultando dados…";
});
window.addEventListener("pageshow", restaurarFormulario);
document.querySelector("[data-focar-erro]")?.focus();
// Âncoras para inputs de data não recebem foco de modo uniforme nos navegadores.
document.querySelectorAll('#erros-filtro a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (evento) => {
    const campo = document.getElementById(link.hash.slice(1));
    if (!campo) return;
    evento.preventDefault();
    campo.focus();
    campo.scrollIntoView({ block: "center" });
  });
});

async function iniciarGrafico(dadosId, graficoId) {
  const dados = document.getElementById(dadosId);
  const grafico = document.getElementById(graficoId);
  if (!dados || !grafico) return;
  const secao = grafico.closest("section");
  const controles = secao.querySelector(".controles-grafico");
  try {
    if (!window.Plotly) throw new Error("Biblioteca de gráficos indisponível");
    const especificacao = JSON.parse(dados.textContent);
    window.Plotly.register({
      moduleType: "locale", name: "pt-BR", dictionary: {},
      format: {
        days: ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"],
        shortDays: ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"],
        months: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
        shortMonths: ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
        decimal: ",", thousands: ".", grouping: [3], date: "%d/%m/%Y",
      },
    });
    if (window.matchMedia("(max-width: 767px)").matches) {
      especificacao.layout.xaxis.nticks = 4;
      especificacao.layout.margin.l = 58;
      especificacao.layout.margin.r = 8;
    }
    await window.Plotly.newPlot(grafico, especificacao.data, especificacao.layout, especificacao.config);
    controles.hidden = false;
    for (const botao of controles.querySelectorAll("[data-zoom]")) {
      botao.addEventListener("click", async () => {
        const faixa = grafico._fullLayout.xaxis.range.map((valor) => {
          const texto = String(valor).replace(" ", "T");
          // O eixo Plotly é UTC; não interpretar datas sem fuso como hora local.
          return Date.parse(texto.length === 10 ? `${texto}T00:00:00Z` : texto.endsWith("Z") ? texto : `${texto}Z`);
        });
        const centro = (faixa[0] + faixa[1]) / 2;
        const metade = (faixa[1] - faixa[0]) * Number(botao.dataset.zoom) / 2;
        await window.Plotly.relayout(grafico, {
          "xaxis.range": [new Date(centro - metade).toISOString(), new Date(centro + metade).toISOString()],
          "xaxis.autorange": false,
        });
      });
    }
    controles.querySelector("[data-restaurar]").addEventListener("click", () => {
      window.Plotly.relayout(grafico, { "xaxis.autorange": true, "yaxis.autorange": true });
    });
  } catch {
    grafico.hidden = true;
    if (controles) controles.hidden = true;
    secao.querySelector("[data-erro-grafico]").hidden = false;
  }
}

iniciarGrafico("dados-grafico", "grafico");
iniciarGrafico("dados-ipca12", "grafico-ipca12");

const atualizacao = document.getElementById("formulario-atualizacao");
const atualizar = document.getElementById("atualizar-dados");
const estadoAtualizacao = document.getElementById("estado-atualizacao");
atualizacao?.addEventListener("submit", (evento) => {
  if (atualizacao.getAttribute("aria-busy") === "true") {
    evento.preventDefault();
    return;
  }
  atualizacao.setAttribute("aria-busy", "true");
  atualizar.disabled = true;
  estadoAtualizacao.textContent = "Renovando consultas…";
});
window.addEventListener("pageshow", () => {
  atualizacao?.removeAttribute("aria-busy");
  if (atualizar) atualizar.disabled = false;
  if (estadoAtualizacao) estadoAtualizacao.textContent = "";
});
