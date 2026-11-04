/* ORIS - helpers de gráficos (Chart.js) do módulo Banco de Dados. */
(function () {
    const PALETA = ["#18B7B0", "#155E75", "#E9A23B", "#39C6D3", "#0B2A4A", "#8FA3AD", "#39A96B", "#D9534F"];
    const SEMANTICA = { ATIVA: "#39A96B", ATIVO: "#39A96B", INATIVA: "#8FA3AD", INATIVO: "#8FA3AD",
                        MANUTENCAO: "#E9A23B", aprovadas: "#39A96B", rejeitadas: "#D9534F",
                        pendentes: "#E9A23B", ativos: "#18B7B0", inativos: "#8FA3AD" };

    const NOMES = { ATIVA: "Ativa", INATIVA: "Inativa", MANUTENCAO: "Manutenção",
                    ATIVO: "Ativo", INATIVO: "Inativo" };

    function rotular(chave) {
        if (NOMES[chave]) return NOMES[chave];
        return String(chave).replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
    }

    function encurtar(texto, max = 26) {
        texto = String(texto);
        return texto.length > max ? texto.slice(0, max - 1) + "…" : texto;
    }

    function cor(chave, i) { return SEMANTICA[chave] || PALETA[i % PALETA.length]; }

    if (window.Chart) {
        Chart.defaults.font.family = '"IBM Plex Sans", system-ui, sans-serif';
        Chart.defaults.color = "#5B6B73";
        Chart.defaults.maintainAspectRatio = false;
        Chart.defaults.plugins.legend.labels.boxWidth = 12;
    }

    window.OrisCharts = {
        cor, rotular, PALETA,

        barras(id, rotulos, series, opcoes = {}) {
            const el = document.getElementById(id);
            if (!el || !window.Chart) return;
            new Chart(el, {
                type: "bar",
                data: {
                    labels: rotulos,
                    datasets: Object.entries(series).map(([nome, valores], i) => ({
                        label: opcoes.nomes?.[nome] || rotular(nome), data: valores,
                        backgroundColor: cor(nome, i), borderRadius: 4, maxBarThickness: 46,
                    })),
                },
                options: {
                    indexAxis: opcoes.horizontal ? "y" : "x",
                    plugins: { legend: { display: Object.keys(series).length > 1 } },
                    scales: {
                        x: { stacked: !!opcoes.empilhado, grid: { display: !!opcoes.horizontal },
                             title: { display: !!opcoes.tituloX, text: opcoes.tituloX },
                             ticks: opcoes.horizontal ? { precision: 0 }
                                 : { callback(v) { return encurtar(this.getLabelForValue(v), 18); } } },
                        y: { stacked: !!opcoes.empilhado, beginAtZero: true,
                             title: { display: !!opcoes.tituloY, text: opcoes.tituloY },
                             ticks: opcoes.horizontal
                                 ? { callback(v) { return encurtar(this.getLabelForValue(v)); } }
                                 : { precision: 0 },
                             grid: { display: !opcoes.horizontal } },
                    },
                },
            });
        },

        rosca(id, rotulos, valores) {
            const el = document.getElementById(id);
            if (!el || !window.Chart) return;
            new Chart(el, {
                type: "doughnut",
                data: { labels: rotulos.map(rotular),
                        datasets: [{ data: valores, backgroundColor: rotulos.map((r, i) => cor(r, i)), borderWidth: 2 }] },
                options: { cutout: "62%", plugins: { legend: { position: "bottom" } } },
            });
        },

        pareto(id, rotulos, barras, acumulado, nomeBarra) {
            const el = document.getElementById(id);
            if (!el || !window.Chart) return;
            new Chart(el, {
                data: {
                    labels: rotulos,
                    datasets: [
                        { type: "bar", label: rotular(nomeBarra), data: barras, backgroundColor: "#18B7B0",
                          borderRadius: 4, yAxisID: "y", order: 2 },
                        { type: "line", label: "% acumulado", data: acumulado, borderColor: "#0B2A4A",
                          backgroundColor: "#0B2A4A", tension: .25, yAxisID: "y1", order: 1 },
                    ],
                },
                options: {
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        y1: { position: "right", min: 0, max: 100, grid: { display: false },
                              ticks: { callback: v => v + "%" } },
                        x: { grid: { display: false } },
                    },
                },
            });
        },

        linhas(id, rotulos, series) {
            const el = document.getElementById(id);
            if (!el || !window.Chart) return;
            new Chart(el, {
                type: "line",
                data: { labels: rotulos,
                        datasets: Object.entries(series).map(([nome, valores], i) => ({
                            label: rotular(nome), data: valores, borderColor: cor(nome, i),
                            backgroundColor: cor(nome, i), tension: .25, fill: false })) },
                options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
            });
        },
    };
})();
