// AcademySync - JavaScript Principal

class AcademySyncApp {
    constructor() {
        this.modal = document.getElementById('schedule-modal');
        this.modalBody = document.getElementById('modal-body');
        this.modalTitle = document.getElementById('modal-title');
        this.closeButton = document.querySelector('.close-button');
        
        this.init();
    }

    init() {
        console.log('AcademySync App inicializado');
        this.setupModal();
        this.setupFileUpload();
        this.setupFormSubmissions();
        this.setupAlunoCards();
        this.setupBlocoHorario(); 
    }

    setupModal() {
        // Fechar modal
        this.closeButton.addEventListener('click', () => this.closeModal());
        window.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.closeModal();
            }
        });
    }

    closeModal() {
        this.modal.style.display = 'none';
        this.modalBody.innerHTML = '';
        this.modalTitle.textContent = 'Horários do Aluno';
    }

    setupFileUpload() {
        const uploadForm = document.querySelector('.upload-form');
        const fileInput = document.getElementById('pdf-files');
        const fileList = document.getElementById('file-list');

        if (uploadForm) {
            uploadForm.addEventListener('submit', (e) => this.handleUploadSubmit(e));
        }
        if (fileInput && fileList) {
            fileInput.addEventListener('change', () => this.handleFileSelection(fileInput, fileList));
        }
    }

    handleUploadSubmit(e) {
        const fileInput = document.getElementById('pdf-files');
        if (fileInput.files.length === 0) {
            e.preventDefault();
            alert("Por favor, selecione pelo menos um PDF antes de processar.");
            return false;
        }
        const submitBtn = e.target.querySelector('button[type="submit"]');
        this.showLoadingState(submitBtn);
    }

    handleFileSelection(fileInput, fileList) {
        fileList.innerHTML = '';
        if (fileInput.files.length > 0) {
            const fileCount = document.createElement('div');
            fileCount.className = 'file-count';
            fileCount.textContent = `${fileInput.files.length} ficheiro(s) selecionado(s)`;
            fileList.appendChild(fileCount);
            const maxFilesToShow = 3;
            for (let i = 0; i < Math.min(fileInput.files.length, maxFilesToShow); i++) {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.textContent = fileInput.files[i].name;
                fileList.appendChild(fileItem);
            }
            if (fileInput.files.length > maxFilesToShow) {
                const moreFiles = document.createElement('div');
                moreFiles.className = 'file-more';
                moreFiles.textContent = `+ ${fileInput.files.length - maxFilesToShow} mais`;
                fileList.appendChild(moreFiles);
            }
        }
    }

    setupFormSubmissions() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            if (form.classList.contains('upload-form')) return;
            form.addEventListener('submit', (e) => {
                const submitBtn = e.target.querySelector('button[type="submit"]');
                this.showLoadingState(submitBtn);
            });
        });
    }

    showLoadingState(submitBtn) {
        if (!submitBtn) return;
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');
        if (btnText && btnLoading) {
            btnText.style.display = 'none';
            btnLoading.style.display = 'inline-flex';
        }
        submitBtn.disabled = true;
    }

    setupAlunoCards() {
        document.querySelectorAll('.aluno-card, .aluno-link').forEach(link => {
            link.addEventListener('click', (e) => this.handleAlunoCardClick(e));
        });
    }

    handleAlunoCardClick(event) {
        event.preventDefault();
        const alunoNome = event.currentTarget.dataset.alunoNome;
        this.modalBody.innerHTML = `<div class="loading-container"><div class="loading-spinner"></div><p>Carregando horários de ${alunoNome}...</p></div>`;
        this.modalTitle.textContent = `Horários de ${alunoNome}`;
        this.modal.style.display = 'flex';
        this.fetchAlunoSchedule(alunoNome);
    }

    async fetchAlunoSchedule(alunoNome) {
        try {
            // A sua rota correta é /aluno/NOME, vamos garantir que a chamada corresponde
            const response = await fetch(`/aluno/${encodeURIComponent(alunoNome)}`);
            if (!response.ok) {
                throw new Error('Erro ao carregar os horários');
            }
            const html = await response.text();
            this.modalBody.innerHTML = html;
        } catch (error) {
            console.error('Erro ao carregar horários:', error);
            this.showErrorModal(error.message);
        }
    }

    showErrorModal(errorMessage) {
        this.modalBody.innerHTML = `<div class="error-container"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 8V12" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 16H12.01" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><h3>Erro ao carregar os horários</h3><p>${errorMessage}</p></div>`;
    }

    // --- MÉTODOS NOVOS PARA OS BLOCOS DE HORÁRIO (INTEGRADOS) ---

    setupBlocoHorario() {
        const container = document.getElementById('blocos-container');
        const addButton = document.querySelector('.btn-add');

        if (!container || !addButton) {
            console.warn('Elementos para blocos de horário não encontrados.');
            return;
        }
        
        addButton.addEventListener('click', () => this.adicionarBloco());

        container.addEventListener('click', (event) => {
            const removeButton = event.target.closest('.btn-remove');
            if (removeButton) {
                this.removerBloco(removeButton);
            }
        });
        
        this.atualizarBotoesRemover();
    }

    adicionarBloco() {
        const container = document.getElementById('blocos-container');
        const template = document.getElementById('bloco-template');
        if (container && template) {
            const clone = template.firstElementChild.cloneNode(true);
            container.appendChild(clone);
            this.atualizarBotoesRemover();
        }
    }

    removerBloco(button) {
        button.closest('.bloco-card').remove();
        this.atualizarBotoesRemover();
    }

    atualizarBotoesRemover() {
        const container = document.getElementById('blocos-container');
        if (container) {
            const blocos = container.getElementsByClassName('bloco-card');
            for (let i = 0; i < blocos.length; i++) {
                const btn = blocos[i].querySelector('.btn-remove');
                if (btn) {
                    btn.style.display = blocos.length > 1 ? 'inline-flex' : 'none';
                }
            }
        }
    }
}

// Inicializar a aplicação quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', () => {
    new AcademySyncApp();
});

// Utilitários globais para debugging
window.AcademySync = {
    debug: {
        log: (message, data) => {
            console.log(`[AcademySync] ${message}`, data);
        },
        error: (message, error) => {
            console.error(`[AcademySync] ${message}`, error);
        }
    }
};