import os
import tabula
import pandas as pd
import unicodedata
import shutil

def normalizar_horario(h: str) -> str:
    h = str(h).strip()
    if "-" in h:
        ini, fim = [x.strip() for x in h.split("-")]
    else:
        ini, fim = h, h
    return f"{ini} - {fim}"
# Dias da semana que indicam uma grade de horários
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]

def _normalizar(texto: str) -> str:
    """Remove acentos, põe minúsculas e tira espaços extras."""
    if not isinstance(texto, str):
        texto = str(texto)
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def _limpar_tabela(df):
    if df is None or df.empty:
        return None
    df = df.dropna(how="all")  # remove linhas totalmente vazias
    df = df.loc[:, ~df.columns.duplicated()]  # remove colunas duplicadas
    return df if not df.empty else None

def _eh_grade(df: pd.DataFrame):
    """Verifica se a tabela parece ser uma grade de horários."""
    cols = [_normalizar(c) for c in df.columns]

    # procura dias no cabeçalho
    if any(any(d in c for d in DIAS_SEMANA) for c in cols):
        return True

    # procura dias na primeira linha também
    if not df.empty:
        primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
        if any(any(d in c for d in DIAS_SEMANA) for c in primeira):
            return True
    return False

def _ajustar_header(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
    if any(x.startswith("hora") for x in primeira) or \
       any(any(d in c for d in DIAS_SEMANA) for c in primeira):
        df.columns = df.iloc[0]
        df = df.drop(df.index[0]).reset_index(drop=True)
    return df

def ler_pdfs_para_excel(pasta_pdfs, saida_excel):
    print("Iniciando leitura de PDFs...")
    print("Lendo PDFs de:", pasta_pdfs)

    # Limpa a pasta ALL_PDFS antes de processar
    if os.path.exists(pasta_pdfs):
        shutil.rmtree(pasta_pdfs)  # Apaga a pasta inteira
    os.makedirs(pasta_pdfs, exist_ok=True)

    arquivos = [f for f in os.listdir(pasta_pdfs) if f.lower().endswith(".pdf")]
    if not arquivos:
        print("Nenhum PDF encontrado.")
        return

    ok, vazios = 0, []
    with pd.ExcelWriter(saida_excel, engine="openpyxl") as writer:
        for nome_arquivo in arquivos:
            caminho = os.path.join(pasta_pdfs, nome_arquivo)
            print("\n→", nome_arquivo)

            try:
                cand = tabula.read_pdf(caminho, pages="all", multiple_tables=True, lattice=True, encoding='latin-1', silent=True)
            except Exception as e:
                print("   ERRO geral:", e)
                vazios.append(nome_arquivo)
                continue

            cand_limpos = [_limpar_tabela(t) for t in cand if t is not None]
            cand_ajustados = [_ajustar_header(t) for t in cand_limpos if t is not None]
            tabelas_validas = [t for t in cand_ajustados if t is not None and _eh_grade(t)]

            if not tabelas_validas:
                vazios.append(nome_arquivo)
                print("   AVISO: Nenhuma grade de horários encontrada.")
                continue

            nome_aba = os.path.splitext(nome_arquivo)[0][:30]
            tabelas_validas[0].to_excel(writer, sheet_name=nome_aba, index=False)  # Salva a primeira tabela válida
            ok += 1
            print(f"   OK: {len(tabelas_validas)} grade(s) escritas na aba", nome_aba)

    if ok == 0:
        print("Nenhum PDF processado com sucesso. Arquivo Excel não será gerado.")
        return

    print("\nFinalizado. Abas criadas:", ok, " |  Sem grade:", len(vazios))
    print("Gerado:", saida_excel)


if __name__ == "__main__":
    pasta = "ALL_PDFS"
    saida = "consolidado_horarios.xlsx"
    ler_pdfs_para_excel(pasta, saida)



