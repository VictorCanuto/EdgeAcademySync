import streamlit as st
import pandas as pd

# --- Configuração da Página ---
st.set_page_config(page_title="Cruzador de Horários", layout="wide")

# --- Carregamento e Cache dos Dados ---
@st.cache_data
def carregar_dados():
    try:
        df = pd.read_csv('base_consolidada.csv')
        df.dropna(subset=['horario'], inplace=True)
        return df
    except FileNotFoundError:
        return None

# --- FUNÇÃO DE VISUALIZAÇÃO ÚNICA E INTELIGENTE ---
def criar_grid_visual(grid_booleana_ocupado, titulo):
    """
    Recebe uma grade de True (ocupado) / False (disponível) e a transforma
    em uma tabela colorida e formatada.
    """
    def formatar_texto(ocupado):
        return "INDISPONÍVEL" if ocupado else "DISPONÍVEL"

    def colorir_celula(ocupado):
        estilo = 'text-align: center; border: 1px solid #D3D3D3;'
        if ocupado:
            cor = 'background-color: #FFC7CE; color: #9C0006;' # Vermelho
        else:
            cor = 'background-color: #C6EFCE; color: #006100;' # Verde
        return estilo + cor
        
    styler = grid_booleana_ocupado.style.map(colorir_celula).format(formatar_texto)
    styler.index.name = None
    styler.columns.name = None
    
    st.header(titulo)
    st.table(styler)

# --- Carregamento dos Dados ---
base_de_dados = carregar_dados()

# --- Interface do Usuário (UI) ---
st.title("Sistema de Cruzamento de Horários 🗓️")

if base_de_dados is None:
    st.error("Arquivo 'base_consolidada.csv' não encontrado. Por favor, execute o script 'processador.py' primeiro.")
else:
    lista_de_alunos = sorted(base_de_dados['aluno'].unique())
    todos_os_horarios = sorted(base_de_dados['horario'].unique())
    dias_da_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
    
    alunos_selecionados = st.multiselect(
        label="Selecione um ou mais alunos para ver a disponibilidade:",
        options=lista_de_alunos
    )

    # --- LÓGICA DE EXIBIÇÃO ---
    if not alunos_selecionados:
        st.info("Por favor, selecione pelo menos um aluno para começar.")
    
    elif len(alunos_selecionados) == 1:
        # MODO INDIVIDUAL
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
        # MODO DE GRUPO
        grid_combinada_ocupado = pd.DataFrame(False, index=todos_os_horarios, columns=dias_da_semana)

        for aluno in alunos_selecionados:
            horarios_aluno = base_de_dados[base_de_dados['aluno'] == aluno]
            
            if horarios_aluno.empty:
                continue

            pivot_aluno = horarios_aluno.pivot_table(
                index='horario', columns='dia', values='materia', aggfunc='first'
            )
            
            # A mesma lógica de ocupado é aplicada aqui para consistência
            grid_ocupado_aluno = (pivot_aluno.notna() & (pivot_aluno != '---')).reindex(
                index=todos_os_horarios, columns=dias_da_semana, fill_value=False
            )
            
            grid_combinada_ocupado |= grid_ocupado_aluno
            
        titulo = f"Disponibilidade Combinada do Grupo ({len(alunos_selecionados)} pessoas)"
        criar_grid_visual(grid_combinada_ocupado, titulo)