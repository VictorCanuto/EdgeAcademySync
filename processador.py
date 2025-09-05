import pandas as pd
import os
import re

def limpar_horario(texto_horario):
    """
    Usa regex para encontrar e extrair o horário de início e fim de uma string,
    retornando em um formato padronizado 'HH:MM - HH:MM'.
    Se o padrão não for encontrado, retorna None.
    """
    if not isinstance(texto_horario, str):
        return texto_horario

    texto_limpo = texto_horario.strip()
    
    match = re.search(r'(\d{2}):?(\d{2}).*?(\d{2}):?(\d{2})', texto_limpo)
    
    if match:
        h1, m1, h2, m2 = match.groups()
        return f"{h1}:{m1} - {h2}:{m2}"
    
    return None

def criar_base_de_dados_consolidada(caminho_excel):
    """
    Lê um arquivo Excel com múltiplas abas, filtra apenas as linhas que
    representam horários válidos e transforma os dados em um DataFrame consolidado.
    """
    if not os.path.exists(caminho_excel):
        print(f"ERRO: O arquivo de entrada '{caminho_excel}' não foi encontrado.")
        return None

    xls = pd.ExcelFile(caminho_excel)
    nomes_dos_alunos = xls.sheet_names
    
    lista_de_dataframes_finais = []

    print(f"Processando {len(nomes_dos_alunos)} alunos do arquivo '{caminho_excel}'...")

    for aluno in nomes_dos_alunos:
        df_aluno = pd.read_excel(xls, sheet_name=aluno)
        df_aluno.rename(columns={df_aluno.columns[0]: 'horario'}, inplace=True)
        df_aluno['horario'] = df_aluno['horario'].astype(str)
        
        df_horarios_validos = df_aluno[df_aluno['horario'].str.contains(r'^\d')].copy()

        if df_horarios_validos.empty:
            continue
        
        df_melted = df_horarios_validos.melt(
            id_vars=['horario'], 
            var_name='dia', 
            value_name='materia'
        )
        
        # Mantemos apenas as linhas que têm algum conteúdo na coluna 'materia'
        df_ocupado = df_melted.dropna(subset=['materia']).copy()
        
        # O FILTRO '---' FOI REMOVIDO DAQUI PARA GARANTIR QUE NADA SEJA PERDIDO
        
        if df_ocupado.empty:
            continue
            
        df_ocupado['horario'] = df_ocupado['horario'].apply(limpar_horario)
        df_ocupado['aluno'] = aluno
        
        lista_de_dataframes_finais.append(df_ocupado)

    if lista_de_dataframes_finais:
        base_consolidada = pd.concat(lista_de_dataframes_finais, ignore_index=True)
        base_consolidada = base_consolidada[['aluno', 'dia', 'horario', 'materia']]
        base_consolidada.dropna(subset=['horario'], inplace=True)
        print("Base de dados consolidada criada com sucesso!")
        return base_consolidada
    else:
        print("Nenhum dado válido para consolidar foi encontrado após a filtragem.")
        return pd.DataFrame()

# --- Bloco de Execução Principal ---
if __name__ == "__main__":
    arquivo_consolidado = 'consolidado_horarios.xlsx'
    base_de_dados = criar_base_de_dados_consolidada(arquivo_consolidado)

    if not base_de_dados.empty:
        print("\n--- Amostra da Base de Dados Limpa ---")
        print(base_de_dados.head())
        print(f"\nTotal de {len(base_de_dados)} horários ocupados encontrados.")
        
        arquivo_saida_csv = 'base_consolidada.csv'
        base_de_dados.to_csv(arquivo_saida_csv, index=False)
        print(f"\nBase de dados limpa e salva em '{arquivo_saida_csv}'.")