// ==========================================================================
// CONFIGURAÇÕES GLOBAIS DA AGENDA
// ==========================================================================
const DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
// Grade fixa
const HORARIOS = [
    '07:00', '07:30', '08:00', '08:30', '09:00', '09:30',
    '10:00', '10:30', '11:00', '11:30', '12:00', '12:30',
    '13:00', '13:30', '14:00', '14:30', '15:00', '15:30',
    '16:00', '16:30', '17:00', '17:30', '18:00'
];

function slotToMinutes(slot) {
    const [hh, mm] = slot.split(':').map(Number);
    return hh * 60 + mm;
}

// Converte texto de bloco ("Manhã (09h-11h)" / "09:00 - 11:00") em início/fim (minutos)
function parseHorarioMinutes(horarioStr) {
    if (!horarioStr) return { inicio: 9 * 60, fim: 11 * 60 };

    const match = horarioStr.match(/(\d+)h-(\d+)h/);
    if (match) {
        return { inicio: parseInt(match[1], 10) * 60, fim: parseInt(match[2], 10) * 60 };
    }

    try {
        const parts = horarioStr.split(' - ');
        return { inicio: slotToMinutes(parts[0].trim()), fim: slotToMinutes(parts[1].trim()) };
    } catch (e) {
        return { inicio: 9 * 60, fim: 11 * 60 };
    }
}

// Estado local para a planilha geral carregada do servidor
let studentSchedules = {};

// Estado local de filtros para a planilha geral
let activeGroupFilter = 'all';
let selectedCompareStudents = new Set();

// Estado local de colapso de dias da semana
let collapsedDays = JSON.parse(localStorage.getItem('academysync_collapsed_days')) || [];

// Mapeamento de nomes de dias completos para curtos
const DIAS_CURTOS = {
    'Segunda': 'Seg',
    'Terça': 'Ter',
    'Quarta': 'Qua',
    'Quinta': 'Qui',
    'Sexta': 'Sex',
    'Sábado': 'Sáb'
};

// Estado para o Popover de Edição
let activePopover = {
    alunoNome: null,
    dia: null,
    horario: null,
    targetCell: null
};

// Lista local de conflitos (calculada dinamicamente)
let activeConflicts = [];

// ==========================================================================
// INICIALIZAÇÃO DA APLICAÇÃO
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setupGlobalEventListeners();

    // Ligar interface de arquivos do Passo 1 se visível
    setupDragDropWizard();
    setupUploadProgress();

    // Inicializar Workspace se o usuário possuir base_data
    if (window.flaskData.hasBaseData) {
        // Carregar horários via Fetch API
        loadSchedulesFromServer().then(() => {
            if (!window.flaskData.emImersao) {
                // Se a turma não for de imersão, abre diretamente a planilha geral
                switchTab('spreadsheet');
            } else if (window.flaskData.hasGroups) {
                // Recuperar última aba ativa ou padrão (apenas para turmas de imersão)
                const lastTab = localStorage.getItem('academysync_active_tab') || 'spreadsheet';
                switchTab(lastTab === 'groups' ? 'groups' : 'spreadsheet');
            } else {
                // Se é imersão, tem base_data mas sem grupos, renderiza o painel de configurações (Passo 2)
                initBlocksListInWizard();
            }
        });
    }

    // Verificar mensagens flash
    displayFlaskFlashMessages();
});

// ==========================================================================
// CONTROLE DE TEMA (CLARO/ESCURO)
// ==========================================================================
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    const themeCheckbox = document.getElementById('checkbox-theme');

    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (themeCheckbox) themeCheckbox.checked = true;
    } else {
        document.body.classList.remove('dark-mode');
        if (themeCheckbox) themeCheckbox.checked = false;
    }

    if (themeCheckbox) {
        themeCheckbox.addEventListener('change', () => {
            if (themeCheckbox.checked) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('theme', 'light');
            }
        });
    }
}

// ==========================================================================
// CONTROLE DE FLUXO DE ABAS DO WORKSPACE
// ==========================================================================
function switchTab(tabName) {
    const tabBtnSpreadsheet = document.getElementById('tab-btn-spreadsheet');
    const tabBtnGroups = document.getElementById('tab-btn-groups');
    const tabViewSpreadsheet = document.getElementById('tab-view-spreadsheet');
    const tabViewGroups = document.getElementById('tab-view-groups');

    if (tabBtnSpreadsheet) tabBtnSpreadsheet.className = tabName === 'spreadsheet' ? 'tab-btn active' : 'tab-btn';
    if (tabBtnGroups) tabBtnGroups.className = tabName === 'groups' ? 'tab-btn active' : 'tab-btn';

    if (tabViewSpreadsheet) tabViewSpreadsheet.className = tabName === 'spreadsheet' ? 'tab-view active' : 'tab-view';
    if (tabViewGroups) tabViewGroups.className = tabName === 'groups' ? 'tab-view active' : 'tab-view';

    localStorage.setItem('academysync_active_tab', tabName);

    if (tabName === 'spreadsheet') {
        renderSpreadsheet();
    } else {
        renderKanban();
    }
}

// ==========================================================================
// CARREGAR DADOS DOS HORÁRIOS VIA FETCH
// ==========================================================================
async function loadSchedulesFromServer() {
    try {
        const response = await fetch('/aluno/schedules_json/' + window.flaskData.turmaId);
        if (response.ok) {
            studentSchedules = await response.json();
            recalculateConflicts();
        }
    } catch (error) {
        console.error('Erro ao buscar agendas do servidor:', error);
    }
}

// ==========================================================================
// RENDERIZAR PLANILHA GERAL DE HORÁRIOS (HTML5 DINÂMICO)
// ==========================================================================
function renderSpreadsheet() {
    const table = document.getElementById('spreadsheet-main-table');
    if (!table) return;
    table.innerHTML = '';

    const listAlunos = window.flaskData.listaAlunos;
    if (listAlunos.length === 0) return;

    // Inicializar os filtros da planilha
    initSpreadsheetFilters();

    // Filtrar a lista de alunos com base nos filtros ativos
    const filteredAlunos = listAlunos.filter(alunoNome => {
        // 1. Filtro de Grupo
        if (activeGroupFilter !== 'all') {
            const grupoInfo = window.flaskData.grupos.find(g => {
                return g.Membros.some(m => m.nome.toLowerCase() === alunoNome.toLowerCase());
            });
            if (activeGroupFilter === 'sem-grupo') {
                if (grupoInfo) return false;
            } else {
                if (!grupoInfo || String(grupoInfo.Grupo) !== String(activeGroupFilter)) return false;
            }
        }

        // 2. Filtro de Comparação
        if (selectedCompareStudents.size > 0) {
            if (!selectedCompareStudents.has(alunoNome)) return false;
        }

        return true;
    });

    // Atualizar texto informativo de status do filtro
    const statusText = document.getElementById('filter-active-status');
    if (statusText) {
        let text = `Mostrando ${filteredAlunos.length} de ${listAlunos.length} alunos`;
        if (selectedCompareStudents.size > 0 || activeGroupFilter !== 'all') {
            text += ` (Filtro Ativo - <a href="#" onclick="clearAllFilters(event)" style="color: var(--color-primary); text-decoration: none; font-weight: 600;">Limpar</a>)`;
        }
        statusText.innerHTML = text;
    }

    // Criar thead e tbody
    let thead = table.querySelector('thead');
    if (!thead) {
        thead = document.createElement('thead');
        table.appendChild(thead);
    } else {
        thead.innerHTML = '';
    }

    let tbody = table.querySelector('tbody');
    if (!tbody) {
        tbody = document.createElement('tbody');
        table.appendChild(tbody);
    } else {
        tbody.innerHTML = '';
    }

    // Header 1: Dias da Semana
    const trDays = document.createElement('tr');

    const thEstudantes = document.createElement('th');
    thEstudantes.rowSpan = 2;
    thEstudantes.className = 'sticky-header estudantes-header';
    thEstudantes.innerText = 'Estudantes';
    trDays.appendChild(thEstudantes);

    DIAS_SEMANA.forEach(dia => {
        const th = document.createElement('th');
        th.className = 'sticky-header day-header';

        const isCollapsed = collapsedDays.includes(dia);
        if (isCollapsed) {
            th.colSpan = 1;
            th.rowSpan = 2;
            th.innerHTML = `${DIAS_CURTOS[dia]} <span style="font-size: 0.65rem; opacity: 0.7;">▸</span>`;
            th.title = `Clique para expandir ${dia}-feira`;
        } else {
            th.colSpan = HORARIOS.length;
            th.rowSpan = 1;
            th.innerHTML = `${dia} <span style="font-size: 0.65rem; opacity: 0.7;">▾</span>`;
            th.title = `Clique para minimizar ${dia}-feira`;
        }

        th.addEventListener('click', () => toggleDayCollapse(dia));
        trDays.appendChild(th);
    });
    thead.appendChild(trDays);

    // Header 2: Horários
    const trHours = document.createElement('tr');
    DIAS_SEMANA.forEach(dia => {
        const isCollapsed = collapsedDays.includes(dia);
        if (!isCollapsed) {
            HORARIOS.forEach(hora => {
                const th = document.createElement('th');
                th.className = 'sticky-header hour-header';
                th.innerText = hora;
                trHours.appendChild(th);
            });
        }
    });
    thead.appendChild(trHours);

    // Linhas dos estudantes
    filteredAlunos.forEach(alunoNome => {
        const tr = document.createElement('tr');

        // Célula fixa do estudante
        const tdName = document.createElement('td');
        tdName.className = 'aluno-name-cell';

        // Descobrir grupo do estudante
        const grupoInfo = window.flaskData.grupos.find(g => {
            return g.Membros.some(m => m.nome.toLowerCase() === alunoNome.toLowerCase());
        });

        const alunoId = (window.flaskData.alunoIdMap || {})[alunoNome];

        tdName.innerHTML = `
            <div style="display:flex; align-items:center; justify-content: space-between; gap:8px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <div class="user-avatar" style="width:24px; height:24px; font-size:0.75rem; background: var(--color-primary); color:white; flex-shrink: 0; align">
                        ${alunoNome[0].toUpperCase()}
                    </div>
                    <div>
                        <h2 style="font-weight: 600; line-height: 1.2; font-size: 0.8rem;">
                            ${alunoNome}
                        </h2>
                        <span style="font-size: 0.7rem; color: var(--text-muted); font-weight:500;">
                            ${grupoInfo ? `Grupo ${grupoInfo.Grupo}` : 'Sem Grupo'}
                        </span>
                    </div>
                </div>

                <div style="display: flex;">
                    ${window.flaskData.isAdmin ? `
                        ${alunoId != null ? 
                            `<button class="action-bttn action-bttn-edit" 
                            onclick='openEditStudantModal(${JSON.stringify({ id: alunoId, nome: alunoNome, turmaId: window.flaskData.turmaId })})'
                            title="Editar Aluno">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                            </svg>
                        </button>` : ''}

                        ${alunoId!= null ? 
                        `<button class="action-bttn action-bttn-delete"
                            onclick='openDeleteStudantModal(${JSON.stringify({ id: alunoId, nome: alunoNome })})'
                            title="Excluir Aluno">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2">
                                </path>
                            </svg>
                        </button>` : ''}
                    ` : ''}
                </div>
            </div>
        `;
        tr.appendChild(tdName);

        // Células de horários
        const agendaAluno = studentSchedules[alunoNome] || {};

        DIAS_SEMANA.forEach(dia => {
            const isCollapsed = collapsedDays.includes(dia);
            if (isCollapsed) {
                const td = document.createElement('td');
                td.className = 'sched-cell collapsed-day-placeholder';
                td.title = `${alunoNome} - Clique para expandir ${dia}-feira`;
                td.addEventListener('click', () => toggleDayCollapse(dia));
                tr.appendChild(td);
            } else {
                HORARIOS.forEach(hora => {
                    const td = document.createElement('td');
                    td.className = 'sched-cell';
                    const key = `${dia}_${hora}`;
                    const state = agendaAluno[key] || 'free';

                    if (state === 'free') {
                        td.classList.add('free');
                        td.innerText = 'L';
                    } else if (state === 'class') {
                        td.classList.add('class');
                        td.innerText = 'X';
                    } else if (state === 'ac') {
                        td.classList.add('ac');
                        td.innerText = 'AC';
                    } else if (state === 'psi') {
                        td.classList.add('psi');
                        td.innerText = 'PSI';
                    } else if (state === 'im') {
                        td.classList.add('im');
                        td.innerText = 'IM';
                    } else if (state === 'ap') {
                        td.classList.add('ap');
                        td.innerText = 'AP';
                    } else if (state === 'r') {
                        td.classList.add('r');
                        td.innerText = 'R';
                    } else {
                        td.classList.add('custom-comp');
                        td.innerText = String(state).charAt(0).toUpperCase();
                        td.title = state;
                    }

                    // Evento clique do popover
                    if (state !== 'class') {
                        td.addEventListener('click', (e) => {
                            openPopover(e, alunoNome, dia, hora);
                        });
                    } else {
                        td.style.cursor = 'not-allowed';
                        td.title = 'Aulas de Graduação não podem ser alteradas';
                    }

                    tr.appendChild(td);
                });
            }
        });

        tbody.appendChild(tr);
    });
}

// ==========================================================================
// POPOVER FLUTUANTE DE EDIÇÃO
// ==========================================================================
function openPopover(event, alunoNome, dia, hora) {
    event.stopPropagation();

    activePopover = {
        alunoNome: alunoNome,
        dia: dia,
        horario: hora,
        targetCell: event.currentTarget
    };

    const popover = document.getElementById('popover-schedule-menu');
    document.getElementById('popover-student-name').innerText = alunoNome;
    document.getElementById('popover-time-info').innerText = `${dia}-feira às ${hora}`;

    document.getElementById('custom-label').value = '';
    document.getElementById('custom-sigla').value = '';

    // Posicionar Popover
    const rect = event.currentTarget.getBoundingClientRect();
    const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    popover.style.display = 'block';

    let leftPos = rect.left + scrollLeft - (popover.offsetWidth / 2) + (rect.width / 2);
    let topPos = rect.top + scrollTop - popover.offsetHeight - 8;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Ajuste horizontal (evitar sair pelas laterais da janela)
    if (leftPos < 10) {
        leftPos = 10;
    } else if (leftPos + popover.offsetWidth > scrollLeft + viewportWidth - 10) {
        leftPos = scrollLeft + viewportWidth - popover.offsetWidth - 10;
    }

    // Ajuste vertical (evitar sair pelo topo da janela)
    // Se sair pelo topo, joga para baixo da célula
    if (rect.top - popover.offsetHeight - 8 < 10) {
        topPos = rect.bottom + scrollTop + 8;
    }

    // Se sair por baixo, joga para cima da base da janela
    if (topPos + popover.offsetHeight > scrollTop + viewportHeight - 10) {
        topPos = scrollTop + viewportHeight - popover.offsetHeight - 10;
    }

    // Garantia final para não sumir acima do topo do documento
    if (topPos < 10) topPos = 10;

    popover.style.left = `${leftPos}px`;
    popover.style.top = `${topPos}px`;
}

function closePopover() {
    const popover = document.getElementById('popover-schedule-menu');
    if (popover) popover.style.display = 'none';
    activePopover = { alunoNome: null, dia: null, horario: null, targetCell: null };
}

function openConflictResolutionModal(message, onConfirm) {
    const modal = document.getElementById('conflict-resolution-modal-overlay');
    if (!modal) return;
    document.getElementById('conflict-message-text').innerHTML = message;

    const confirmBtn = document.getElementById('btn-confirm-conflict-swap');
    confirmBtn.onclick = () => {
        onConfirm();
    };
    modal.classList.add('active');
}

function closeConflictResolutionModal() {
    const modal = document.getElementById('conflict-resolution-modal-overlay');
    if (modal) modal.classList.remove('active');
}

async function updateCellStatus(newStatus) {
    await runUpdateCellStatus(newStatus, false);
}

async function runUpdateCellStatus(newStatus, forceSwap = false, activeParams = null) {
    const params = activeParams || { ...activePopover };
    const { alunoNome, dia, horario } = params;
    if (!alunoNome) return;

    let statusValue = newStatus;
    if (newStatus === 'custom') {
        const label = document.getElementById('custom-label').value.trim();
        const sigla = document.getElementById('custom-sigla').value.trim().toUpperCase();

        if (!label || !sigla) {
            alert('Preencha a descrição e a sigla do compromisso customizado.');
            return;
        }
        statusValue = label;
    }

    if (!forceSwap) {
        closePopover();
    }

    // Enviar alteração via POST para o Flask
    try {
        const response = await fetch('/aluno/update_schedule/' + window.flaskData.turmaId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                aluno: alunoNome,
                dia: dia,
                horario: horario,
                status: statusValue,
                force_swap: forceSwap
            })
        });

        if (response.ok) {
            const data = await response.json();

            // Atualizar cache local
            if (!studentSchedules[alunoNome]) studentSchedules[alunoNome] = {};
            studentSchedules[alunoNome][`${dia}_${horario}`] = statusValue;

            if (forceSwap) {
                // Recarrega a página para manter grupos, alertas e visualizações 100% sincronizados
                window.location.reload();
                return;
            }

            renderSpreadsheet();
            recalculateConflicts();

            if (data.conflito) {
                showToast('Novo Conflito Gerado', `A agenda de ${alunoNome} agora conflita com a imersão do Grupo ${data.grupo}!`, 'danger');
            } else {
                showToast('Horário Atualizado', 'Alteração salva no banco de dados.', 'success');
            }
        } else {
            if (response.status === 409) {
                const resData = await response.json();
                const msg = `O aluno <strong>${resData.conflicting_student}</strong> (${resData.conflicting_turma_name}) já possui o compromisso <strong>${resData.materia_nome}</strong> agendado para ${dia}-feira às ${horario}.`;
                openConflictResolutionModal(msg, () => {
                    closeConflictResolutionModal();
                    runUpdateCellStatus(newStatus, true, params);
                });
                return;
            }
            let errorMsg = 'Não foi possível atualizar o horário no servidor.';
            try {
                const errData = await response.json();
                if (errData && errData.error) {
                    errorMsg = errData.error;
                }
            } catch (e) { }
            showToast('Erro ao Salvar', errorMsg, 'danger');
        }
    } catch (error) {
        console.error('Erro de rede ao salvar horário:', error);
        showToast('Erro de Conexão', 'Verifique a conexão de rede.', 'danger');
    }
}

// ==========================================================================
// GERENCIADOR DE GRUPOS (KANBAN DE COLUNAS & DRAG AND DROP)
// ==========================================================================
function renderKanban() {
    const container = document.getElementById('kanban-columns-container');
    if (!container) return;
    container.innerHTML = '';

    const grupos = window.flaskData.grupos;
    const blocos = window.flaskData.blocos;

    grupos.forEach(g => {
        // Encontrar bloco correspondente
        const hours = parseHorarioMinutes(g.Horário);
        const bloco = blocos.find(b => b.id === `b${g.Grupo}`) || { dia: g.Dia, inicio: hours.inicio, fim: hours.fim };
        const hasConflict = activeConflicts.some(c => c.alunoGrupo === g.Grupo);

        const col = document.createElement('div');
        col.className = 'glass-panel kanban-column';
        if (hasConflict) {
            col.classList.add('com-conflito');
        }
        col.id = `kanban-col-grupo-${g.Grupo}`;

        col.setAttribute('ondragover', 'allowDrop(event)');
        col.setAttribute('ondragleave', 'handleDragLeave(event)');
        col.setAttribute('ondrop', `handleDrop(event, ${g.Grupo})`);

        col.innerHTML = `
            <div class="column-header">
                <div>
                    <h3>Grupo ${g.Grupo}</h3>
                    <span style="font-size:0.7rem; color: var(--text-muted); font-weight:600;">
                        🗓️ ${g.Dia} (${g.Horário})
                    </span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div class="grp-badge">${g.Membros.length} alunos</div>
                    <div class="export-dropdown" id="export-dropdown-grp-${g.Grupo}" style="margin: 0;">
                        <button class="btn btn-secondary" style="padding: 2px 6px; font-size: 0.75rem;" onclick="toggleGroupExportMenu(${g.Grupo}); event.stopPropagation();">
                            ⬇️
                        </button>
                        <div class="export-menu" style="width: 140px; right: 0;">
                            <a href="/download/grupo/${window.flaskData.turmaId}/${g.Grupo}?format=xlsx" class="export-item" style="padding: 6px 12px; font-size: 0.75rem; text-decoration: none;">Excel (.xlsx)</a>
                            <a href="/download/grupo/${window.flaskData.turmaId}/${g.Grupo}?format=csv" class="export-item" style="padding: 6px 12px; font-size: 0.75rem; text-decoration: none;">CSV</a>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="column-cards-container" id="column-cards-grp-${g.Grupo}"></div>
            
            <button class="btn btn-secondary" style="margin-top: 14px; font-size: 0.75rem; padding: 6px;" onclick="openGroupMatrix(${g.Grupo})">
                👁️ Ver Compatibilidade
            </button>
        `;
        container.appendChild(col);

        const cardsContainer = document.getElementById(`column-cards-grp-${g.Grupo}`);
        g.Membros.forEach(m => {
            const card = createStudentCard(m.nome, g.Grupo);
            cardsContainer.appendChild(card);
        });
    });

    // Hidratar banco de alunos fora de grupo (Removidos)
    const bancoContainer = document.getElementById('banco-removidos-dropzone');
    if (bancoContainer) {
        bancoContainer.innerHTML = '';
        window.flaskData.alunosSemGrupo.forEach(alunoNome => {
            const card = createStudentCard(alunoNome, null);
            bancoContainer.appendChild(card);
        });
    }
}

function createStudentCard(alunoNome, grupoId) {
    const card = document.createElement('div');
    card.className = 'student-card';
    card.setAttribute('draggable', 'true');
    card.id = `stud-card-${alunoNome.replace(/\s+/g, '-')}`;

    const temConflito = activeConflicts.some(c => c.alunoNome.toLowerCase() === alunoNome.toLowerCase());
    if (temConflito) {
        card.style.borderColor = 'var(--color-danger)';
        card.style.background = 'rgba(239, 68, 68, 0.03)';
    }

    card.innerHTML = `
        <div class="student-card-header">
            <div class="stud-avatar" style="background:${temConflito ? 'var(--color-danger)' : 'var(--color-primary)'}">
                ${alunoNome[0].toUpperCase()}
            </div>
            <span class="stud-name">${alunoNome}</span>
            ${temConflito ? '<span style="font-size:0.9rem; margin-left:auto;">⚠️</span>' : ''}
        </div>
        <div class="sugestoes-block">
            <button class="sugs-btn" onclick="toggleSugDropdown(event, '${alunoNome}', ${grupoId})">
                <span>Sugestões de Troca</span>
                <span style="font-size: 8px;">▼</span>
            </button>
            <div class="sugs-dropdown" id="sugs-dropdown-${alunoNome.replace(/\s+/g, '-')}"></div>
        </div>
    `;

    // Ligar eventos Drag
    card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', alunoNome);
        e.dataTransfer.setData('grupo-origem', String(grupoId));
        card.classList.add('dragging');
        highlightCompatibleColumns(alunoNome);
    });

    card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
        clearColumnHighlights();
    });

    return card;
}

// Highlights durante o arrasto
function highlightCompatibleColumns(alunoNome) {
    const grupos = window.flaskData.grupos;
    grupos.forEach(g => {
        const col = document.getElementById(`kanban-col-grupo-${g.Grupo}`);
        if (!col) return;

        const isCompatible = isStudentCompatibleWithGroup(alunoNome, g.Grupo);
        if (isCompatible) {
            col.classList.add('compativel');
        } else {
            col.classList.add('incompativel');
        }
    });
}

function clearColumnHighlights() {
    document.querySelectorAll('.kanban-column').forEach(col => {
        col.classList.remove('compativel');
        col.classList.remove('incompativel');
    });
}

function allowDrop(ev) {
    ev.preventDefault();
    const col = ev.currentTarget;
    if (col.classList.contains('kanban-column') || col.id === 'banco-removidos-dropzone') {
        col.style.boxShadow = 'inset 0 0 10px rgba(79, 70, 229, 0.15)';
    }
}

function handleDragLeave(ev) {
    ev.currentTarget.style.boxShadow = 'none';
}

function handleDrop(ev, destGrupo) {
    ev.preventDefault();
    ev.currentTarget.style.boxShadow = 'none';

    const alunoNome = ev.dataTransfer.getData('text/plain');
    const origGrupoStr = ev.dataTransfer.getData('grupo-origem');
    const origGrupo = origGrupoStr === 'null' ? null : parseInt(origGrupoStr);
    const destGrupoVal = destGrupo === 'banco' ? null : destGrupo;

    if (origGrupo === destGrupoVal) return;

    // Executar a mudança no banco (POST para /trocar_aluno e reload)
    executeMoveOnServer(alunoNome, origGrupo, destGrupoVal);
}

function executeMoveOnServer(alunoNome, grupoAId, grupoBId) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/trocar_aluno/' + window.flaskData.turmaId;

    const inputA = document.createElement('input');
    inputA.type = 'hidden';
    inputA.name = 'aluno_a';
    inputA.value = alunoNome;
    form.appendChild(inputA);

    if (grupoAId !== null) {
        const inputGrpA = document.createElement('input');
        inputGrpA.type = 'hidden';
        inputGrpA.name = 'grupo_a_id';
        inputGrpA.value = String(grupoAId);
        form.appendChild(inputGrpA);
    }

    if (grupoBId !== null) {
        const inputGrpB = document.createElement('input');
        inputGrpB.type = 'hidden';
        inputGrpB.name = 'grupo_b_id';
        inputGrpB.value = String(grupoBId);
        form.appendChild(inputGrpB);
    }

    document.body.appendChild(form);

    // Salvar aba ativa para restaurar pós-refresh
    localStorage.setItem('academysync_active_tab', 'groups');
    form.submit();
}

// Lógica local de validação de compatibilidade
function isStudentCompatibleWithGroup(alunoNome, grupoNum) {
    const g = window.flaskData.grupos.find(x => x.Grupo === grupoNum);
    const blocos = window.flaskData.blocos;
    if (!g) return true;

    // Mapear dia e hora
    const diaAbrevMap = { 'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta', 'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado' };
    const diaCompleto = diaAbrevMap[g.Dia] || g.Dia;

    const hours = parseHorarioMinutes(g.Horário);
    const hInicio = hours.inicio, hFim = hours.fim;

    const agenda = studentSchedules[alunoNome] || {};

    for (const slot of HORARIOS) {
        const m = slotToMinutes(slot);
        if (m < hInicio || m >= hFim) continue;
        const state = agenda[`${diaCompleto}_${slot}`] || 'free';
        if (state !== 'free') {
            return false;
        }
    }
    return true;
}

// ==========================================================================
// CÁLCULO E DETECÇÃO DE CONFLITOS DE HORÁRIOS
// ==========================================================================
function recalculateConflicts() {
    activeConflicts = [];
    const grupos = window.flaskData.grupos;
    if (grupos.length === 0) return;

    grupos.forEach(g => {
        g.Membros.forEach(m => {
            const compat = isStudentCompatibleWithGroup(m.nome, g.Grupo);
            if (!compat) {
                activeConflicts.push({
                    alunoNome: m.nome,
                    alunoGrupo: g.Grupo,
                    dia: g.Dia,
                    horario: g.Horário
                });
            }
        });
    });

    // Atualizar Badge de Notificações
    const badge = document.getElementById('alerts-count-badge');
    if (badge) badge.innerText = activeConflicts.length;

    renderAlertsDrawer();
}

// ==========================================================================
// GAVETA LATERAL DE PENDÊNCIAS (DRAWER)
// ==========================================================================
function toggleAlertDrawer(open) {
    const drawer = document.getElementById('alerts-sidebar-drawer');
    if (!drawer) return;
    if (open) {
        drawer.classList.add('open');
    } else {
        drawer.classList.remove('open');
    }
}

function renderAlertsDrawer() {
    const list = document.getElementById('alerts-drawer-list');
    if (!list) return;
    list.innerHTML = '';

    if (activeConflicts.length === 0) {
        list.innerHTML = `
            <div style="text-align:center; padding: 40px 10px; color: var(--text-muted);">
                <div style="font-size: 2rem; margin-bottom: 10px;">🎉</div>
                <h5 style="font-size:0.9rem; font-weight:700; color: var(--text-main);">Tudo em ordem!</h5>
                <p style="font-size:0.75rem; margin-top:4px;">Nenhum choque de horário nos grupos da turma.</p>
            </div>
        `;
        return;
    }

    activeConflicts.forEach(c => {
        const card = document.createElement('div');
        card.className = 'alert-card';
        card.innerHTML = `
            <h6>Incompatibilidade de Horário</h6>
            <p><strong>${c.alunoNome}</strong> colide com o horário do <strong>Grupo ${c.alunoGrupo}</strong> (${c.dia} das ${c.horario}).</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                <span class="alert-card-action" onclick="focusConflictStudent('${c.alunoNome}')">Localizar Aluno</span>
            </div>
        `;
        list.appendChild(card);
    });
}

function focusConflictStudent(alunoNome) {
    toggleAlertDrawer(false);

    if (localStorage.getItem('academysync_active_tab') === 'spreadsheet') {
        renderSpreadsheet();
        showToast('Localizado', `Encontre a linha de ${alunoNome} na planilha geral.`, 'info');
    } else {
        const cardId = `stud-card-${alunoNome.replace(/\s+/g, '-')}`;
        const card = document.getElementById(cardId);
        if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.style.transform = 'scale(1.08)';
            setTimeout(() => card.style.transform = 'none', 1000);
        }
    }
}

// ==========================================================================
// SUGESTÕES INTELIGENTES NO KANBAN CARD
// ==========================================================================
function toggleSugDropdown(event, alunoNome, grupoId) {
    event.stopPropagation();
    const dd = document.getElementById(`sugs-dropdown-${alunoNome.replace(/\s+/g, '-')}`);
    if (!dd) return;
    const isActive = dd.classList.contains('active');

    document.querySelectorAll('.sugs-dropdown').forEach(el => el.classList.remove('active'));

    if (!isActive) {
        dd.classList.add('active');
        renderSuggestions(alunoNome, grupoId, dd);
    }
}

function renderSuggestions(alunoNome, grupoId, container) {
    container.innerHTML = '';
    const grupos = window.flaskData.grupos;

    // Mapear compatibilidade direta com grupos
    let compGrupos = [];
    grupos.forEach(g => {
        if (g.Grupo !== grupoId) {
            if (isStudentCompatibleWithGroup(alunoNome, g.Grupo)) {
                compGrupos.push(g.Grupo);
            }
        }
    });

    if (compGrupos.length === 0) {
        // Tentar sugestão de trocas 1-para-1 a partir das sugestões vindas do Flask
        const gOrig = grupos.find(x => x.Grupo === grupoId);
        let m = gOrig ? gOrig.Membros.find(x => x.nome.toLowerCase() === alunoNome.toLowerCase()) : null;

        if (m && m.sugestoes && m.sugestoes.troca_simples && m.sugestoes.troca_simples.length > 0) {
            m.sugestoes.troca_simples.forEach(t => {
                const item = document.createElement('div');
                item.className = 'sug-item';
                item.innerHTML = `🔄 Trocar com <strong>${t.trocar_com}</strong> (Grupo ${t.grupo_destino})`;

                // Evento clique da troca
                item.onclick = () => {
                    executeSwapOnServer(alunoNome, grupoId, t.trocar_com, t.grupo_destino);
                };
                container.appendChild(item);
            });
        } else {
            container.innerHTML = `<span style="font-size:0.7rem; color:var(--text-muted);">Sem opções viáveis. Modifique a planilha geral.</span>`;
        }
    } else {
        compGrupos.forEach(gId => {
            const item = document.createElement('div');
            item.className = 'sug-item';
            item.innerHTML = `➡️ Mover para <strong>Grupo ${gId}</strong> (Compatível)`;
            item.onclick = () => {
                executeMoveOnServer(alunoNome, grupoId, gId);
            };
            container.appendChild(item);
        });
    }
}

function executeSwapOnServer(alunoA, grupoA, alunoB, grupoB) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/trocar_aluno/' + window.flaskData.turmaId;

    const inputA = document.createElement('input');
    inputA.type = 'hidden';
    inputA.name = 'aluno_a';
    inputA.value = alunoA;
    form.appendChild(inputA);

    const inputGrpA = document.createElement('input');
    inputGrpA.type = 'hidden';
    inputGrpA.name = 'grupo_a_id';
    inputGrpA.value = String(grupoA);
    form.appendChild(inputGrpA);

    const inputB = document.createElement('input');
    inputB.type = 'hidden';
    inputB.name = 'aluno_b';
    inputB.value = alunoB;
    form.appendChild(inputB);

    const inputGrpB = document.createElement('input');
    inputGrpB.type = 'hidden';
    inputGrpB.name = 'grupo_b_id';
    inputGrpB.value = String(grupoB);
    form.appendChild(inputGrpB);

    document.body.appendChild(form);

    localStorage.setItem('academysync_active_tab', 'groups');
    form.submit();
}

// ==========================================================================
// MODAL MATRIZ DE COMPATIBILIDADE DE GRUPOS (SÍNCRONIA DETALHADA)
// ==========================================================================
function openGroupMatrix(grupoNum) {
    const modal = document.getElementById('group-details-modal');
    if (!modal) return;

    document.getElementById('modal-group-title').innerText = `Grupo ${grupoNum} - Calendário de Compatibilidade`;
    const table = document.getElementById('group-matrix-compatibility-table');
    table.innerHTML = '';

    const g = window.flaskData.grupos.find(x => x.Grupo === grupoNum);
    if (!g) return;

    // Header horas
    const trHeader = document.createElement('tr');
    trHeader.innerHTML = `<th>Dia</th>`;
    HORARIOS.forEach(h => {
        trHeader.innerHTML += `<th>${h}</th>`;
    });
    table.appendChild(trHeader);

    // Linha dias
    DIAS_SEMANA.forEach(dia => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td style="font-weight:700;">${dia}</td>`;

        HORARIOS.forEach(h => {
            let todosLivres = true;
            let livresCount = 0;

            g.Membros.forEach(m => {
                const agenda = studentSchedules[m.nome] || {};
                const state = agenda[`${dia}_${h}`] || 'free';
                if (state === 'free') {
                    livresCount++;
                } else {
                    todosLivres = false;
                }
            });

            // Verificar se é o slot ativo de reuniões
            const diaAbrevMap = { 'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta', 'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado' };
            const isImersao = (diaAbrevMap[g.Dia] === dia); // Comparação simplificada por dia

            const td = document.createElement('td');
            td.className = 'group-matrix-cell';

            if (todosLivres) {
                td.className += ' free-sinc';
                td.innerText = 'LIVRE';
                td.style.fontSize = '0.62rem';
                td.style.fontWeight = 'bold';
                td.style.color = 'var(--cell-free-text)';
            } else {
                td.className += ' blocked-sinc';
                td.innerText = `${livresCount}/${g.Membros.length}`;
                td.style.fontSize = '0.65rem';
                td.style.color = 'var(--cell-class-text)';
            }

            if (isImersao) {
                td.style.border = '2px solid var(--color-primary)';
            }

            tr.appendChild(td);
        });
        table.appendChild(tr);
    });

    modal.classList.add('active');
}

function closeGroupModal() {
    const modal = document.getElementById('group-details-modal');
    if (modal) modal.classList.remove('active');
}

// ==========================================================================
// MODAL RECONFIGURAÇÃO RÁPIDA & SENHA
// ==========================================================================
function showConfigPanelFromWorkspace() {
    const modal = document.getElementById('reconfig-groups-modal-overlay');
    if (modal) modal.classList.add('active');
}

function closeConfigPanelFromWorkspace() {
    const modal = document.getElementById('reconfig-groups-modal-overlay');
    if (modal) modal.classList.remove('active');
}

function openChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    if (modal) modal.classList.add('active');
}

function closeChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    if (modal) modal.classList.remove('active');
}

function openSecurityQuestionModal() {
    const modal = document.getElementById('security-question-modal');
    if (modal) modal.classList.add('active');
}

function closeSecurityQuestionModal() {
    const modal = document.getElementById('security-question-modal');
    if (modal) modal.classList.remove('active');
}

function toggleCustomQuestion(selectElement, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const inputField = container.querySelector('input');
    if (selectElement.value === 'custom') {
        container.style.display = 'block';
        if (inputField) inputField.setAttribute('required', 'required');
    } else {
        container.style.display = 'none';
        if (inputField) {
            inputField.removeAttribute('required');
            inputField.value = '';
        }
    }
}

function toggleExportMenu(id) {
    const wrapper = document.getElementById(id);
    if (wrapper) {
        document.querySelectorAll('.export-dropdown').forEach(el => {
            if (el.id !== id) el.classList.remove('active');
        });
        wrapper.classList.toggle('active');
    }
}

function toggleGroupExportMenu(grupoId) {
    const id = `export-dropdown-grp-${grupoId}`;
    toggleExportMenu(id);
}

// ==========================================================================
// COMPONENTES AUXILIARES DO WIZARD DE CRIAÇÃO (PASSO 2)
// ==========================================================================
function addNewConfigBlock() {
    const list = document.getElementById('config-blocks-list');
    const temp = document.getElementById('new-block-template');
    if (!list || !temp) return;

    const idx = list.children.length;
    const card = document.createElement('div');
    card.className = 'bloco-edit-card';
    card.id = `config-bloco-card-${idx}`;
    card.innerHTML = `<button type="button" class="bloco-remove-btn" onclick="this.parentElement.remove()">&times;</button>`;

    const fields = temp.cloneNode(true);
    fields.style.display = 'grid';
    card.appendChild(fields);
    list.appendChild(card);
}

function addNewReconfigBlock() {
    const list = document.getElementById('reconfig-blocks-list');
    const temp = document.getElementById('new-block-template');
    if (!list || !temp) return;

    const idx = list.children.length + 50;
    const card = document.createElement('div');
    card.className = 'bloco-edit-card';
    card.id = `reconfig-bloco-card-${idx}`;
    card.innerHTML = `<button type="button" class="bloco-remove-btn" onclick="this.parentElement.remove()">&times;</button>`;

    const fields = temp.cloneNode(true);
    fields.style.display = 'grid';
    card.appendChild(fields);
    list.appendChild(card);
}

// Drag and drop do Passo 1 do Wizard
function setupDragDropWizard() {
    const dropArea = document.getElementById('drag-drop-area-real');
    const fileInput = document.getElementById('pdf-files-real');
    const list = document.getElementById('selected-files-list-real');
    if (!dropArea || !fileInput) return;

    dropArea.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        renderFileList(e.target.files, list);
    });

    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('drag-over');
    });

    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('drag-over');
    });

    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('drag-over');
        fileInput.files = e.dataTransfer.files;
        renderFileList(e.dataTransfer.files, list);
    });
}

function renderFileList(files, container) {
    container.innerHTML = '';
    Array.from(files).forEach(file => {
        if (file.name.endsWith('.pdf')) {
            const item = document.createElement('div');
            item.className = 'selected-file-item';
            item.innerHTML = `<span>📄 ${file.name}</span>`;
            container.appendChild(item);
        }
    });
}

function setupUploadProgress() {
    const form = document.getElementById('upload-form-real');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        const fileInput = document.getElementById('pdf-files-real');
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            return; // let HTML5 validation handle empty file selection
        }

        e.preventDefault();

        // Show overlay
        const overlay = document.getElementById('upload-progress-overlay');
        const title = document.getElementById('progress-title');
        const status = document.getElementById('progress-status');
        const barFill = document.getElementById('progress-bar-fill');
        const percentage = document.getElementById('progress-percentage');

        if (overlay) overlay.classList.add('active');
        if (title) title.innerText = "Preparando Envio";
        if (status) status.innerText = "Empacotando atestados para transmissão...";
        if (barFill) barFill.style.width = "0%";
        if (percentage) percentage.innerText = "0%";

        const formData = new FormData(form);
        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                if (barFill) barFill.style.width = percent + "%";
                if (percentage) percentage.innerText = percent + "%";

                if (percent < 100) {
                    if (title) title.innerText = "Enviando Atestados";
                    if (status) status.innerText = `Enviando arquivos para o servidor: ${percent}% concluído.`;
                } else {
                    if (title) title.innerText = "Envio Concluído";
                    if (status) status.innerText = "Arquivos recebidos com sucesso! Processando e extraindo horários...";
                }
            }
        });

        // Track response completion
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                if (status) status.innerText = "Processamento concluído com sucesso! Atualizando workspace...";
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success && response.redirect_url) {
                        setTimeout(() => {
                            window.location.href = response.redirect_url;
                        }, 800);
                        return;
                    }
                } catch (e) {
                    // Fallback to standard redirect
                }
                setTimeout(() => {
                    if (xhr.responseURL) {
                        window.location.href = xhr.responseURL;
                    } else {
                        window.location.reload();
                    }
                }, 800);
            } else {
                if (overlay) overlay.classList.remove('active');
                console.error("Erro no upload de PDFs. Status:", xhr.status, "Texto:", xhr.statusText, "Resposta:", xhr.responseText);
                showToast("Erro de Processamento", "Ocorreu um erro ao enviar e processar os PDFs.", "danger");
            }
        };

        xhr.onerror = () => {
            if (overlay) overlay.classList.remove('active');
            console.error("Erro de conexão/rede no upload de PDFs.");
            showToast("Erro de Conexão", "Não foi possível conectar ao servidor para enviar os arquivos.", "danger");
        };

        xhr.open('POST', form.getAttribute('action'), true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send(formData);
    });
}

function initBlocksListInWizard() {
    // Adiciona bloco extra por padrão no wizard se vazio
    const list = document.getElementById('config-blocks-list');
    if (list && list.children.length === 1) {
        addNewConfigBlock();
    }
}

// ==========================================================================
// TOASTER NOTIFICATIONS SYSTEM
// ==========================================================================
function showToast(title, desc, type = 'info') {
    const container = document.getElementById('toast-messages-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';

    let icon = 'ℹ️';
    let border = 'var(--color-primary)';

    if (type === 'success') {
        icon = '✅';
        border = 'var(--color-success)';
    } else if (type === 'danger') {
        icon = '⚠️';
        border = 'var(--color-danger)';
    } else if (type === 'warning') {
        icon = '⚠️';
        border = 'var(--color-warning)';
    } else if (type === 'info') {
        icon = 'ℹ️';
        border = 'var(--color-secondary)';
    }

    toast.style.borderLeftColor = border;

    toast.innerHTML = `
        <div style="font-size: 1.2rem;">${icon}</div>
        <div class="toast-content">
            <h5>${title}</h5>
            <p>${desc}</p>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function openUnprocessedPDFsModal(data) {
    const modal = document.getElementById('unprocessed-pdfs-modal-overlay');
    const summary = document.getElementById('unprocessed-modal-summary');
    const list = document.getElementById('unprocessed-modal-files-list');
    if (!modal || !summary || !list) return;

    const falhas = data.falha_arquivos || [];
    const numAlunos = data.num_alunos || 0;
    const totalPDFs = data.total_pdfs || (numAlunos + falhas.length);
    const naoProcessadosCount = data.nao_processados_count || falhas.length;
    const turmaNome = data.turma_nome || '';

    if (numAlunos > 0) {
        summary.innerHTML = `Dos <strong>${totalPDFs} arquivo(s) PDF</strong> enviados para a turma <strong>"${turmaNome}"</strong>, <strong>${numAlunos} aluno(s)</strong> foram cadastrados com sucesso. No entanto, <strong>${naoProcessadosCount} arquivo(s) PDF não foram processados</strong>:`;
    } else {
        summary.innerHTML = `Não foi possível processar <strong>${naoProcessadosCount} de ${totalPDFs} arquivo(s) PDF</strong> enviados para a turma <strong>"${turmaNome}"</strong>:`;
    }

    list.innerHTML = '';
    falhas.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.style.cssText = "display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding: 6px 0; border-bottom: 1px dashed var(--border-color); font-size: 0.85rem;";

        let fileName = typeof item === 'string' ? item : item.file;
        let type = typeof item === 'object' ? item.type : 'leitura';
        let alunoNome = typeof item === 'object' ? item.aluno : null;

        let icon = type === 'duplicado' ? 'ℹ️' : '📄';
        let color = type === 'duplicado' ? 'var(--text-main)' : '#DC2626';
        let reasonBadge = type === 'duplicado'
            ? `<span style="font-size: 0.75rem; background: rgba(59, 130, 246, 0.1); color: #2563EB; padding: 2px 8px; border-radius: 12px; font-weight: 600;">Aluno Duplicado${alunoNome ? ': ' + alunoNome : ''}</span>`
            : `<span style="font-size: 0.75rem; background: rgba(239, 68, 68, 0.1); color: #DC2626; padding: 2px 8px; border-radius: 12px; font-weight: 600;">Erro de Leitura</span>`;

        itemEl.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; color: ${color}; font-weight: 600; word-break: break-all;">
                <span>${icon}</span>
                <span>${fileName}</span>
            </div>
            <div style="flex-shrink: 0;">${reasonBadge}</div>
        `;
        list.appendChild(itemEl);
    });

    modal.classList.add('active');
    modal.style.display = 'flex';
}

function closeUnprocessedPDFsModal() {
    const modal = document.getElementById('unprocessed-pdfs-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    if (typeof window.onUnprocessedModalClose === 'function') {
        const cb = window.onUnprocessedModalClose;
        window.onUnprocessedModalClose = null;
        cb();
    }
}

// ==========================================================================
// GESTÃO DO MODAL "ADD ALUNO" NA PÁGINA DA TURMA ESPECÍFICA (WORKSPACE)
// ==========================================================================
let turmaAddAlunoFilesList = [];
let pendingTurmaAddAlunoFormData = null;

/**
 * Abre o modal "Adicionar Alunos" para a turma aberta no momento.
 */
function openTurmaAddAlunoModal() {
    turmaAddAlunoFilesList = [];
    renderTurmaAddAlunoFilesList();
    const modal = document.getElementById('turma-add-aluno-modal-overlay');
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

/**
 * Fecha o modal "Adicionar Alunos" da turma e reseta os arquivos selecionados.
 */
function closeTurmaAddAlunoModal() {
    const modal = document.getElementById('turma-add-aluno-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    turmaAddAlunoFilesList = [];
    const input = document.getElementById('turma-pdf-files-input');
    if (input) input.value = '';
}

/**
 * Trata a seleção de múltiplos PDFs pelo input de arquivo.
 * @param {Event} event Evento change do input file.
 */
function handleTurmaAddAlunoFilesSelect(event) {
    const files = Array.from(event.target.files);
    if (!files || files.length === 0) return;

    files.forEach(f => {
        if (f.name.endsWith('.pdf')) {
            turmaAddAlunoFilesList.push(f);
        }
    });

    event.target.value = '';
    renderTurmaAddAlunoFilesList();
}

/**
 * Remove um arquivo anexado da lista pelo seu índice.
 * @param {number} index Índice do arquivo no array turmaAddAlunoFilesList.
 */
function removeTurmaAddAlunoFile(index) {
    turmaAddAlunoFilesList.splice(index, 1);
    renderTurmaAddAlunoFilesList();
}

/**
 * Renderiza dinamicamente a lista de arquivos selecionados no modal da turma.
 */
function renderTurmaAddAlunoFilesList() {
    const container = document.getElementById('turma-pdf-files-list');
    const badge = document.getElementById('turma-pdf-count-badge');
    if (!container) return;

    if (badge) {
        badge.innerText = `${turmaAddAlunoFilesList.length} arquivo(s)`;
        badge.style.background = turmaAddAlunoFilesList.length > 0 ? 'rgba(16,185,129,0.12)' : 'rgba(0,0,0,0.04)';
        badge.style.color = turmaAddAlunoFilesList.length > 0 ? 'var(--color-success)' : 'var(--text-muted)';
    }

    if (turmaAddAlunoFilesList.length === 0) {
        container.innerHTML = `
            <div style="font-size: 0.84rem; color: var(--text-muted); font-style: italic; text-align: center; padding: 16px 0; background: rgba(0,0,0,0.02); border: 1px dashed var(--border-color); border-radius: 8px;">
                Nenhum arquivo PDF selecionado. Clique no botão acima para adicionar.
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    turmaAddAlunoFilesList.forEach((file, idx) => {
        const item = document.createElement('div');
        item.style.cssText = 'display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.03); border: 1px solid var(--border-color); padding: 8px 12px; border-radius: 8px; font-size: 0.85rem;';
        item.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 85%;">
                <span style="color: #EF4444;">📄</span>
                <span style="font-weight: 600; color: var(--text-main);">${file.name}</span>
                <span style="color: var(--text-muted); font-size: 0.75rem;">(${(file.size / 1024).toFixed(1)} KB)</span>
            </div>
            <button type="button" class="btn btn-secondary" onclick="removeTurmaAddAlunoFile(${idx})" style="padding: 4px 8px; color: #EF4444; border-color: rgba(239,68,68,0.3); font-size: 0.8rem;" title="Remover PDF">&times;</button>
        `;
        container.appendChild(item);
    });
}

/**
 * Submete os PDFs da turma via AJAX POST /turma/<turma_id>/add_alunos.
 * @param {Event|null} event Evento de envio do formulário.
 * @param {boolean} forceConfirm Se true, envia confirm_update=true.
 */
async function submitTurmaAddAlunos(event, forceConfirm = false) {
    if (event) event.preventDefault();

    const turmaId = window.flaskData ? window.flaskData.turmaId : null;
    if (!turmaId) {
        showToast('Erro', 'Identificador da turma não encontrado.', 'danger');
        return;
    }

    let formData;
    if (forceConfirm && pendingTurmaAddAlunoFormData) {
        formData = pendingTurmaAddAlunoFormData;
        formData.set('confirm_update', 'true');
    } else {
        if (turmaAddAlunoFilesList.length === 0) {
            showToast('Aviso', 'Selecione ao menos um arquivo PDF antes de enviar.', 'warning');
            return;
        }

        formData = new FormData();
        turmaAddAlunoFilesList.forEach(file => {
            formData.append('pdf_files', file);
        });
    }

    const btnSave = document.getElementById('btn-save-turma-add-aluno');
    if (btnSave) {
        btnSave.disabled = true;
        btnSave.innerText = 'Processando...';
    }

    try {
        const response = await fetch(`/turma/${turmaId}/add_alunos`, {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        const data = await response.json();

        if (data.requires_confirmation) {
            pendingTurmaAddAlunoFormData = formData;
            openTurmaConfirmStudentUpdateModal(data);
        } else if (data.success) {
            closeTurmaAddAlunoModal();
            closeTurmaConfirmStudentUpdateModal();

            if (data.unprocessed_data && data.unprocessed_data.nao_processados_count > 0) {
                showToast('Aviso', 'Alguns PDFs não foram processados. Veja os detalhes.', 'warning');
                openUnprocessedPDFsModal(data.unprocessed_data);
                window.onUnprocessedModalClose = () => window.location.reload();
            } else {
                showToast('Sucesso', data.message || 'Aluno(s) adicionado(s) com sucesso!', 'success');
                setTimeout(() => window.location.reload(), 1200);
            }
        } else {
            showToast('Erro', data.error || 'Falha ao cadastrar alunos.', 'danger');
        }
    } catch (err) {
        console.error("Erro ao enviar PDFs para a turma:", err);
        showToast('Erro', 'Falha na comunicação com o servidor.', 'danger');
    } finally {
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.innerText = 'Confirmar e Enviar PDFs';
        }
    }
}

/**
 * Abre o modal de confirmação de alunos pré-existentes na turma.
 * @param {Object} data Resposta JSON do servidor contendo existing_students.
 */
function openTurmaConfirmStudentUpdateModal(data) {
    const modal = document.getElementById('turma-confirm-student-update-modal-overlay');
    const msg = document.getElementById('turma-confirm-student-update-message');
    const list = document.getElementById('turma-confirm-student-update-list');
    if (!modal || !msg || !list) return;

    const existing = data.existing_students || [];
    msg.innerHTML = `Identificamos que <strong>${existing.length} aluno(s)</strong> já estão cadastrado(s) nesta turma:`;
    
    list.innerHTML = '';
    existing.forEach(student => {
        const item = document.createElement('div');
        item.style.cssText = "display: flex; align-items: center; gap: 8px; color: #D97706; font-weight: 600; font-size: 0.85rem;";
        item.innerHTML = `<span>👤</span> <span>${student}</span>`;
        list.appendChild(item);
    });

    modal.classList.add('active');
    modal.style.display = 'flex';
}

/**
 * Fecha o modal de confirmação de aluno existente.
 */
function closeTurmaConfirmStudentUpdateModal() {
    const modal = document.getElementById('turma-confirm-student-update-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    pendingTurmaAddAlunoFormData = null;
}

/**
 * Prossegue com o envio após confirmação explícita do usuário de atualizar os horários do aluno.
 */
function proceedTurmaStudentUpdateConfirmation() {
    submitTurmaAddAlunos(null, true);
}

function displayFlaskFlashMessages() {
    if (window.flaskData.flashMessages) {
        window.flaskData.flashMessages.forEach(msg => {
            let cat = msg.category;
            if (cat === 'unprocessed_modal') {
                try {
                    let data = JSON.parse(msg.message);
                    openUnprocessedPDFsModal(data);
                } catch (e) {
                    console.error("Erro ao abrir modal de PDFs não processados:", e);
                }
            } else {
                let type = cat === 'error' || cat === 'danger' ? 'danger' : (cat === 'warning' ? 'warning' : (cat === 'success' ? 'success' : 'info'));
                let title = type === 'danger' ? 'Erro' : (type === 'warning' ? 'Aviso' : (type === 'success' ? 'Sucesso' : 'Notificação'));
                showToast(title, msg.message, type);
            }
        });
    }
}

function setupGlobalEventListeners() {
    // Clique fora fecha popover
    document.addEventListener('click', (e) => {
        const popover = document.getElementById('popover-schedule-menu');
        if (popover && popover.style.display === 'block') {
            const isInside = popover.contains(e.target);
            const isCell = e.target.classList.contains('sched-cell');
            if (!isInside && !isCell) {
                closePopover();
            }
        }

        if (!e.target.closest('.export-dropdown')) {
            document.querySelectorAll('.export-dropdown').forEach(el => {
                el.classList.remove('active');
            });
        }
    });
}

// ==========================================================================
// FILTROS E COMPARAÇÃO DE ALUNOS NA PLANILHA GERAL
// ==========================================================================
function initSpreadsheetFilters() {
    const groupSelect = document.getElementById('filter-group-select');
    if (!groupSelect) return;

    // Se o dropdown já foi preenchido com os grupos, evite repopular para não perder seleção
    if (groupSelect.children.length > 2) return;

    const grupos = window.flaskData.grupos || [];
    grupos.forEach(g => {
        const opt = document.createElement('option');
        opt.value = g.Grupo;
        opt.innerText = `Grupo ${g.Grupo}`;
        groupSelect.appendChild(opt);
    });
}

function handleGroupFilterChange(value) {
    activeGroupFilter = value;
    renderSpreadsheet();
}

function openCompareModal() {
    const modal = document.getElementById('compare-students-modal-overlay');
    if (modal) {
        modal.classList.add('active');
        // Limpar campo de busca
        const searchInput = document.getElementById('compare-search-input');
        if (searchInput) searchInput.value = '';

        populateCompareModalList();
    }
}

function closeCompareModal() {
    const modal = document.getElementById('compare-students-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
    }
}

function populateCompareModalList() {
    const container = document.getElementById('compare-students-list');
    if (!container) return;
    container.innerHTML = '';

    const listAlunos = window.flaskData.listaAlunos;
    if (listAlunos.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem; text-align: center;">Nenhum aluno cadastrado.</p>';
        return;
    }

    const grid = document.createElement('div');
    grid.className = 'compare-students-grid';

    listAlunos.forEach(alunoNome => {
        const item = document.createElement('div');
        item.className = 'compare-student-item';
        if (selectedCompareStudents.has(alunoNome)) {
            item.classList.add('selected');
        }

        const isChecked = selectedCompareStudents.has(alunoNome) ? 'checked' : '';

        item.innerHTML = `
            <input type="checkbox" id="chk-comp-${alunoNome}" value="${alunoNome}" ${isChecked} onchange="handleCompareCheckboxChange(this)">
            <label for="chk-comp-${alunoNome}">${alunoNome}</label>
        `;

        // Clicar no item todo também marca o checkbox
        item.addEventListener('click', (e) => {
            if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') {
                const chk = item.querySelector('input[type="checkbox"]');
                chk.checked = !chk.checked;
                handleCompareCheckboxChange(chk);
            }
        });

        grid.appendChild(item);
    });

    container.appendChild(grid);
}

function handleCompareCheckboxChange(checkbox) {
    const card = checkbox.closest('.compare-student-item');
    if (!card) return;

    if (checkbox.checked) {
        card.classList.add('selected');
    } else {
        card.classList.remove('selected');
    }
}

function filterCompareList() {
    const query = document.getElementById('compare-search-input').value.toLowerCase();
    const items = document.querySelectorAll('.compare-student-item');

    items.forEach(item => {
        const labelText = item.querySelector('label').innerText.toLowerCase();
        if (labelText.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function selectAllCompare(select) {
    const checkboxes = document.querySelectorAll('#compare-students-list input[type="checkbox"]');
    checkboxes.forEach(chk => {
        const item = chk.closest('.compare-student-item');
        // Só altera os que estão visíveis pela busca ativa
        if (item && item.style.display !== 'none') {
            chk.checked = select;
            handleCompareCheckboxChange(chk);
        }
    });
}

function applyCompareFilter() {
    const checkboxes = document.querySelectorAll('#compare-students-list input[type="checkbox"]');
    selectedCompareStudents.clear();

    checkboxes.forEach(chk => {
        if (chk.checked) {
            selectedCompareStudents.add(chk.value);
        }
    });

    closeCompareModal();
    renderSpreadsheet();
}

function clearAllFilters(e) {
    if (e) e.preventDefault();

    // Resetar filtro de grupo
    const groupSelect = document.getElementById('filter-group-select');
    if (groupSelect) groupSelect.value = 'all';
    activeGroupFilter = 'all';

    // Limpar comparação
    selectedCompareStudents.clear();

    renderSpreadsheet();
}

// ==========================================================================
// EXPORTAÇÃO UNIFICADA DE PLANILHAS (GRADE E GRUPOS)
// ==========================================================================
function getVisibleStudents() {
    if (!window.flaskData || !window.flaskData.listaAlunos) return [];
    const listAlunos = window.flaskData.listaAlunos || [];
    return listAlunos.filter(alunoNome => {
        if (activeGroupFilter !== 'all') {
            const grupoInfo = (window.flaskData.grupos || []).find(g => {
                return g.Membros.some(m => m.nome.toLowerCase() === alunoNome.toLowerCase());
            });
            if (activeGroupFilter === 'sem-grupo') {
                if (grupoInfo) return false;
            } else {
                if (!grupoInfo || String(grupoInfo.Grupo) !== String(activeGroupFilter)) return false;
            }
        }
        if (selectedCompareStudents.size > 0) {
            if (!selectedCompareStudents.has(alunoNome)) return false;
        }
        return true;
    });
}

function openUnifiedExportModal() {
    const overlay = document.getElementById('unified-export-modal-overlay');
    if (!overlay) return;

    const hasGroups = window.flaskData.hasGroups && window.flaskData.grupos && window.flaskData.grupos.length > 0;

    const groupFilterArea = document.getElementById('export-schedule-group-filter-area');
    const groupsSection = document.getElementById('export-groups-section-container');
    const filterNoticeArea = document.getElementById('workspace-export-filter-notice');
    const filterNoticeText = document.getElementById('workspace-export-filter-notice-text');

    const visibleStudents = getVisibleStudents();
    const allStudents = window.flaskData.listaAlunos || [];
    const isFiltered = (selectedCompareStudents.size > 0 || activeGroupFilter !== 'all');

    if (isFiltered && filterNoticeArea && filterNoticeText) {
        filterNoticeText.innerText = `Apenas os ${visibleStudents.length} de ${allStudents.length} alunos atualmente visíveis na tela serão incluídos na planilha.`;
        filterNoticeArea.style.display = 'block';
    } else if (filterNoticeArea) {
        filterNoticeArea.style.display = 'none';
    }

    if (hasGroups) {
        groupFilterArea.style.display = 'block';
        groupsSection.style.display = 'flex';

        const container = document.getElementById('export-groups-checkbox-list');
        const checkAllLabel = container.querySelector('label');
        const hr = container.querySelector('hr');

        container.innerHTML = '';
        container.appendChild(checkAllLabel);
        container.appendChild(hr);

        document.getElementById('export-check-all-groups').checked = true;

        const grupos = window.flaskData.grupos || [];
        grupos.forEach(g => {
            const lbl = document.createElement('label');
            lbl.style.cssText = "display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 4px; border-radius: 4px; font-size: 0.8rem; transition: background 0.15s ease;";
            lbl.innerHTML = `
                <input type="checkbox" class="export-group-checkbox" value="${g.Grupo}" checked onchange="updateExportCheckAllState()">
                <span>Grupo ${g.Grupo} — ${g.Dia} (${g.Horário})</span>
            `;
            container.appendChild(lbl);
        });

        const semGrupo = window.flaskData.alunosSemGrupo || [];
        if (semGrupo.length > 0) {
            const lbl = document.createElement('label');
            lbl.style.cssText = "display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 4px; border-radius: 4px; font-size: 0.8rem; transition: background 0.15s ease;";
            lbl.innerHTML = `
                <input type="checkbox" class="export-group-checkbox" value="sem-grupo" checked onchange="updateExportCheckAllState()">
                <span>Estudantes sem Grupo (${semGrupo.length})</span>
            `;
            container.appendChild(lbl);
        }
    } else {
        groupFilterArea.style.display = 'none';
        groupsSection.style.display = 'none';
    }

    overlay.style.display = 'flex';
}

function closeUnifiedExportModal() {
    const overlay = document.getElementById('unified-export-modal-overlay');
    if (overlay) overlay.style.display = 'none';
}

function toggleExportCheckAll(chk) {
    const checkboxes = document.querySelectorAll('.export-group-checkbox');
    checkboxes.forEach(c => c.checked = chk.checked);
}

function updateExportCheckAllState() {
    const checkboxes = Array.from(document.querySelectorAll('.export-group-checkbox'));
    const allChecked = checkboxes.every(c => c.checked);
    document.getElementById('export-check-all-groups').checked = allChecked;
}

function submitGroupExport(format) {
    const checkboxes = Array.from(document.querySelectorAll('.export-group-checkbox'));
    const hasGroups = window.flaskData.hasGroups && window.flaskData.grupos && window.flaskData.grupos.length > 0;
    const selected = hasGroups ? checkboxes.filter(c => c.checked).map(c => c.value) : [];

    if (hasGroups && selected.length === 0) {
        alert("Por favor, selecione pelo menos um grupo para exportar.");
        return;
    }

    const turmaId = window.flaskData.turmaId;
    let url = `/download/schedule/${format}/${turmaId}`;

    const isFiltered = (selectedCompareStudents.size > 0 || activeGroupFilter !== 'all');
    if (isFiltered) {
        const visibleStudents = getVisibleStudents();
        url += `?students=${encodeURIComponent(visibleStudents.join(','))}`;
    } else if (hasGroups) {
        const allChecked = document.getElementById('export-check-all-groups').checked;
        if (selected.length < checkboxes.length || !allChecked) {
            url += `?grupos=${selected.join(',')}`;
        }
    }

    window.location.href = url;
    closeUnifiedExportModal();
}

function toggleDayCollapse(dia) {
    const idx = collapsedDays.indexOf(dia);
    if (idx > -1) {
        collapsedDays.splice(idx, 1);
    } else {
        collapsedDays.push(dia);
    }
    localStorage.setItem('academysync_collapsed_days', JSON.stringify(collapsedDays));
    renderSpreadsheet();
}

// ==========================================================================
// EDITAR / EXCLUIR ALUNO (mesma lógica da aba "Alunos", adaptada para a
// planilha desta turma)
// ==========================================================================
let pendingDeleteStudant = null;

function openDeleteStudantModal(aluno) {
    pendingDeleteStudant = aluno;
    const modal = document.getElementById('delete-studant-modal');
    const description = document.getElementById('delete-studant-modal-description');
    if (description) {
        description.textContent = aluno && aluno.nome
            ? `Tem certeza que quer excluir o aluno ${aluno.nome}? Essa ação não pode ser desfeita!`
            : 'Tem certeza que deseja deletar este aluno? Essa ação não pode ser desfeita!';
    }
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

function closeDeleteStudantModal() {
    pendingDeleteStudant = null;
    const modal = document.getElementById('delete-studant-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

function deleteStudant() {
    const aluno = pendingDeleteStudant;
    if (!aluno || aluno.id == null) return;

    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/delete_studant/' + encodeURIComponent(aluno.id);

    const returnToInput = document.createElement('input');
    returnToInput.type = 'hidden';
    returnToInput.name = 'return_to_turma_id';
    returnToInput.value = window.flaskData.turmaId;
    form.appendChild(returnToInput);

    document.body.appendChild(form);
    form.submit();
    closeDeleteStudantModal();
}

let pendingEditStudant = null;

function openEditStudantModal(aluno) {
    if (!aluno || aluno.id == null) return;
    pendingEditStudant = aluno;

    const form = document.getElementById('edit-studant-form');
    form.action = '/edit_studant/' + encodeURIComponent(aluno.id);

    document.getElementById('edit_studant_name').value = aluno.nome || '';

    const turmaOriginalId = aluno.turmaId != null ? String(aluno.turmaId) : '';
    document.getElementById('edit-studant-turma-original').value = turmaOriginalId;

    const select = document.getElementById('edit_studant_turma');
    select.innerHTML = '';
    (window.flaskData.todasTurmas || []).forEach(t => {
        const opt = document.createElement('option');
        opt.value = String(t.id);
        opt.textContent = t.nome;
        if (turmaOriginalId && String(t.id) === turmaOriginalId) {
            opt.selected = true;
        }
        select.appendChild(opt);
    });

    const pdfInput = document.getElementById('edit_studant_pdf');
    if (pdfInput) pdfInput.value = '';
    const pdfLabel = document.getElementById('edit_studant_pdf_filename');
    if (pdfLabel) pdfLabel.textContent = '';

    const modal = document.getElementById('edit-studant-modal');
    modal.classList.add('active');
    modal.style.display = 'flex';
}

function closeEditStudantModal() {
    pendingEditStudant = null;
    const modal = document.getElementById('edit-studant-modal');
    modal.classList.remove('active');
    modal.style.display = 'none';
}

function handleEditStudantPdfSelect() {
    const input = document.getElementById('edit_studant_pdf');
    const label = document.getElementById('edit_studant_pdf_filename');
    if (!input || !label) return;
    label.textContent = (input.files && input.files.length) ? input.files[0].name : '';
}

function submitEditStudantForm(event) {
    const select = document.getElementById('edit_studant_turma');
    const originalId = document.getElementById('edit-studant-turma-original').value;

    if (select && originalId && select.value !== originalId) {
        const novoNome = select.options[select.selectedIndex] ? select.options[select.selectedIndex].text : 'a turma selecionada';
        const nomeAluno = (pendingEditStudant && pendingEditStudant.nome) ? pendingEditStudant.nome : 'este aluno';
        const ok = confirm(`Tem certeza que deseja mover ${nomeAluno} para a turma "${novoNome}"? Os horários do aluno serão transferidos e ele sairá dos grupos formados na turma atual.`);
        if (!ok) {
            event.preventDefault();
            return false;
        }
    }
    return true;
}
