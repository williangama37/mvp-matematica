// Funções de gráficos compartilhadas pelos dashboards (Chart.js).
// Uma série = uma cor (slot 1); marcas finas, grade discreta, tooltip ao passar o mouse.
(function () {
	const estilo = getComputedStyle(document.documentElement);
	const cor = (nome) => estilo.getPropertyValue(nome).trim();

	Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
	Chart.defaults.color = cor('--texto-secundario');
	Chart.defaults.plugins.legend.display = false;

	const eixoValores = (maximo, sufixo) => ({
		beginAtZero: true,
		max: maximo,
		grid: { color: cor('--grade') },
		border: { display: false },
		// Sem sufixo o eixo é uma contagem: só números inteiros.
		ticks: { precision: sufixo ? undefined : 0, callback: (valor) => valor + (sufixo || '') },
	});

	const eixoCategorias = {
		grid: { display: false },
		border: { color: cor('--grade') },
	};

	window.graficoBarrasHorizontais = function (id, rotulos, valores, opcoes) {
		opcoes = opcoes || {};
		const elemento = document.getElementById(id);
		if (!elemento) return;
		new Chart(elemento, {
			type: 'bar',
			data: {
				labels: rotulos,
				datasets: [{
					label: opcoes.rotulo || '',
					data: valores,
					backgroundColor: cor('--serie-1'),
					borderRadius: 4,
					borderSkipped: 'start',
					barThickness: 18,
				}],
			},
			options: {
				indexAxis: 'y',
				maintainAspectRatio: false,
				scales: { x: eixoValores(opcoes.maximo, opcoes.sufixo), y: eixoCategorias },
				plugins: {
					tooltip: {
						callbacks: {
							label: (contexto) => {
								const extra = opcoes.detalhes ? ' — ' + opcoes.detalhes[contexto.dataIndex] : '';
								return ' ' + contexto.formattedValue + (opcoes.sufixo || '') + extra;
							},
						},
					},
				},
			},
		});
	};

	window.graficoLinha = function (id, rotulos, valores, opcoes) {
		opcoes = opcoes || {};
		const elemento = document.getElementById(id);
		if (!elemento) return;
		new Chart(elemento, {
			type: 'line',
			data: {
				labels: rotulos,
				datasets: [{
					label: opcoes.rotulo || '',
					data: valores,
					borderColor: cor('--serie-1'),
					backgroundColor: cor('--serie-1'),
					borderWidth: 2,
					pointRadius: 4,
					pointHoverRadius: 6,
					pointBorderColor: cor('--superficie'),
					pointBorderWidth: 2,
					tension: 0.25,
				}],
			},
			options: {
				maintainAspectRatio: false,
				interaction: { mode: 'index', intersect: false },
				scales: { y: eixoValores(opcoes.maximo, opcoes.sufixo), x: eixoCategorias },
				plugins: {
					tooltip: {
						callbacks: { label: (contexto) => ' ' + contexto.formattedValue + (opcoes.sufixo || '') },
					},
				},
			},
		});
	};
})();
