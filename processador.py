import pandas as pd
import os
import re

# Helper para limpar e padronizar as strings de horário.
def limpar_horario(texto_horario):
    """
    Usa regex para encontrar e extrair um horário no formato HH:MM - HH:MM.
    Se não encontrar, retorna None para que a linha seja descartada.
    """
    if not isinstance(texto_horario, str):
        return texto_horario

    # Remove espaços em branco no início e no fim da string.
    texto_limpo = texto_horario.strip()
    
    # Procura pelo padrão de horário completo (ex: 15:20 - 16:10).
    match = re.search(r'(\d{2}):?(\d{2}).*?(\d{2}):?(\d{2})', texto_limpo)
    
    if match:
        h1, m1, h2, m2 = match.groups()
        return f"{h1}:{m1} - {h2}:{m2}"
    
    # Se não encontrar um horário válido, marca para remoção.
    return None

# Função principal que lê o Excel, limpa os dados e os transforma.
def criar_base_de_dados_consolidada(caminho_excel):
    """
    Lê um arquivo Excel com múltiplas abas, filtra apenas as linhas que
    representam horários válidos e transforma os dados em um DataFrame consolidado.
    """
    # Verifica se o arquivo de entrada existe antes de começar.
    if not os.path.exists(caminho_excel):
        print(f"ERRO: O arquivo de entrada '{caminho_excel}' não foi encontrado.")
        return None

    # Carrega o arquivo Excel e pega o nome de todas as abas (alunos).
    xls = pd.ExcelFile(caminho_excel)
    nomes_dos_alunos = xls.sheet_names
    
    lista_de_dataframes_finais = []

    print(f"Processando {len(nomes_dos_alunos)} alunos do arquivo '{caminho_excel}'...")

    # Itera sobre cada aluno (cada aba da planilha).
    for aluno in nomes_dos_alunos:
        df_aluno = pd.read_excel(xls, sheet_name=aluno)
        # Padroniza o nome da primeira coluna para 'horario'.
        df_aluno.rename(columns={df_aluno.columns[0]: 'horario'}, inplace=True)
        df_aluno['horario'] = df_aluno['horario'].astype(str)
        
        # Filtro principal: mantém apenas as linhas que começam com um número na coluna 'horario'.
        df_horarios_validos = df_aluno[df_aluno['horario'].str.contains(r'^\d')].copy()

        # Pula o aluno se ele não tiver nenhuma linha de horário válida.
        if df_horarios_validos.empty:
            continue
        
        # Transforma a tabela do formato 'largo' (colunas de dias) para o 'longo' (linhas de eventos).
        df_melted = df_horarios_validos.melt(
            id_vars=['horario'], 
            var_name='dia', 
            value_name='materia'
        )
        
        # Remove as linhas que representam horários genuinamente vazios.
        df_ocupado = df_melted.dropna(subset=['materia']).copy()
        
        # Pula se não houverem horários ocupados para este aluno.
        if df_ocupado.empty:
            continue
            
        # Aplica a função de limpeza para padronizar e validar a coluna de horários.
        df_ocupado['horario'] = df_ocupado['horario'].apply(limpar_horario)
        # Adiciona a coluna com o nome do aluno para identificar os registros.
        df_ocupado['aluno'] = aluno
        
        lista_de_dataframes_finais.append(df_ocupado)

    # Se a lista de dataframes não estiver vazia, junta tudo em uma tabela mestra.
    if lista_de_dataframes_finais:
        base_consolidada = pd.concat(lista_de_dataframes_finais, ignore_index=True)
        # Reorganiza as colunas para o formato final.
        base_consolidada = base_consolidada[['aluno', 'dia', 'horario', 'materia']]
        # Limpeza final: remove quaisquer linhas com horários nulos após a limpeza.
        base_consolidada.dropna(subset=['horario'], inplace=True)
        print("Base de dados consolidada criada com sucesso!")
        return base_consolidada
    else:
        print("Nenhum dado válido para consolidar foi encontrado após a filtragem.")
        return pd.DataFrame()

# Este bloco só executa quando o script é chamado diretamente pelo terminal (python processador.py).
if __name__ == "__main__":
    arquivo_consolidado = 'consolidado_horarios.xlsx'
    base_de_dados = criar_base_de_dados_consolidada(arquivo_consolidado)

    # Se a criação da base de dados foi bem-sucedida, mostra uma amostra e salva o resultado.
    if not base_de_dados.empty:
        print("\n--- Amostra da Base de Dados Limpa ---")
        print(base_de_dados.head())
        print(f"\nTotal de {len(base_de_dados)} horários ocupados encontrados.")
        
        arquivo_saida_csv = 'base_consolidada.csv'
        base_de_dados.to_csv(arquivo_saida_csv, index=False)
        print(f"\nBase de dados limpa e salva em '{arquivo_saida_csv}'.")