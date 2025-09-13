import pandas as pd
import tabula
import os

# --- 1. Configurações ---
# Define a pasta de onde o script vai ler os arquivos PDF.
pasta_dos_pdfs = 'C:/edgesync/ALL_PDFS' 
# Define o nome do arquivo Excel que será criado com os resultados.
arquivo_excel_saida = 'consolidado_horarios.xlsx'


# Abre o arquivo Excel de saída, que ficará pronto para receber múltiplas abas (uma por aluno).
with pd.ExcelWriter(arquivo_excel_saida, engine='openpyxl') as writer:
    
    print(f"Iniciando processo...")
    print(f"Os PDFs da pasta '{pasta_dos_pdfs}' serão salvos em '{arquivo_excel_saida}'")

    # Loop principal: passa por cada arquivo encontrado na pasta de PDFs.
    for nome_arquivo in os.listdir(pasta_dos_pdfs):
        
        # Filtro para processar apenas arquivos que terminam com '.pdf'.
        if nome_arquivo.lower().endswith('.pdf'):
            
            caminho_completo_pdf = os.path.join(pasta_dos_pdfs, nome_arquivo)
            print(f"\n--- Processando arquivo: {nome_arquivo} ---")

            # Bloco de segurança: se a leitura de um PDF falhar, o script anota o erro e continua para o próximo.
            try:
                # A função principal do 'tabula' que lê o PDF e extrai as tabelas.
                lista_de_tabelas = tabula.read_pdf(caminho_completo_pdf, pages='all', encoding='latin-1')
                
                # Lógica principal: verifica se o PDF tem a estrutura esperada (pelo menos 2 tabelas).
                if len(lista_de_tabelas) >= 2:
                    # Assume que a grade de horários é sempre a segunda tabela encontrada (índice 1).
                    tabela_horarios = lista_de_tabelas[1]
                    
                    # Usa o nome do arquivo (sem a extensão .pdf) como nome da aba na planilha.
                    nome_da_planilha = os.path.splitext(nome_arquivo)[0][:30]

                    # Escreve a tabela extraída na sua respectiva aba dentro do arquivo Excel.
                    tabela_horarios.to_excel(writer, sheet_name=nome_da_planilha, index=False)
                    
                    print(f"Sucesso! Tabela extraída e adicionada na aba '{nome_da_planilha}'.")
                else:
                    # Se não encontrar 2 tabelas, avisa e ignora o arquivo.
                    print(f"AVISO: O arquivo '{nome_arquivo}' não possui duas tabelas e foi ignorado.")

            except Exception as e:
                # Captura e exibe qualquer outro erro que possa ocorrer durante o processamento do PDF.
                print(f"ERRO ao processar o arquivo {nome_arquivo}: {e}")

print(f"\nProcesso concluído! O arquivo '{arquivo_excel_saida}' foi criado com sucesso.")