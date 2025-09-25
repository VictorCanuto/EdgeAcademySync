import os
import re
import pandas as pd
import unicodedata

# Dias da semana aceitos (mantém a lista completa, mas vamos ignorar Dom ao gerar CSV)
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]

# Regex para validar intervalos de horários
PAT_HORARIO = re.compile(r"^\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*$")

# Palavras ou padrões que identificam ruído
LIXO = ["sigaa", "nti", "copyright", "srv1inst1"]

def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def extrair_grade(df: pd.DataFrame, aluno: str):
    # tenta detectar a coluna de horários
    col_horario = None
    for c in df.columns:
        amostra = df[c].dropna().astype(str).head(10).tolist()
        if any(PAT_HORARIO.match(str(x).strip()) for x in amostra):
            col_horario = c
            break

    if not col_horario:
        return None

    resultados = []
    for _, linha in df.iterrows():
        horario = str(linha[col_horario]).strip()
        if not PAT_HORARIO.match(horario):
            continue  # se não parece horário, pula

        # normaliza horários sem traço → "07:30" vira "07:30 - 07:30"
        if "-" not in horario:
            horario = horario + " - " + horario

        for c in df.columns:
            if c == col_horario:
                continue
            dia = str(c).strip().title()
            if _normalizar(dia).startswith("dom"):
                continue
            if not any(_normalizar(dia).startswith(d) for d in DIAS_SEMANA):
                continue

            materia = str(linha[c]).strip()
            if not materia or materia.lower() in ["nan", "none", "---"]:
                materia = "---"
            else:
                if any(bad in materia.lower() for bad in LIXO):
                    materia = "---"

            resultados.append({
                "aluno": aluno,
                "dia": dia,
                "horario": horario,
                "materia": materia
            })

    return pd.DataFrame(resultados) if resultados else None


def criar_base_de_dados_consolidada(caminho_excel: str) -> pd.DataFrame:
    if not os.path.exists(caminho_excel):
        print("ERRO:", caminho_excel, "não existe.")
        return pd.DataFrame()

    xls = pd.ExcelFile(caminho_excel)
    sheets = xls.sheet_names
    finais, vazios = [], []

    print(f"Processando {len(sheets)} abas...")

    for aluno in sheets:
        df = pd.read_excel(xls, sheet_name=aluno)
        df = df.loc[:, ~df.columns.duplicated()]
        if df.empty:
            vazios.append(aluno)
            continue

        df_grade = extrair_grade(df, aluno)
        if df_grade is None or df_grade.empty:
            vazios.append(aluno)
            continue

        finais.append(df_grade)

    if not finais:
        print("Nada válido após a limpeza.")
        return pd.DataFrame()

    base = pd.concat(finais, ignore_index=True)

    # Deduplica: um registro por aluno-dia-horario
    base = (
        base.sort_values(by=["aluno", "dia", "horario", "materia"])
        .drop_duplicates(subset=["aluno", "dia", "horario"], keep="last")
    )

    if not finais:
        print("Nada válido após a limpeza.")
        return pd.DataFrame()

    base = pd.concat(finais, ignore_index=True)
    
    # Remove Duplicatas
    base = base.drop_duplicates(subset=['aluno', 'dia', 'horario'])

    # Ordena por aluno, dia da semana e horário
    ordem_dias = {d.title(): i for i, d in enumerate(DIAS_SEMANA) if d != "dom"}
    base["ord_dia"] = base["dia"].map(ordem_dias)
    base["ord_hora"] = (
        base["horario"].str.extract(r"^(\d{1,2}):(\d{2})")[0].astype(float) * 60
        + base["horario"].str.extract(r"^(\d{1,2}):(\d{2})")[1].astype(float)
    )
    base = base.sort_values(by=["aluno", "ord_dia", "ord_hora"]).drop(columns=["ord_dia", "ord_hora"])

    print(f"OK! Registros: {len(base)}  |  Abas vazias/descartadas: {len(vazios)}")
    if vazios:
        print("Atenção: abas sem linhas de grade de horários válidas:")
        for a in vazios:
            print(" -", a)
    return base


if __name__ == "__main__":
    xlsx_in = "consolidado_horarios.xlsx"
    base = criar_base_de_dados_consolidada(xlsx_in)
    if not base.empty:
        base.to_csv("base_consolidada.csv", index=False)
        print("Salvo em 'base_consolidada.csv'")
