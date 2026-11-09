/* ORIS - Dashboard integrado do banco (Etapa 06). Busca /bd/dashboard/dados com os filtros. */
(function () {
    const form = document.getElementById("filtros");
    const kpis = document.getElementById("kpis");
    const painel = document.getElementById("painel");
    const alerta = document.getElementById("alerta");
    const PAL = (window.OrisCharts && OrisCharts.PALETA) || ["#18B7B0", "#155E75", "#E9A23B", "#39C6D3", "#0B2A4A", "#8FA3AD"];
    const COR_CLASS = { CRITICA: "#D9534F", ATENCAO: "#E9A23B", ADEQUADA: "#39A96B", SEM_EQUIPAMENTO: "#8FA3AD" };
    const NOME_CLASS = { CRITICA: "Crítica", ATENCAO: "Atenção", ADEQUADA: "Adequada", SEM_EQUIPAMENTO: "Sem equipamento" };
    const graficos = {};
    let contador = 0;

    const brl = v => Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    const num = v => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("pt-BR");
    const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    function desenhar(id, config) {
        if (graficos[id]) graficos[id].destroy();
        graficos[id] = new Chart(document.getElementById(id), config);
    }

    function tile(titulo, valor, sub) {
        return `<div class="dbd-kpi"><small>${esc(titulo)}</small><strong>${valor}</strong><span class="dbd-sub">${sub || "&nbsp;"}</span></div>`;
    }

    function renderKpis(k) {
        let tend = "";
        if (k.tendencia_manutencoes !== null && k.tendencia_manutencoes !== undefined) {
            const t = k.tendencia_manutencoes;
            tend = `<span class="${t > 0 ? "dbd-up" : "dbd-down"}">${t > 0 ? "▲" : "▼"} ${Math.abs(t)}% vs. mês anterior</span>`;
        }
        kpis.innerHTML =
            tile("Unidades", num(k.unidades), `${num(k.unidades_criticas)} em situação crítica`) +
            tile("Serviços ativos", num(k.servicos_ativos)) +
            tile("Equipamentos", num(k.equipamentos), k.pct_operantes === null ? "" : `${num(k.pct_operantes)}% operantes`) +
            tile("Manutenções no período", num(k.manutencoes), `${num(k.manutencoes_abertas)} abertas · ${tend || "sem tendência"}`) +
            tile("Custo total", brl(k.custo_total), `média por concluída: ${k.custo_medio === null ? "—" : brl(k.custo_medio)}`) +
            tile("Duração média", k.dias_medios === null ? "—" : `${num(k.dias_medios)} dias`, "por manutenção");
    }

    function vazio(id, ok) {
        const el = document.getElementById(id).parentElement;
        let aviso = el.querySelector(".dbd-vazio");
        if (!ok && !aviso) {
            aviso = document.createElement("p");
            aviso.className = "dbd-vazio text-muted small position-absolute top-50 start-50 translate-middle";
            aviso.textContent = "Sem dados para os filtros.";
            el.appendChild(aviso);
        }
        if (ok && aviso) aviso.remove();
    }

    function renderGraficos(d) {
        const c = d.classificacao;
        vazio("g-class", c.rotulos.length);
        desenhar("g-class", { type: "doughnut", data: { labels: c.rotulos.map(r => NOME_CLASS[r] || r),
            datasets: [{ data: c.total, backgroundColor: c.rotulos.map((r, i) => COR_CLASS[r] || PAL[i % PAL.length]), borderWidth: 2 }] },
            options: { cutout: "55%", plugins: { legend: { position: "bottom" } } } });

        const m = d.mensal;
        vazio("g-mensal", m.rotulos.length);
        desenhar("g-mensal", { data: { labels: m.rotulos, datasets: [
            { type: "bar", label: "Manutenções", data: m.qtd, backgroundColor: "#18B7B0", borderRadius: 4, yAxisID: "y" },
            { type: "line", label: "Custo (R$)", data: m.custo, borderColor: "#0B2A4A", backgroundColor: "#0B2A4A", tension: .3, yAxisID: "y1" }] },
            options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Qtd" } },
                y1: { position: "right", beginAtZero: true, grid: { display: false }, title: { display: true, text: "R$" } } } } });

        const e = d.equip_por_tipo;
        vazio("g-equip", e.rotulos.length);
        desenhar("g-equip", { type: "bar", data: { labels: e.rotulos, datasets: [
            { label: "Ativos", data: e.ativos, backgroundColor: "#39A96B", borderRadius: 4 },
            { label: "Inativos", data: e.inativos, backgroundColor: "#8FA3AD", borderRadius: 4 }] },
            options: { indexAxis: "y", scales: { x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }, y: { stacked: true } } } });

        const t = d.top_unidades_custo;
        vazio("g-top", t.rotulos.length);
        desenhar("g-top", { type: "bar", data: { labels: t.rotulos, datasets: [{ label: "Custo (R$)", data: t.custo, backgroundColor: "#155E75", borderRadius: 4 }] },
            options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } } });

        const ct = d.custo_por_tipo;
        vazio("g-custo-tipo", ct.rotulos.length);
        desenhar("g-custo-tipo", { type: "doughnut", data: { labels: ct.rotulos.map(r => r.charAt(0) + r.slice(1).toLowerCase()),
            datasets: [{ data: ct.custo, backgroundColor: ["#18B7B0", "#E9A23B"], borderWidth: 2 }] },
            options: { cutout: "55%", plugins: { legend: { position: "bottom" } } } });

        const r = d.manut_por_tipo_equip;
        vazio("g-radar", r.rotulos.length);
        desenhar("g-radar", { type: "radar", data: { labels: r.rotulos, datasets: [{ label: "Manutenções", data: r.qtd,
            backgroundColor: "rgba(24,183,176,.25)", borderColor: "#18B7B0", pointBackgroundColor: "#18B7B0" }] },
            options: { scales: { r: { beginAtZero: true, ticks: { precision: 0 } } }, plugins: { legend: { display: false } } } });
    }

    function renderTabela(linhas) {
        const corpo = document.getElementById("tabela-atencao");
        if (!linhas.length) { corpo.innerHTML = '<tr><td colspan="3" class="text-muted small p-3">Nenhuma unidade crítica ou em atenção.</td></tr>'; return; }
        corpo.innerHTML = linhas.map(l => `<tr><td class="small bd-quebra">${esc(l.unidade)}</td><td>${num(l.pct_operantes)}%</td>
            <td><span class="badge" style="background:${COR_CLASS[l.classificacao] || "#8FA3AD"}">${esc(NOME_CLASS[l.classificacao] || l.classificacao)}</span></td></tr>`).join("");
    }

    function parametros() {
        const p = new URLSearchParams();
        new FormData(form).forEach((v, k) => { if (v) p.set(k, v); });
        return p;
    }

    async function carregar() {
        const meu = ++contador;
        painel.classList.add("dbd-loading");
        const p = parametros();
        history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
        try {
            const resp = await fetch(`${location.pathname}/dados?${p}`, { headers: { Accept: "application/json" } });
            const d = await resp.json();
            if (meu !== contador) return;  // resposta antiga
            if (!resp.ok) throw new Error(d.erro || "Falha ao carregar.");
            alerta.classList.add("d-none");
            renderKpis(d.kpis); renderGraficos(d); renderTabela(d.unidades_atencao);
        } catch (err) {
            alerta.textContent = err.message; alerta.classList.remove("d-none");
        } finally {
            if (meu === contador) painel.classList.remove("dbd-loading");
        }
    }

    function iso(d) { return d.toISOString().slice(0, 10); }

    document.getElementById("periodo").addEventListener("change", ev => {
        const meses = ev.target.value;
        if (meses === "") return;
        if (meses === "0") { form.data_ini.value = ""; form.data_fim.value = ""; }
        else {
            const fim = new Date(), ini = new Date();
            ini.setMonth(ini.getMonth() - Number(meses));
            form.data_ini.value = iso(ini); form.data_fim.value = iso(fim);
        }
        carregar();
    });
    form.querySelectorAll("input,select").forEach(el => el.addEventListener("change", () => {
        if (el.id !== "periodo") { if (el.name === "data_ini" || el.name === "data_fim") document.getElementById("periodo").value = ""; carregar(); }
    }));
    document.getElementById("limpar").addEventListener("click", () => { form.reset(); carregar(); });

    // restaura filtros da URL (link compartilhável)
    new URLSearchParams(location.search).forEach((v, k) => { if (form.elements[k]) form.elements[k].value = v; });
    carregar();
})();
