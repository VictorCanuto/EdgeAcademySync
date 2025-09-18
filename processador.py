import os
import re
import pandas as pd

# Aceita: 8:00 - 10:00 | 08h às 10h | 9.20-10.10 | 9 20 10 10 etc.
REG = re.compile(
    r'(?P<h1>\d{1,2})\s*[:h\.]?\s*(?P<m1>\d{2})\s*(?:-|a|às|as|até|to)?\s*'
    r'(?P<h2>\d{1,2})\s*[:h\.]?\s*(?P<m2>\d{2})',
    flags=re.IGNORECASE
)

def limpar_horario(s: str):
    if not isinstance(s, str):
        return None
    s = s.strip()
    m = REG.search(s)
    if not m:
        return None
    h1, m1, h2, m2 = m.group('h1','m1','h2','m2')
    return f"{int(h1):02d}:{m1} - {int(h2):02d}:{m2}"

def criar_base_de_dados_consolidada(caminho_excel: str) -> pd.DataFrame:
    if not os.path.exists(caminho_excel):
        print(f"ERRO: '{caminho_excel}' não existe.")
        return pd.DataFrame()

    xls = pd.ExcelFile(caminho_excel)
    sheets = xls.sheet_names
    finais = []
    vazios = []

    print(f"Processando {len(sheets)} abas...")

    for aluno in sheets:
        df = pd.read_excel(xls, sheet_name=aluno)
        if df.empty:
            vazios.append(aluno); continue

        df.rename(columns={df.columns[0]: 'horario'}, inplace=True)
        df['horario'] = df['horario'].astype(str)

        df_valid = df[df['horario'].str.contains(r'^\s*\d', regex=True)].copy()
        if df_valid.empty:
            vazios.append(aluno); continue

        melt = df_valid.melt(id_vars=['horario'], var_name='dia', value_name='materia')
        melt = melt.dropna(subset=['materia']).copy()
        if melt.empty:
            vazios.append(aluno); continue

        melt['horario'] = melt['horario'].apply(limpar_horario)
        melt = melt.dropna(subset=['horario'])
        if melt.empty:
            vazios.append(aluno); continue

        # Normalizações leves
        melt['aluno'] = str(aluno).strip()
        melt['dia'] = melt['dia'].astype(str).str.strip().str.title()
        melt['materia'] = melt['materia'].astype(str).str.strip()
        finais.append(melt[['aluno','dia','horario','materia']])

    if not finais:
        print("Nada válido após a limpeza.")
        return pd.DataFrame()

    base = pd.concat(finais, ignore_index=True)
    base.dropna(subset=['horario'], inplace=True)
    print(f"OK! Registros: {len(base)}  |  Abas vazias/descartadas: {len(vazios)}")
    if vazios:
        print("Atenção: abas sem linhas válidas:")
        for a in vazios: print(" -", a)
    return base

if __name__ == "__main__":
    xlsx_in = 'consolidado_horarios.xlsx'
    base = criar_base_de_dados_consolidada(xlsx_in)
    if not base.empty:
        base.to_csv('base_consolidada.csv', index=False)
        print("Salvo em 'base_consolidada.csv'")
