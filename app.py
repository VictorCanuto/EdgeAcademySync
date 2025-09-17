import streamlit as st
import pandas as pd
from grupos import formar_grupos
from datetime import datetime
import re

# --- Configuração da Página ---
st.set_page_config(page_title="Edge", layout="wide")

# --- Carregamento e Cache dos Dados ---
@st.cache_data
def carregar_dados():
    """Carrega a base de dados limpa a partir do arquivo CSV."""
    try:
        df = pd.read_csv('base_consolidada_ok.csv')
        df.dropna(subset=['horario'], inplace=True)
        return df
    except FileNotFoundError:
        return None

# --- FUNÇÃO PARA VERIFICAR CONFLITO DE HORÁRIOS ---
def horarios_conflitam(horario_aluno, horario_bloco):
    """Verifica se dois horários conflitam."""
    try:
        # Converte horários para minutos para comparação
        def horario_para_minutos(horario_str):
            partes = horario_str.split(' - ')
            inicio = datetime.strptime(partes[0], '%H:%M')
            fim = datetime.strptime(partes[1], '%H:%M')
            return inicio.hour * 60 + inicio.minute, fim.hour * 60 + fim.minute
        
        inicio_aluno, fim_aluno = horario_para_minutos(horario_aluno)
        inicio_bloco, fim_bloco = horario_para_minutos(horario_bloco)
        
        # Verifica sobreposição
        return not (fim_aluno <= inicio_bloco or inicio_aluno >= fim_bloco)
    except:
        return False

# --- FUNÇÃO PARA CRIAR AGENDA GERAL COMPLETA ---
def criar_agenda_geral_completa(df):
    """Cria agenda geral mostrando quantos alunos estão DISPONÍVEIS em cada horário específico."""
    
    # Pega todos os horários únicos da base de dados
    todos_horarios = sorted(df['horario'].unique())
    dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
    todos_alunos = df['aluno'].unique()
    
    # Cria grade vazia para disponibilidade
    agenda_disponivel = pd.DataFrame(0, index=todos_horarios, columns=dias_semana)
    
    # Para cada horário e dia, conta alunos disponíveis
    for horario in todos_horarios:
        for dia in dias_semana:
            count_disponivel = 0
            
            for aluno in todos_alunos:
                # Verifica se o aluno está OCUPADO neste horário e dia específico
                ocupado = df[(df['aluno'] == aluno) & 
                           (df['dia'] == dia) & 
                           (df['horario'] == horario) &
                           (df['materia'] != '---')].any().any()
                
                # Se NÃO está ocupado, está disponível
                if not ocupado:
                    count_disponivel += 1
            
            agenda_disponivel.loc[horario, dia] = count_disponivel
    
    return agenda_disponivel

# --- FUNÇÃO PARA OBTER ALUNOS DISPONÍVEIS ESPECÍFICO ---
def obter_alunos_disponiveis_especifico(df, dia, horario):
    """Retorna lista de alunos disponíveis em um horário e dia específicos."""
    todos_alunos = df['aluno'].unique()
    alunos_disponiveis = []
    
    for aluno in todos_alunos:
        # Verifica se o aluno está OCUPADO neste horário específico
        ocupado = df[(df['aluno'] == aluno) & 
                   (df['dia'] == dia) & 
                   (df['horario'] == horario) &
                   (df['materia'] != '---')].any().any()
        
        # Se NÃO está ocupado, está disponível
        if not ocupado:
            alunos_disponiveis.append(aluno)
    
    return sorted(alunos_disponiveis)

# --- FUNÇÃO DE VISUALIZAÇÃO DA AGENDA GERAL COMPLETA ---
def visualizar_agenda_geral_completa(df):
    """Exibe a agenda geral completa com todos os horários."""
    st.header("📊 Agenda Geral Completa - Alunos Disponíveis por Horário")
    
    # Cria agenda de disponibilidade completa
    agenda_disponivel = criar_agenda_geral_completa(df)
    
    # Formata a visualização
    def formatar_celula(valor):
        return f"{int(valor)} DISPONÍVEIS" if valor > 0 else "Livre"
    
    def colorir_celula(valor):
        estilo = 'text-align: center; border: 1px solid #D3D3D3; cursor: pointer; padding: 8px;'
        if valor == 0:
            cor = 'background-color: #F8F9FA; color: #6C757D; font-weight: normal;' #cinza
        elif valor <= 15:
            cor = 'background-color: #F8D7DA; color: #721C24; font-weight: bold;' #vermelho claro
        elif valor <= 19:
            cor = 'background-color: #FFF3CD; color: #856404; font-weight: bold;'# amarelo
        elif valor <= 24:
            cor = 'background-color: #D4EDDA; color: #155724; font-weight: bold;'  # Verde claro - Bom
        else:
            cor = 'background-color: #28A745; color: white; font-weight: bold;' #verde escuro
        return estilo + cor
    
    # Exibe a tabela
    styler = agenda_disponivel.style.map(colorir_celula).format(formatar_celula)
    styler.index.name = "Horário"
    styler.columns.name = "Dia"
    
    st.table(styler)
    
    # --- SELEÇÃO PARA VER DETALHES ESPECÍFICOS ---
    st.subheader("🔍 Ver Alunos Disponíveis em Horário Específico")
    
    col1, col2 = st.columns(2)
    with col1:
        horario_selecionado = st.selectbox(
            "Selecione o horário:",
            options=agenda_disponivel.index.tolist(),
            key="horario_select"
        )
    with col2:
        dia_selecionado = st.selectbox(
            "Selecione o dia:",
            options=agenda_disponivel.columns.tolist(),
            key="dia_select"
        )
    
    # Mostra alunos disponíveis no horário específico
    disponivel_count = agenda_disponivel.loc[horario_selecionado, dia_selecionado]
    alunos_disponiveis = obter_alunos_disponiveis_especifico(df, dia_selecionado, horario_selecionado)
    
    st.write(f"**{disponivel_count} alunos disponíveis em {horario_selecionado} ({dia_selecionado})**")
    
    if disponivel_count > 0:
        # Mostra em duas colunas para muitos alunos
        col_count = 2 if len(alunos_disponiveis) > 10 else 1
        cols = st.columns(col_count)
        
        for i, aluno in enumerate(alunos_disponiveis):
            col_idx = i % col_count
            with cols[col_idx]:
                st.write(f"• {aluno}")
    else:
        st.info("Nenhum aluno disponível neste horário.")

# --- FUNÇÃO DE VISUALIZAÇÃO ORIGINAL ---
def criar_grid_visual(grid_booleana_ocupado, titulo):
    """Recebe uma grade de True (ocupado) / False (disponível) e a transforma em uma tabela colorida."""
    def formatar_texto(ocupado):
        return "INDISPONÍVEL" if ocupado else "DISPONÍVEL"

    def colorir_celula(ocupado):
        estilo = 'text-align: center; border: 1px solid #D3D3D3;'
        if ocupado:
            cor = 'background-color: #FFC7CE; color: #9C0006;'
        else:
            cor = 'background-color: #C6EFCE; color: #006100;'
        return estilo + cor
        
    styler = grid_booleana_ocupado.style.map(colorir_celula).format(formatar_texto)
    styler.index.name = None
    styler.columns.name = None
    
    st.header(titulo)
    st.table(styler)

# --- Carregamento Inicial dos Dados ---
base_de_dados = carregar_dados()

# --- Interface do Usuário (UI) ---
st.title("Sistema de Cruzamento de Horários 🗓️")

# --- Sistema de Abas ---
tab1, tab2, tab3 = st.tabs(["Visualização Individual", "Cruzamento de Grupo", "Agenda Geral"])

with tab1:
    # Código original da visualização individual
    if base_de_dados is None:
        st.error("Arquivo 'base_consolidada_ok.csv' não encontrado. Por favor, execute o script 'processador.py' primeiro.")
    else:
        lista_de_alunos = sorted(base_de_dados['aluno'].unique())
        todos_os_horarios = sorted(base_de_dados['horario'].unique())
        dias_da_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
        
        alunos_selecionados = st.multiselect(
            label="Selecione um ou mais alunos para ver a disponibilidade:",
            options=lista_de_alunos,
            key="tab1_select"
        )

        if not alunos_selecionados:
            st.info("Por favor, selecione pelo menos um aluno para começar.")
        
        elif len(alunos_selecionados) == 1:
            aluno = alunos_selecionados[0]
            horarios_aluno = base_de_dados[base_de_dados['aluno'] == aluno]
            
            pivot_aluno = horarios_aluno.pivot_table(
                index='horario', columns='dia', values='materia', aggfunc='first'
            )
            
            grid_ocupado_aluno = (pivot_aluno.notna() & (pivot_aluno != '---')).reindex(
                index=todos_os_horarios, columns=dias_da_semana, fill_value=False
            )
            
            criar_grid_visual(grid_ocupado_aluno, f"Grade de Horários de {aluno}")

        else:
            grid_combinada_ocupado = pd.DataFrame(False, index=todos_os_horarios, columns=dias_da_semana)

            for aluno in alunos_selecionados:
                horarios_aluno = base_de_dados[base_de_dados['aluno'] == aluno]
                
                if horarios_aluno.empty:
                    continue

                pivot_aluno = horarios_aluno.pivot_table(
                    index='horario', columns='dia', values='materia', aggfunc='first'
                )
                
                grid_ocupado_aluno = (pivot_aluno.notna() & (pivot_aluno != '---')).reindex(
                    index=todos_os_horarios, columns=dias_da_semana, fill_value=False
                )
                
                grid_combinada_ocupado |= grid_ocupado_aluno
                
            titulo = f"Disponibilidade Combinada do Grupo ({len(alunos_selecionados)} pessoas)"
            criar_grid_visual(grid_combinada_ocupado, titulo)

with tab2:
    # Aba para gerar grupos
    st.header("Formação de Grupos")
    if st.button("Gerar Grupos de Acompanhamento"):
        grupos = formar_grupos('base_consolidada_ok.csv', 3)
        for g in grupos:
            grupo_id = g.get('Grupo', '?')
            dia = g.get('Dia', '')
            horario = g.get('Horário', '')
            membros = g.get('Membros', [])

            st.subheader(f"Grupo {grupo_id} — {dia} ({horario}) — {len(membros)} alunos")
            for i, membro in enumerate(membros, 1):
                st.write(f"{i}. {membro}")

            st.markdown("---")

with tab3:
    # NOVA ABA: AGENDA GERAL COMPLETA
    if base_de_dados is None:
        st.error("Arquivo 'base_consolidada_ok.csv' não encontrado.")
    else:
        visualizar_agenda_geral_completa(base_de_dados)

# --- Rodapé ---
st.markdown("---")
st.caption("Sistema de Cruzamento de Horários - Desenvolvido para gestão de grupos de acompanhamento")