import os
import pandas as pd
import tabula

# Tenta achar a pasta de PDFs: ./ALL_PDFS, ./all_pdfs ou caminho antigo
CANDIDATAS = [
    os.path.abspath("./ALL_PDFS"),
    os.path.abspath("./all_pdfs"),
    os.path.abspath("C:/edgesync/ALL_PDFS"),
]
pasta_dos_pdfs = next((p for p in CANDIDATAS if os.path.isdir(p)), None)
if pasta_dos_pdfs is None:
    raise SystemExit("Pasta de PDFs não encontrada. Crie ./ALL_PDFS (ou ./all_pdfs) e coloque os comprovantes lá.")

arquivo_excel_saida = 'consolidado_horarios.xlsx'

def _maior_tabela(dfs):
    melhor, score = None, -1
    for df in dfs or []:
        if isinstance(df, pd.DataFrame):
            s = df.shape[0] * df.shape[1]
            if s > score:
                melhor, score = df, s
    return melhor

print("Iniciando...")
print(f"Lendo PDFs de: {pasta_dos_pdfs}")
ok, vazios = 0, []

with pd.ExcelWriter(arquivo_excel_saida, engine='openpyxl') as writer:
    for nome_arquivo in sorted(os.listdir(pasta_dos_pdfs)):
        if not nome_arquivo.lower().endswith('.pdf'):
            continue

        caminho_pdf = os.path.join(pasta_dos_pdfs, nome_arquivo)
        print(f"→ {nome_arquivo}")

        try:
            # Tenta pelos dois modos do tabula
            t_lattice = tabula.read_pdf(caminho_pdf, pages='all', lattice=True, multiple_tables=True, encoding='latin-1')
            t_stream  = tabula.read_pdf(caminho_pdf, pages='all', stream=True,  multiple_tables=True, encoding='latin-1')
            cand = (t_lattice or []) + (t_stream or [])
            tabela = _maior_tabela(cand)

            if tabela is None or tabela.empty:
                vazios.append(nome_arquivo)
                print("   AVISO: Nenhuma tabela útil encontrada.")
                continue

            nome_aba = os.path.splitext(nome_arquivo)[0][:30]
            tabela.to_excel(writer, sheet_name=nome_aba, index=False)
            ok += 1

        except Exception as e:
            print(f"   ERRO: {e}")

print(f"\nFinalizado. Abas criadas: {ok}  |  Sem tabela: {len(vazios)}")
if vazios:
    print("Arquivos sem tabela detectável:")
    for v in vazios:
        print(" -", v)
print(f"Gerado: {arquivo_excel_saida}")
