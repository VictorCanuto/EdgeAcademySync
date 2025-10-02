# services/pdf_parser.py
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
    Nova versão que tenta primeiro usar os módulos reorganizados (pdf_reader + pdf_processor)
    e fallback para o método original se necessário
    """
    if not pdf_paths:
        return None
    
    # Verifica se temos os módulos necessários para o novo método
    try:
        from .pdf_reader import ler_pdfs_para_excel
        from .pdf_processor import processar_excel
        TEM_MODULOS = True
    except ImportError:
        TEM_MODULOS = False
        print("Módulos pdf_reader/pdf_processor não disponíveis, usando fallback")
    
    if not TEM_MODULOS:
        return _processar_pdfs_fallback(pdf_paths)
    
    # Cria pasta temporária se necessário
    temp_dir = "temp_processing"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Passo 1: Processar PDFs para Excel usando pdf_reader
        # Precisamos criar uma pasta temporária com os PDFs para o ler_pdfs_para_excel
        pdf_temp_dir = os.path.join(temp_dir, "pdfs")
        os.makedirs(pdf_temp_dir, exist_ok=True)
        
        # Copia os PDFs para a pasta temporária
        for pdf_path in pdf_paths:
            import shutil
            shutil.copy2(pdf_path, pdf_temp_dir)
        
        excel_temp = os.path.join(temp_dir, "temp_consolidado.xlsx")
        ler_pdfs_para_excel(pdf_temp_dir, excel_temp)
        
        # Verifica se o Excel foi criado
        if not os.path.exists(excel_temp):
            print("PDF Reader não conseguiu gerar o arquivo Excel, usando fallback")
            return _processar_pdfs_fallback(pdf_paths)
        
        # Passo 2: Processar Excel para CSV usando pdf_processor
        csv_temp = os.path.join(temp_dir, "temp_base.csv")
        processar_excel(excel_temp, csv_temp)
        
        # Carregar resultado final
        if os.path.exists(csv_temp):
            df = pd.read_csv(csv_temp)
            print(f"Processamento integrado bem-sucedido: {len(df)} registros")
            return df
        else:
            print("PDF Processor não conseguiu gerar o CSV, usando fallback")
            return _processar_pdfs_fallback(pdf_paths)
            
    except Exception as e:
        print(f"Erro no processamento integrado: {e}")
        # Fallback para o método original
        return _processar_pdfs_fallback(pdf_paths)
    
    finally:
        # Limpeza opcional dos arquivos temporários
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass  # Ignora erros na limpeza

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