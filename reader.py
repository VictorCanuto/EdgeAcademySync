import pandas as pd
import tabula
import os

pasta_dos_pdfs = 'C:/Users/JoséQuintela/Desktop/edge/ALL_PDFS' 

arquivo_excel_saida = 'consolidado_horarios.xlsx'

with pd.ExcelWriter(arquivo_excel_saida, engine='openpyxl') as writer:
    
    print(f"Iniciando processo...")
    print(f"Os PDFs da pasta '{pasta_dos_pdfs}' serão salvos em '{arquivo_excel_saida}'")

    for nome_arquivo in os.listdir(pasta_dos_pdfs):
        
        if nome_arquivo.lower().endswith('.pdf'):
            
            caminho_completo_pdf = os.path.join(pasta_dos_pdfs, nome_arquivo)
            print(f"\n--- Processando arquivo: {nome_arquivo} ---")

            try:
                lista_de_tabelas = tabula.read_pdf(caminho_completo_pdf, pages='all', encoding='latin-1')
                
                if len(lista_de_tabelas) >= 2:
                    tabela_horarios = lista_de_tabelas[1]
                    
                    nome_da_planilha = os.path.splitext(nome_arquivo)[0][:30]

                    tabela_horarios.to_excel(writer, sheet_name=nome_da_planilha, index=False)
                    
                    print(f"Sucesso! Tabela extraída e adicionada na aba '{nome_da_planilha}'.")
                else:
                    print(f"AVISO: O arquivo '{nome_arquivo}' não possui duas tabelas e foi ignorado.")

            except Exception as e:
                print(f"ERRO ao processar o arquivo {nome_arquivo}: {e}")

print(f"\nProcesso concluído! O arquivo '{arquivo_excel_saida}' foi criado com sucesso.")