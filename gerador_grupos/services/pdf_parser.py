import os
import pandas as pd
import tabula
import unicodedata
import re
from typing import List, Optional

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab"]
PAT_HORARIO = re.compile(r"^\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*$")
LIXO = ["sigaa", "nti", "copyright", "srv1inst1"]

def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def _eh_grade(df: pd.DataFrame) -> bool:
    cols = [_normalizar(c) for c in df.columns]
    if any(any(d in c for d in DIAS_SEMANA) for c in cols):
        return True
    if not df.empty:
        primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
        if any(any(d in c for d in DIAS_SEMANA) for c in primeira):
            return True
    return False

def _ajustar_header(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
    if any(x.startswith("hora") for x in primeira) or any(any(d in c for d in DIAS_SEMANA) for c in primeira):
        df.columns = df.iloc[0]
        df = df.drop(df.index[0]).reset_index(drop=True)
    return df

def extrair_grade_de_df(df: pd.DataFrame, aluno: str) -> Optional[pd.DataFrame]:
    col_horario = None
    for c in df.columns:
        if any(PAT_HORARIO.match(str(x).strip()) for x in df[c].dropna().astype(str).head(10)):
            col_horario = c
            break
    if not col_horario:
        return None

    resultados = []
    for _, linha in df.iterrows():
        horario = str(linha[col_horario]).strip()
        if not PAT_HORARIO.match(horario):
            continue
        for c in df.columns:
            if c == col_horario: continue
            dia = str(c).strip().title()
            if not any(_normalizar(dia).startswith(d) for d in DIAS_SEMANA):
                continue
            materia = str(linha[c]).strip()
            if not materia or materia.lower() in ["nan", "none", "---"] or any(bad in materia.lower() for bad in LIXO):
                materia = "---"
            resultados.append({"aluno": aluno, "dia": dia, "horario": horario, "materia": materia})
    return pd.DataFrame(resultados) if resultados else None

def processar_pdfs_para_dataframe(pdf_paths: List[str]) -> Optional[pd.DataFrame]:
    finais = []
    for caminho_pdf in pdf_paths:
        aluno = re.sub(r'\.pdf$', '', caminho_pdf.split(os.path.sep)[-1], flags=re.IGNORECASE)
        try:
            tabelas_brutas = tabula.read_pdf(caminho_pdf, pages="all", multiple_tables=True, lattice=True)
            if not tabelas_brutas: continue
            
            tabelas_validas = []
            for t in tabelas_brutas:
                t_limpa = t.dropna(how="all").loc[:, ~t.columns.duplicated()]
                if not t_limpa.empty and _eh_grade(t_limpa):
                    tabelas_validas.append(_ajustar_header(t_limpa))
            
            if not tabelas_validas: continue
            df_aluno_completo = pd.concat(tabelas_validas, ignore_index=True)
            
            df_grade = extrair_grade_de_df(df_aluno_completo, aluno)
            if df_grade is not None and not df_grade.empty:
                finais.append(df_grade)
        except Exception as e:
            print(f"Erro ao processar {caminho_pdf}: {e}")
            continue

    if not finais:
        return None

    base = pd.concat(finais, ignore_index=True)
    base = base.drop_duplicates(subset=['aluno', 'dia', 'horario']).reset_index(drop=True)
    return base