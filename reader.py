import os
import tabula
import pandas as pd
import unicodedata

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
            except UnicodeDecodeError as e:
                print("   ERRO de encoding:", e)
                cand = tabula.read_pdf(caminho, pages="all", multiple_tables=True, lattice=True, encoding='iso-8859-1', silent=True)
            except Exception as e:
                print("   ERRO geral:", e)
                vazios.append(nome_arquivo)
                continue

            cand_limpos = [_limpar_tabela(t) for t in cand if t is not None]
            cand_ajustados = [_ajustar_header(t) for t in cand_limpos if t is not None]
            tabelas_validas = [t for t in cand_ajustados if t is not None and _eh_grade(t)]

            if not tabelas_validas:
                vazios.append(nome_arquivo)
                print("AVISO: Nenhuma grade de horários encontrada.")
                continue

            # Junta todas as tabelas de grade do PDF
            tabela_final = pd.concat(tabelas_validas, ignore_index=True)

            # Normaliza coluna de horários se existir
            if 'Horário' in tabela_final.columns:
                tabela_final['Horário'] = tabela_final['Horário'].apply(normalizar_horario)

            nome_aba = os.path.splitext(nome_arquivo)[0][:30]  # Excel limita 31 chars
            tabela_final.to_excel(writer, sheet_name=nome_aba, index=False)
            ok += 1
            print(f"   OK: {len(tabelas_validas)} grade(s) escritas na aba", nome_aba)

    print("\nFinalizado. Abas criadas:", ok, " |  Sem grade:", len(vazios))
    print("Gerado:", saida_excel)


if __name__ == "__main__":
    pasta = "ALL_PDFS"
    saida = "consolidado_horarios.xlsx"
    ler_pdfs_para_excel(pasta, saida)



