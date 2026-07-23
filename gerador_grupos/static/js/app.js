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
        
        tdName.innerHTML = `
            <div style="display:flex; align-items:center; gap:8px;">
                <div class="user-avatar" style="width:24px; height:24px; font-size:0.75rem; background: var(--color-primary); color:white;">
                    ${alunoNome[0].toUpperCase()}
                </div>
                <div>
                    <div>${alunoNome}</div>
                    <span style="font-size: 0.7rem; color: var(--text-muted); font-weight:500;">
                        ${grupoInfo ? `Grupo ${grupoInfo.Grupo}` : 'Sem Grupo'}
                    </span>
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

    if (leftPos < 10) leftPos = 10;
    if (topPos < 10) topPos = rect.bottom + scrollTop + 8;

    popover.style.left = `${leftPos}px`;
    popover.style.top = `${topPos}px`;
}

function closePopover() {
    const popover = document.getElementById('popover-schedule-menu');
    if (popover) popover.style.display = 'none';
    activePopover = { alunoNome: null, dia: null, horario: null, targetCell: null };
}

async function updateCellStatus(newStatus) {
    const { alunoNome, dia, horario } = activePopover;
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

    closePopover();

    // Enviar alteração via POST para o Flask
    try {
        const response = await fetch('/aluno/update_schedule/' + window.flaskData.turmaId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                aluno: alunoNome,
                dia: dia,
                horario: horario,
                status: statusValue
            })
        });

        if (response.ok) {
            const data = await response.json();
            
            // Atualizar cache local
            if (!studentSchedules[alunoNome]) studentSchedules[alunoNome] = {};
            studentSchedules[alunoNome][`${dia}_${horario}`] = statusValue;
            
            renderSpreadsheet();
            recalculateConflicts();

            if (data.conflito) {
                showToast('Novo Conflito Gerado', `A agenda de ${alunoNome} agora conflita com a imersão do Grupo ${data.grupo}!`, 'danger');
            } else {
                showToast('Horário Atualizado', 'Alteração salva no banco de dados.', 'success');
            }
        } else {
            showToast('Erro ao Salvar', 'Não foi possível atualizar o horário no servidor.', 'danger');
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
                <div class="grp-badge">${g.Membros.length} alunos</div>
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
    const diaAbrevMap = {'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta', 'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado'};
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
            const diaAbrevMap = {'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta', 'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado'};
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

function toggleExportMenu() {
    const wrapper = document.getElementById('export-dropdown-wrapper');
    if (wrapper) wrapper.classList.toggle('active');
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

function displayFlaskFlashMessages() {
    // Executa no carregamento da página para mostrar mensagens flash injetadas pelo Flask como Toasts
    if (window.flaskData.flashMessages) {
        window.flaskData.flashMessages.forEach(msg => {
            let cat = msg.category;
            let type = cat === 'error' || cat === 'danger' ? 'danger' : (cat === 'success' ? 'success' : (cat === 'warning' ? 'warning' : 'info'));
            showToast(type === 'danger' ? 'Erro' : (type === 'success' ? 'Sucesso' : 'Notificação'), msg.message, type);
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

        const exp = document.getElementById('export-dropdown-wrapper');
        if (exp && exp.classList.contains('active')) {
            if (!exp.contains(e.target)) {
                exp.classList.remove('active');
            }
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
