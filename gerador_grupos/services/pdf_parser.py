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

def _limpar_nome_aluno(nome_bruto: str) -> str:
    if not nome_bruto:
        return ""
    
    texto = os.path.splitext(nome_bruto)[0].replace('_', ' ').strip()

    if " - " in texto or "-" in texto:
        partes = [p.strip() for p in re.split(r'\s*-\s*', texto) if p.strip()]
        partes_limpas = [
            p for p in partes 
            if not any(lixo in p.lower() for lixo in [
                "sistema", "gestao", "atividades", "academicas", "academica",
                "comprovante", "atestado", "matricula", "portal", "discente",
                "universidade", "instituto", "sigaa", "emitido", "relatorio"
            ])
        ]
        if partes_limpas:
            texto = partes_limpas[-1]

    texto = re.sub(r'^\d+\s*', '', texto).strip()
    texto = re.sub(r'^(comprovante|atestado|matricula|relatorio|sigaa)\s*(de\s*)?', '', texto, flags=re.IGNORECASE).strip()
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

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

def extrair_grade_de_df(df: pd.DataFrame, aluno: str, matricula: Optional[str] = None) -> Optional[pd.DataFrame]:
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
            resultados.append({"aluno": aluno, "matricula": matricula, "dia": dia, "horario": horario, "materia": materia})
    return pd.DataFrame(resultados) if resultados else None

def _processar_single_pdf(caminho_pdf: str):
    """
    Tenta processar um único PDF primeiro via pypdf e depois via tabula (fallback).
    Retorna (df_resultado, aluno_key) se obtiver dados, ou (None, aluno_key/filename).
    """
    filename = os.path.basename(caminho_pdf)
    clean_filename = re.sub(r'^\d+_', '', filename)
    aluno_key = _limpar_nome_aluno(clean_filename).replace(" ", "_")

    # 1. Tentar processar via pypdf (rápido e puro Python)
    try:
        import pypdf
        reader = pypdf.PdfReader(caminho_pdf)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        match = re.search(
            r"Nome\s*:\s*([^\r\n]+?)(?=\s*Curso\s*:|\s*Matr[ií]cula\s*:|\r|\n|$)",
            text,
            re.IGNORECASE,
        )
        if match:
            raw_name = match.group(1).strip()
            nome_extraido = _limpar_nome_aluno(raw_name)
            if nome_extraido:
                aluno_key = nome_extraido.replace(" ", "_")
                print(f"   👤 [PDF Text] Nome do Aluno extraído: {nome_extraido}")
        else:
            nome_extraido = _limpar_nome_aluno(clean_filename)
            aluno_key = nome_extraido.replace(" ", "_")
            print(f"   ⚠️ [PDF Text] Campo 'Nome:' não encontrado via regex. Usando nome do arquivo limpo: {nome_extraido}")

        match_matricula = re.search(r"Matr[ií]cula:\s*(\d+)", text, re.IGNORECASE)
        matricula_val = match_matricula.group(1) if match_matricula else None

        header_pattern = re.compile(r"dom\s+seg\s+ter\s+qua\s+qui\s+sex\s+sab", re.IGNORECASE)
        match_header = header_pattern.search(text)
        if match_header:
            table_start_idx = match_header.end()
            table_text = text[table_start_idx:]

            time_pattern = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
            time_matches = list(time_pattern.finditer(table_text))

            dias_semana = ["dom", "seg", "ter", "qua", "qui", "sex", "sab"]
            dias_semana_map = {
                "dom": "Dom",
                "seg": "Seg",
                "ter": "Ter",
                "qua": "Qua",
                "qui": "Qui",
                "sex": "Sex",
                "sab": "Sab"
            }

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

                for stop_word in ["ATENÇÃO", "sigaa", "NTI", "copyright", "srv", "sistema integrado", "portal do discente", "emitido em", "https://", "período letivo"]:
                    stop_idx = dados_raw.lower().find(stop_word.lower())
                    if stop_idx != -1:
                        dados_raw = dados_raw[:stop_idx].strip()

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
                                "matricula": matricula_val,
                                "dia": dias_semana_map[dia_nome],
                                "horario": horario_str,
                                "materia": materia
                            })
            if rows:
                return pd.DataFrame(rows), aluno_key
    except Exception as e:
        print(f"Erro pypdf para {filename}: {e}")

    # 2. Fallback para tabula caso pypdf não consiga extrair a grade
    try:
        matricula_val = None
        try:
            import pypdf
            reader = pypdf.PdfReader(caminho_pdf)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            match_matricula = re.search(r"Matr[ií]cula:\s*(\d+)", text, re.IGNORECASE)
            if match_matricula:
                matricula_val = match_matricula.group(1)
        except Exception:
            pass

        tabelas_brutas = tabula.read_pdf(caminho_pdf, pages="all", multiple_tables=True, lattice=True)
        if tabelas_brutas:
            tabelas_validas = []
            for t in tabelas_brutas:
                t_limpa = t.dropna(how="all").loc[:, ~t.columns.duplicated()]
                if not t_limpa.empty and _eh_grade(t_limpa):
                    tabelas_validas.append(_ajustar_header(t_limpa))

            if tabelas_validas:
                df_aluno_completo = pd.concat(tabelas_validas, ignore_index=True)
                df_grade = extrair_grade_de_df(df_aluno_completo, aluno_key, matricula_val)
                if df_grade is not None and not df_grade.empty:
                    return df_grade, aluno_key
    except Exception as e:
        print(f"Erro tabula fallback para {filename}: {e}")

    return None, filename

def processar_pdfs_para_dataframe(pdf_paths: List[str]):
    if not pdf_paths:
        return None, {
            "sucesso_alunos": [],
            "falha_arquivos": [],
            "total_arquivos": 0,
            "nao_processados_count": 0
        }

    finais = []
    sucesso_alunos = []
    falha_arquivos = []
    seen_students = set()

    print(f"\n==========================================")
    print(f"🚀 INICIANDO PROCESSAMENTO DE {len(pdf_paths)} ARQUIVOS PDF")
    print(f"==========================================")

    for idx, caminho_pdf in enumerate(pdf_paths, start=1):
        raw_filename = os.path.basename(caminho_pdf)
        clean_filename = re.sub(r'^\d+_', '', raw_filename)
        print(f"\n[{idx}/{len(pdf_paths)}] 📄 Arquivo: {clean_filename}")

        df_single, identificador = _processar_single_pdf(caminho_pdf)
        if df_single is not None and not df_single.empty:
            finais.append(df_single)
            nome_limpo = identificador.replace('_', ' ').strip()
            nome_lower = nome_limpo.lower()

            if nome_lower in seen_students:
                print(f"   ℹ️ ALUNO DUPLICADO: '{nome_limpo}' já foi processado neste lote.")
                falha_arquivos.append({
                    "file": clean_filename,
                    "type": "duplicado",
                    "aluno": nome_limpo
                })
            else:
                seen_students.add(nome_lower)
                sucesso_alunos.append(nome_limpo)
                print(f"   ✅ ALUNO CADASTRADO COM SUCESSO: '{nome_limpo}'")
        else:
            print(f"   🔴 FALHA DE LEITURA: Não foi possível extrair horários de '{clean_filename}'")
            falha_arquivos.append({
                "file": clean_filename,
                "type": "leitura",
                "aluno": None
            })

    print(f"\n==========================================")
    print(f"📊 RESUMO DO PROCESSAMENTO NO TERMINAL:")
    print(f" - Total de PDFs enviados: {len(pdf_paths)}")
    print(f" - Alunos únicos cadastrados: {len(sucesso_alunos)}")
    print(f" - PDFs não processados: {len(falha_arquivos)}")
    print(f"==========================================\n")

    process_info = {
        "sucesso_alunos": sucesso_alunos,
        "falha_arquivos": falha_arquivos,
        "total_arquivos": len(pdf_paths),
        "nao_processados_count": len(falha_arquivos)
    }

    if not finais:
        return None, process_info

    base = pd.concat(finais, ignore_index=True)
    base = base.drop_duplicates(subset=['aluno', 'dia', 'horario']).reset_index(drop=True)
    return base, process_info

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