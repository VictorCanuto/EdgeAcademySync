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
            if c == col_horario: 
                continue
            dia = str(c).strip().title()
            if not any(_normalizar(dia).startswith(d) for d in DIAS_SEMANA):
                continue
            materia = str(linha[c]).strip()
            if not materia or materia.lower() in ["nan", "none", "---"] or any(bad in materia.lower() for bad in LIXO):
                materia = "---"
            resultados.append({"aluno": aluno, "dia": dia, "horario": horario, "materia": materia})
    return pd.DataFrame(resultados) if resultados else None

def _processar_pdfs_fallback(pdf_paths: List[str]) -> Optional[pd.DataFrame]:
    """
    Método fallback usando a lógica original do pdf_parser - processamento direto com tabula
    """
    finais = []
    for caminho_pdf in pdf_paths:
        aluno = re.sub(r'\.pdf$', '', caminho_pdf.split(os.path.sep)[-1], flags=re.IGNORECASE)
        try:
            tabelas_brutas = tabula.read_pdf(caminho_pdf, pages="all", multiple_tables=True, lattice=True)
            if not tabelas_brutas: 
                continue
            
            tabelas_validas = []
            for t in tabelas_brutas:
                t_limpa = t.dropna(how="all").loc[:, ~t.columns.duplicated()]
                if not t_limpa.empty and _eh_grade(t_limpa):
                    tabelas_validas.append(_ajustar_header(t_limpa))
            
            if not tabelas_validas: 
                continue
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

def processar_pdfs_para_dataframe(pdf_paths: List[str]) -> Optional[pd.DataFrame]:
    """
    Tenta primeiro usar processamento baseado em pypdf (puro Python, sem dependência de Java).
    Se falhar ou não encontrar registros, faz o fallback para o processamento via tabula.
    """
    if not pdf_paths:
        return None
        
    try:
        import pypdf
        
        finais = []
        for caminho_pdf in pdf_paths:
            reader = pypdf.PdfReader(caminho_pdf)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
                
            aluno_key = os.path.splitext(os.path.basename(caminho_pdf))[0]
            
            # Encontrar o início da tabela (cabeçalho de dias)
            header_pattern = re.compile(r"dom\s+seg\s+ter\s+qua\s+qui\s+sex\s+sab", re.IGNORECASE)
            match_header = header_pattern.search(text)
            if not match_header:
                continue
                
            table_start_idx = match_header.end()
            table_text = text[table_start_idx:]
            
            # Encontrar todos os padrões de horário (HH:MM - HH:MM)
            time_pattern = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
            time_matches = list(time_pattern.finditer(table_text))
            if not time_matches:
                continue
                
            dias_semana = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
            dias_semana_map = {"Seg": "Seg", "Ter": "Ter", "Qua": "Qua", "Qui": "Qui", "Sex": "Sex", "Sab": "Sab"}
            
            rows = []
            for idx, match in enumerate(time_matches):
                start_time = match.group(1)
                end_time = match.group(2)
                horario_str = f"{start_time} - {end_time}"
                
                start_pos = match.end()
                if idx + 1 < len(time_matches):
                    end_pos = time_matches[idx + 1].start()
                else:
                    end_pos = len(table_text)
                    
                dados_raw = table_text[start_pos:end_pos].strip()
                
                # Truncar antes de rodapés ou outras páginas
                for stop_word in ["ATENÇÃO", "sigaa", "NTI", "copyright", "srv", "sistema integrado", "portal do discente", "emitido em", "https://", "período letivo"]:
                    stop_idx = dados_raw.lower().find(stop_word.lower())
                    if stop_idx != -1:
                        dados_raw = dados_raw[:stop_idx].strip()
                        
                # Limpar espaços extras
                dados_raw = re.sub(r"\s+", " ", dados_raw)
                tokens = dados_raw.split()
                
                if len(tokens) >= 7:
                    tokens = tokens[:7]
                    for d_idx, token_dado in enumerate(tokens):
                        dia_nome = dias_semana[d_idx]
                        if dia_nome in dias_semana_map:
                            materia = token_dado
                            if materia == '---' or not materia:
                                materia = '---'
                            rows.append({
                                "aluno": aluno_key,
                                "dia": dias_semana_map[dia_nome],
                                "horario": horario_str,
                                "materia": materia
                            })
                            
            if rows:
                finais.append(pd.DataFrame(rows))
                
        if finais:
            base = pd.concat(finais, ignore_index=True)
            base = base.drop_duplicates(subset=['aluno', 'dia', 'horario']).reset_index(drop=True)
            print(f"Processamento via pypdf bem-sucedido: {len(base)} registros")
            return base
            
    except Exception as e:
        print(f"Erro no processamento pypdf: {e}. Usando fallback para tabula...")
        
    # Se pypdf falhar ou não achar registros, usa o fallback original
    return _processar_pdfs_fallback(pdf_paths)

# Para compatibilidade com o app.py existente
def processar_pdfs_para_dataframe_original(pdf_paths: List[str]) -> Optional[pd.DataFrame]:
    """
    Versão que mantém exatamente o comportamento original (só usa tabula)
    """
    return _processar_pdfs_fallback(pdf_paths)

if __name__ == "__main__":
    # Teste simples
    import sys
    if len(sys.argv) > 1:
        pdfs = sys.argv[1:]
        resultado = processar_pdfs_para_dataframe(pdfs)
        if resultado is not None:
            print(f"Processados {len(resultado)} registros de {len(resultado['aluno'].unique())} alunos")
            resultado.to_csv("teste_saida.csv", index=False)
        else:
            print("Nenhum dado processado")