import streamlit as st
import pandas as pd

# --- Configuração da Página ---
# Define o título da aba do navegador e o layout da página como 'wide' (largo).
st.set_page_config(page_title="Cruzador de Horários", layout="wide")


# --- Carregamento e Cache dos Dados ---
# Otimização do Streamlit: esta função só roda uma vez. Nas interações seguintes,
# o resultado fica em cache (memória), tornando a aplicação muito mais rápida.
@st.cache_data
def carregar_dados():
    """Carrega a base de dados limpa a partir do arquivo CSV."""
    try:
        df = pd.read_csv('base_consolidada.csv')
        df.dropna(subset=['horario'], inplace=True)
        return df
    except FileNotFoundError:
        return None


# --- FUNÇÃO DE VISUALIZAÇÃO ---
def criar_grid_visual(grid_booleana_ocupado, titulo):
    """Recebe uma grade de True (ocupado) / False (disponível) e a transforma em uma tabela colorida."""
    
    # Define o texto a ser exibido com base no valor booleano.
    def formatar_texto(ocupado):
        return "INDISPONÍVEL" if ocupado else "DISPONÍVEL"

    # Define a cor de fundo (vermelho/verde) com base no valor booleano.
    def colorir_celula(ocupado):
        estilo = 'text-align: center; border: 1px solid #D3D3D3;'
        if ocupado:
            cor = 'background-color: #FFC7CE; color: #9C0006;' # Vermelho
        else:
            cor = 'background-color: #C6EFCE; color: #006100;' # Verde
        return estilo + cor
        
    # Aplica as funções de cor e texto à tabela usando o Styler do pandas.
    styler = grid_booleana_ocupado.style.map(colorir_celula).format(formatar_texto)
    styler.index.name = None
    styler.columns.name = None
    
    # Exibe o título e a tabela final na tela.
    st.header(titulo)
    st.table(styler)


# --- Carregamento Inicial dos Dados ---
base_de_dados = carregar_dados()


# --- Interface do Usuário (UI) ---
st.title("Sistema de Cruzamento de Horários 🗓️")

# Checagem de segurança: verifica se o arquivo 'base_consolidada.csv' existe.
if base_de_dados is None:
    st.error("Arquivo 'base_consolidada.csv' não encontrado. Por favor, execute o script 'processador.py' primeiro.")
else:
    # Prepara as listas de dados que serão usadas nos filtros e na grade.
    lista_de_alunos = sorted(base_de_dados['aluno'].unique())
    todos_os_horarios = sorted(base_de_dados['horario'].unique())
    dias_da_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
    
    # Cria o componente principal da UI: o menu de seleção múltipla.
    alunos_selecionados = st.multiselect(
        label="Selecione um ou mais alunos para ver a disponibilidade:",
        options=lista_de_alunos
    )

    # --- Lógica de Exibição ---
    # Se nenhum aluno for selecionado, mostra uma mensagem inicial.
    if not alunos_selecionados:
        st.info("Por favor, selecione pelo menos um aluno para começar.")
    
    # Caso apenas UM aluno seja selecionado, exibe sua grade individual.
    elif len(alunos_selecionados) == 1:
        aluno = alunos_selecionados[0]
        horarios_aluno = base_de_dados[base_de_dados['aluno'] == aluno]
        
        # Transforma a lista de horários do aluno em uma grade (formato pivot).
        pivot_aluno = horarios_aluno.pivot_table(
            index='horario', columns='dia', values='materia', aggfunc='first'
        )
        
        # Converte a grade em True (ocupado) / False (disponível) para a visualização.
        grid_ocupado_aluno = (pivot_aluno.notna() & (pivot_aluno != '---')).reindex(
            index=todos_os_horarios, columns=dias_da_semana, fill_value=False
        )
        
        # Chama a função de visualização para desenhar a grade na tela.
        criar_grid_visual(grid_ocupado_aluno, f"Grade de Horários de {aluno}")

    # Caso VÁRIOS alunos sejam selecionados, entra no modo de cruzamento.
    else:
        # Inicia uma grade "vazia" (tudo False) que será preenchida.
        grid_combinada_ocupado = pd.DataFrame(False, index=todos_os_horarios, columns=dias_da_semana)

        # Loop para processar cada aluno do grupo selecionado.
        for aluno in alunos_selecionados:
            horarios_aluno = base_de_dados[base_de_dados['aluno'] == aluno]
            
            if horarios_aluno.empty:
                continue

            pivot_aluno = horarios_aluno.pivot_table(
                index='horario', columns='dia', values='materia', aggfunc='first'
            )
            
            # Gera a grade de ocupação (True/False) para o aluno atual.
            grid_ocupado_aluno = (pivot_aluno.notna() & (pivot_aluno != '---')).reindex(
                index=todos_os_horarios, columns=dias_da_semana, fill_value=False
            )
            
            # Lógica principal: atualiza a grade combinada. O resultado é a SOMA (OU lógico) das ocupações.
            # Um horário fica ocupado se QUALQUER aluno estiver ocupado.
            grid_combinada_ocupado |= grid_ocupado_aluno
            
        # Define o título e chama a função de visualização para a grade combinada.
        titulo = f"Disponibilidade Combinada do Grupo ({len(alunos_selecionados)} pessoas)"
        criar_grid_visual(grid_combinada_ocupado, titulo)