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

	// Barras horizontais agrupadas, uma série por grupo (ex.: tentativas), até 3 séries.
	// series = [{ rotulo, valores, slot }]: o slot (1 a 3) fixa a cor da série, para que a mesma
	// entidade tenha sempre a mesma cor, qualquer que seja a quantidade de séries.
	window.graficoBarrasAgrupadas = function (id, rotulos, series, opcoes) {
		opcoes = opcoes || {};
		const elemento = document.getElementById(id);
		if (!elemento) return;
		new Chart(elemento, {
			type: 'bar',
			data: {
				labels: rotulos,
				datasets: series.map((serie) => ({
					label: serie.rotulo,
					data: serie.valores,
					backgroundColor: cor('--serie-' + serie.slot),
					borderRadius: 4,
					borderSkipped: 'start',
					barThickness: 12,
					categoryPercentage: 0.8,
					barPercentage: 0.9,
				})),
			},
			options: {
				indexAxis: 'y',
				maintainAspectRatio: false,
				interaction: { mode: 'index', axis: 'y', intersect: false },
				scales: { x: eixoValores(opcoes.maximo, opcoes.sufixo), y: eixoCategorias },
				plugins: {
					legend: { display: true, position: 'top', align: 'start', labels: { boxWidth: 12, boxHeight: 12 } },
					tooltip: {
						callbacks: {
							label: (contexto) =>
								' ' + contexto.dataset.label + ': ' + (contexto.raw === null ? 'não avaliado' : contexto.formattedValue + (opcoes.sufixo || '')),
						},
					},
				},
			},
		});
	};

	// opcoes.detalhes: texto extra no tooltip de cada ponto; opcoes.vazados: pontos desenhados vazados
	// (ex.: amostra pequena). Valores null ficam como lacuna na linha. Retorna o gráfico criado.
	window.graficoLinha = function (id, rotulos, valores, opcoes) {
		opcoes = opcoes || {};
		const elemento = document.getElementById(id);
		if (!elemento) return;
		const vazados = opcoes.vazados || [];
		return new Chart(elemento, {
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
					pointBackgroundColor: valores.map((_, i) => cor(vazados[i] ? '--superficie' : '--serie-1')),
					pointBorderColor: valores.map((_, i) => cor(vazados[i] ? '--serie-1' : '--superficie')),
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

	// Evolução teste a teste com seletor de assunto acima do gráfico (estatisticas.evolucao_por_teste).
	// O seletor vazio mostra o acerto geral; ao escolher um assunto, o gráfico é redesenhado só com ele.
	window.graficoEvolucao = function (idCanvas, idSeletor, idNota, evolucao, unidade) {
		const seletor = document.getElementById(idSeletor);
		const nota = document.getElementById(idNota);
		let grafico = null;

		function desenhar() {
			const assunto = seletor ? seletor.value : '';
			const pontos = assunto ? evolucao.assuntos[assunto] : evolucao.geral;
			const vazados = pontos.map((p) => p !== null && p.total < evolucao.min_questoes);
			if (grafico) grafico.destroy();
			grafico = graficoLinha(idCanvas, evolucao.rotulos, pontos.map((p) => (p === null ? null : p.percentual)), {
				rotulo: assunto || 'Acerto geral',
				sufixo: '%',
				maximo: 100,
				detalhes: pontos.map((p) => (p === null ? 'não avaliado' : p.acertos + ' de ' + p.total + ' ' + unidade)),
				vazados: vazados,
			});
			if (nota) nota.hidden = !vazados.some(Boolean);
		}

		if (seletor) seletor.addEventListener('change', desenhar);
		desenhar();
	};
})();
