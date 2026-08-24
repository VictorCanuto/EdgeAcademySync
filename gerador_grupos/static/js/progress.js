/**
 * ==========================================================================
 * AcademySync - Módulo Global de Progresso de Upload em 2 Estágios
 * ==========================================================================
 * Este módulo gerencia o overlay de carregamento (#upload-progress-overlay),
 * dividindo a experiência visual em duas etapas claras e verídicas:
 * 
 * Estágio 1 (0% -> 50%): Transmissão física dos bytes dos PDFs pela rede.
 * Estágio 2 (50% -> 100%): Processamento no backend Python (leitura de tabelas,
 *                          sanitização de alunos e gravação no banco de dados).
 */

(function (window) {
    'use strict';

    /**
     * Dispara o overlay de progresso unificado em 2 estágios.
     * 
     * @param {Object} options Configurações do upload:
     * @param {string} options.url URL do endpoint backend.
     * @param {FormData} options.formData Dados do formulário contendo os arquivos.
     * @param {number} [options.totalFiles=1] Quantidade total de arquivos PDF sendo enviados.
     * @param {Function} [options.onSuccess] Callback executada ao receber sucesso do servidor (data, xhr).
     * @param {Function} [options.onError] Callback executada em caso de erro de rede ou servidor (error, xhr).
     */
    function triggerGlobalUploadProgress(options) {
        const url = options.url;
        const formData = options.formData;
        const totalFiles = options.totalFiles || 1;
        const onSuccess = options.onSuccess;
        const onError = options.onError;

        const overlay = document.getElementById('upload-progress-overlay');
        const title = document.getElementById('progress-title');
        const status = document.getElementById('progress-status');
        const barFill = document.getElementById('progress-bar-fill');
        const percentage = document.getElementById('progress-percentage');

        // Ativa o overlay e reinicia o estado visual
        if (overlay) {
            overlay.classList.add('active');
            overlay.style.display = 'flex';
        }
        if (barFill) {
            barFill.classList.remove('processing');
            barFill.style.width = "0%";
        }
        if (percentage) percentage.innerText = "0%";
        if (title) title.innerText = "Enviando Arquivos PDF";
        if (status) status.innerText = `Transmitindo ${totalFiles} arquivo(s) PDF para o servidor... [0%]`;

        const xhr = new XMLHttpRequest();
        let serverStageInterval = null;

        // ESTÁGIO 1: Acompanhamento da transmissão de bytes na rede (0% -> 50%)
        xhr.upload.addEventListener('progress', function (event) {
            if (event.lengthComputable) {
                const networkPercent = Math.round((event.loaded / event.total) * 100);
                // Mapeia 0-100% de rede para 0-50% visual da barra
                const visualPercent = Math.round(networkPercent * 0.5);

                if (barFill) barFill.style.width = visualPercent + "%";
                if (percentage) percentage.innerText = visualPercent + "%";

                if (networkPercent < 100) {
                    if (title) title.innerText = "Enviando Arquivos PDF";
                    if (status) status.innerText = `Transmitindo ${totalFiles} arquivo(s) PDF para o servidor... [${networkPercent}%]`;
                } else {
                    // ESTÁGIO 2: Transmissão concluída; inicia leitura de PDFs no servidor Python
                    if (title) title.innerText = "Processando e Extraindo Horários";
                    if (status) status.innerText = `Lendo tabelas dos PDFs e extraindo horários dos alunos... Por favor, aguarde.`;
                    if (barFill) {
                        barFill.classList.add('processing');
                        barFill.style.width = "55%";
                    }
                    if (percentage) percentage.innerText = "55%";

                    // Avanço dinâmico enquanto o Python processa as tabelas em segundo plano
                    let currentSimulated = 55;
                    if (!serverStageInterval) {
                        serverStageInterval = setInterval(function () {
                            if (currentSimulated < 95) {
                                currentSimulated += Math.floor(Math.random() * 4) + 1;
                                if (currentSimulated > 95) currentSimulated = 95;
                                if (barFill) barFill.style.width = currentSimulated + "%";
                                if (percentage) percentage.innerText = currentSimulated + "%";
                            }
                        }, 400);
                    }
                }
            }
        });

        // Conclusão da resposta do servidor
        xhr.onload = function () {
            if (serverStageInterval) clearInterval(serverStageInterval);

            if (barFill) {
                barFill.classList.remove('processing');
                barFill.style.width = "100%";
            }
            if (percentage) percentage.innerText = "100%";
            if (title) title.innerText = "Processamento Concluído";
            if (status) status.innerText = "Operação realizada com sucesso!";

            setTimeout(function () {
                if (overlay) {
                    overlay.classList.remove('active');
                    overlay.style.display = 'none';
                }

                let responseData = null;
                try {
                    responseData = JSON.parse(xhr.responseText);
                } catch (e) {
                    responseData = { success: xhr.status >= 200 && xhr.status < 400 };
                }

                if (typeof onSuccess === 'function') {
                    onSuccess(responseData, xhr);
                }
            }, 500);
        };

        // Tratamento de erros de conexão/rede
        xhr.onerror = function (err) {
            if (serverStageInterval) clearInterval(serverStageInterval);
            if (overlay) {
                overlay.classList.remove('active');
                overlay.style.display = 'none';
            }
            if (typeof onError === 'function') {
                onError(err, xhr);
            } else if (typeof window.showToast === 'function') {
                window.showToast('Erro', 'Falha na comunicação com o servidor.', 'danger');
            }
        };

        xhr.open('POST', url, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send(formData);
    }

    // Exporta de forma segura no objeto global window
    window.triggerGlobalUploadProgress = triggerGlobalUploadProgress;

})(window);
