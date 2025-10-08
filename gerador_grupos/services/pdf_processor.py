import pandas as pd
import re
import os
import unicodedata

PADRAO_HORARIO = re.compile(r"^\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*$")
PADRAO_HORA_SOZINHA = re.compile(r"^\s*\d{1,2}:\d{2}\s*$")
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
LIXO = ["atencao", "autenticidade", "sigaa", "verificar"]

def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def _parece_horario(valor: str) -> bool:
    """Detecta se uma célula é um horário (para não tratá-la como matéria)."""
    if valor is None:
        return False
    valor_str = str(valor).strip()
    if not valor_str:
        return False
    if PADRAO_HORARIO.match(valor_str):
        return True
    if PADRAO_HORA_SOZINHA.match(valor_str):
        return True
    if re.match(r"^\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}$", valor_str.replace(" ", "")):
        return True
    return False

def _normalizar_horario_cru(h: str) -> str:
    """Padroniza formatos simples de horário para 'HH:MM - HH:MM'."""
    if h is None:
        return ""
    texto = str(h).strip()
    if not texto or texto.lower() in ["nan", "none", "---"]:
        return ""
    # já no formato completo
    if PADRAO_HORARIO.match(texto):
        return texto.strip()
    # formato "HH:MM"
    if PADRAO_HORA_SOZINHA.match(texto):
        tempo = texto.strip()
        return f"{tempo} - {tempo}"
    # formato "HH:MM-HH:MM" sem espaços
    correspondencia = re.match(r"^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})$", texto.replace(" ", ""))
    if correspondencia:
        return f"{correspondencia.group(1)} - {correspondencia.group(2)}"
    return texto  # retorna cru — será filtrado depois se inválido

def _agrupar_colunas_dias(df: pd.DataFrame):
    """
    Agrupa colunas do dataframe por dia (seg/ter/qua...), retornando um dicionário:
      { 'seg': [col1, col2], 'ter': [colX], ... }
    A classificação é feita pela normalização dos 3 primeiros caracteres do nome da coluna.
    """
    grupos = {dia: [] for dia in DIAS_SEMANA}
    for coluna in df.columns:
        chave = _normalizar(str(coluna))
        if not chave:
            continue
        tres_primeiros = chave[:3]
        if tres_primeiros in grupos:
            grupos[tres_primeiros].append(coluna)
    return grupos

def _mesclar_colunas_dias(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada dia, junta múltiplas colunas que representam esse dia numa única coluna abreviada ('seg', 'ter', ...).
    A prioridade é: primeiro valor NÃO vazio, que NÃO pareça horário e que não seja lixo.
    """
    df_trabalho = df.copy()
    grupos = _agrupar_colunas_dias(df_trabalho)

    # preserva a ordem original das colunas para avaliar prioridades corretamente
    colunas_originais = list(df_trabalho.columns)

    for dia, colunas in grupos.items():
        if not colunas:
            continue
        # mantém a ordem original das colunas dentro do grupo
        colunas_ordenadas = [coluna for coluna in colunas_originais if coluna in colunas]

        mesclado = []
        for indice, linha in df_trabalho.iterrows():
            escolhido = None
            for coluna in colunas_ordenadas:
                valor = str(linha.get(coluna, "")).strip()
                if not valor or valor.lower() in ["nan", "none", "---"]:
                    continue
                # se parecer horário, ignora como matéria
                if _parece_horario(valor):
                    continue
                # se conter palavras inúteis, ignora
                valor_minusculo = valor.lower()
                if any(ruim in valor_minusculo for ruim in LIXO):
                    continue
                escolhido = valor
                break
            if escolhido is None:
                escolhido = "---"
            mesclado.append(escolhido)

        # cria/atualiza coluna do dia 
        df_trabalho[dia] = mesclado

        # remove as colunas originais do grupo 
        for coluna in colunas_ordenadas:
            # só drop se o nome original for diferente do target day
            if coluna != dia and coluna in df_trabalho.columns:
                df_trabalho = df_trabalho.drop(columns=[coluna])

    return df_trabalho

def extrair_grade(df: pd.DataFrame, aluno: str):
    if df is None or df.empty:
        return None

    # 1) primeiro, normaliza e mergeia colunas de dia
    df2 = _mesclar_colunas_dias(df)

    # 2) identifica coluna de horário (procura coluna cujo nome contenha 'hora' ou com amostra de horário)
    coluna_horario = None
    for coluna in df2.columns:
        if "hora" in _normalizar(str(coluna)):
            coluna_horario = coluna
            break
    if not coluna_horario:
        # amostra heurística
        for coluna in df2.columns:
            amostra = df2[coluna].dropna().astype(str).head(15).tolist()
            if any(PADRAO_HORARIO.match(str(valor).strip()) or PADRAO_HORA_SOZINHA.match(str(valor).strip()) for valor in amostra):
                coluna_horario = coluna
                break

    if not coluna_horario:
        return None

    # garantir que coluna_horario seja usado como string padronizada
    # cria uma coluna temporária com horário normalizado
    horario_normalizado = df2[coluna_horario].astype(str).apply(lambda x: _normalizar_horario_cru(x).strip())
    df2["_horario_normalizado"] = horario_normalizado

    resultados = []
    # percorre linhas na ordem original (assim preserva a ordem lida)
    for indice, linha in df2.iterrows():
        valor_horario = str(linha.get("_horario_normalizado", "")).strip()
        if not valor_horario or valor_horario.lower() in ["", "nan", "none", "---"]:
            # ignora linhas sem horário válido
            continue
        # se valor_horario ainda não bate com o formato esperado, tenta normalizar 
        if not PADRAO_HORARIO.match(valor_horario):
            # se for apenas HH:MM, normaliza
            if PADRAO_HORA_SOZINHA.match(valor_horario):
                valor_horario = valor_horario + " - " + valor_horario
            else:
                # se não for formato aceitável, pula
                continue

        # percorre dias em ordem fixa (seg, ter, ...)
        for dia in DIAS_SEMANA:
            # só processa se a coluna existir no df2
            if dia not in df2.columns:
                continue
            materia_cru = str(linha.get(dia, "")).strip()
            # se a célula for horário por engano — transformar em '---'
            if _parece_horario(materia_cru):
                materia = "---"
            else:
                materia = materia_cru if materia_cru and materia_cru.lower() not in ["nan", "none", ""] else "---"
                materia_minuscula = materia.lower()
                if any(ruim in materia_minuscula for ruim in LIXO):
                    materia = "---"

            if materia != "---":
                resultados.append({
                    "aluno": aluno,
                    "dia": dia.capitalize(),            
                    "horario": valor_horario,
                    "materia": materia
            })

    if not resultados:
        return None
    return pd.DataFrame(resultados)

def processar_excel(entrada_excel: str, saida_csv: str):
    print("Processando abas...")
    arquivo_excel = pd.ExcelFile(entrada_excel)

    resultados = []
    vazias = []

    for aba in arquivo_excel.sheet_names:
        df = pd.read_excel(arquivo_excel, sheet_name=aba)
        grade = extrair_grade(df, aba)
        if grade is not None and not grade.empty:
            resultados.append(grade)
        else:
            vazias.append(aba)

    if resultados:
        base = pd.concat(resultados, ignore_index=True)

        # remover duplicados exatos
        base = base.drop_duplicates(subset=["aluno","dia","horario","materia"])

        # ordenar por dia e manter ordem original dentro de cada dia
        ordem = {dia.capitalize(): i for i, dia in enumerate(DIAS_SEMANA)}
        base["dia_ordem"] = base["dia"].map(lambda x: ordem.get(str(x), 99))

        # ordem original por aluno/dia (cumcount sobre a ordem atual preserva a leitura original)
        base["ordem_original"] = base.groupby(["aluno","dia"]).cumcount()

        base = base.sort_values(by=["aluno","dia_ordem","ordem_original"], kind="stable")

        # limpar colunas auxiliares
        base = base.drop(columns=["dia_ordem","ordem_original"])

        # salvar
        base.to_csv(saida_csv, index=False, encoding="utf-8-sig")
        print(f"OK! Registros: {len(base)}  |  Abas vazias/descartadas: {len(vazias)}")
    else:
        print("Nenhum registro válido encontrado.")
        base = pd.DataFrame()

    if vazias:
        print("Atenção: abas sem linhas de grade de horários válidas:")
        for vazia in vazias:
            print(" -", vazia)

    print("Salvo em", repr(saida_csv))
    return base

def criar_base_de_dados_consolidada(entrada_excel: str):
    """Compatibilidade com app.py — apenas chama processar_excel."""
    caminho_saida = os.path.join("..", "session_data")
    os.makedirs(caminho_saida, exist_ok=True)
    
    saida_csv = os.path.join(caminho_saida, "base_consolidada.csv")
    return processar_excel(entrada_excel, saida_csv)

if __name__ == "__main__":
    caminho_dados = os.path.join("..", "session_data")
    os.makedirs(caminho_dados, exist_ok=True)

    # O arquivo de entrada agora é lido de session_data
    entrada = os.path.join(caminho_dados, "consolidado_horarios.xlsx")
    # E o arquivo de saída é salvo lá
    saida = os.path.join(caminho_dados, "base_consolidada.csv")
    
    processar_excel(entrada, saida)