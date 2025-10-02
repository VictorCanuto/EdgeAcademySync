import os
import re
import tabula
import pandas as pd
import unicodedata

# fallback text parser imports (tentamos importar; se não houver PyPDF2, fallback será desabilitado)
try:
    from PyPDF2 import PdfReader
    TEM_PYPDF2 = True
except Exception:
    TEM_PYPDF2 = False

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]

def normalizar_horario(h: str) -> str:
    h = str(h).strip()
    if not h or h.lower() in ["nan", "none", "---"]:
        return "---"
    partes = [x.strip() for x in h.split("-") if x.strip()]
    if len(partes) == 1:
        return f"{partes[0]} - {partes[0]}"
    elif len(partes) == 2:
        return f"{partes[0]} - {partes[1]}"
    else:
        return "---"

def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def _limpar_tabela(df):
    if df is None or df.empty:
        return None
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.duplicated()]
    return df if not df.empty else None

def _eh_grade(df: pd.DataFrame):
    cols = [_normalizar(c) for c in df.columns]
    if any(any(d in c for d in DIAS_SEMANA) for c in cols):
        return True
    if not df.empty:
        primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
        if any(any(d in c for d in DIAS_SEMANA) for c in primeira):
            return True
    return False

def _ajustar_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    primeira = [_normalizar(x) for x in df.iloc[0].tolist()]
    if any(x.startswith("hora") for x in primeira) or \
       any(any(d in c for d in DIAS_SEMANA) for c in primeira):
        df.columns = df.iloc[0]
        df = df.drop(df.index[0]).reset_index(drop=True)
    return df

# ---------- Fallback: extrair tabela por texto (PyPDF2) ----------
def _extrair_texto_de_pdf(caminho):
    if not TEM_PYPDF2:
        return None
    leitor = PdfReader(str(caminho))
    partes = []
    for pagina in leitor.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:
            partes.append("")
    return "\n".join(partes)

def _analisar_bloco_horario_do_texto(texto):
    if not texto:
        return None
    linhas = [linha.rstrip() for linha in texto.splitlines() if linha.strip()]
    # localizar linha com dias (linha que contenha 3+ tokens parecidos com dias)
    indice_dia = None
    for i, linha in enumerate(linhas):
        linha_minuscula = linha.lower()
        if any(palavra_chave in linha_minuscula for palavra_chave in ["horar", "horário", "horarios", "tabela de horarios", "tabela de horários"]):
            # procurar a linha de dias nas próximas 4 linhas
            for j in range(i, min(i+4, len(linhas))):
                contagem_seg = sum(1 for d in DIAS_SEMANA if d in linhas[j].lower())
                if contagem_seg >= 3:
                    indice_dia = j
                    break
            if indice_dia is not None:
                break
    if indice_dia is None:
        # fallback: procura qualquer linha com 3+ tokens de dia
        for i, linha in enumerate(linhas):
            if sum(1 for d in DIAS_SEMANA if d in linha.lower()) >= 3:
                indice_dia = i
                break
    if indice_dia is None:
        return None

    linha_cabecalho = linhas[indice_dia]
    # extrai tokens candidatos a dias
    tokens_cabecalho = re.split(r'\s{2,}|\t', linha_cabecalho)
    if len(tokens_cabecalho) < 3:
        tokens_cabecalho = linha_cabecalho.split()
    dias_cabecalho = []
    for token in tokens_cabecalho:
        token_normalizado = re.sub(r'[^A-Za-zÀ-ú]', '', token).lower()
        if any(token_normalizado.startswith(d) for d in DIAS_SEMANA):
            dias_cabecalho.append(token_normalizado[:3].title())
    if len(dias_cabecalho) < 3:
        tokens = linha_cabecalho.split()
        dias_cabecalho = [token.lower()[:3].title() for token in tokens if any(token.lower().startswith(d) for d in DIAS_SEMANA)]
    # analisar as linhas seguintes até marca de fim (atenção / autenticidade / sigaa)
    linhas_dados = []
    for linha in linhas[indice_dia+1:]:
        if re.search(r'\b(aten[cç][ãa]o|para verificar|autenticidade|sigaa)\b', linha.lower()):
            break
        correspondencia = re.match(r'^\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*(.*)$', linha)
        if not correspondencia:
            continue
        horario = correspondencia.group(1).strip()
        resto = correspondencia.group(2).strip()
        celulas = re.split(r'\s{2,}|\t', resto)
        if len(celulas) < len(dias_cabecalho):
            tokens = resto.split()
            # heurística de agrupar tokens com base em '---' ou tokens MAIÚSCULOS
            celulas = []
            atual = []
            for token in tokens:
                atual.append(token)
                if token.strip() == '---' or re.match(r'^[A-Z0-9]{2,}$', token) or len(atual) > 3:
                    celulas.append(' '.join(atual).strip())
                    atual = []
            if atual:
                celulas.append(' '.join(atual).strip())
        if len(celulas) < len(dias_cabecalho):
            celulas += ['---'] * (len(dias_cabecalho) - len(celulas))
        elif len(celulas) > len(dias_cabecalho):
            celulas = celulas[:len(dias_cabecalho)]
        linhas_dados.append((horario, celulas))
    if not linhas_dados:
        return None
    colunas = ["Horário"] + dias_cabecalho
    dados = []
    for horario, celulas in linhas_dados:
        dados.append([horario] + [celula if celula and celula.strip() else '---' for celula in celulas])
    return pd.DataFrame(dados, columns=colunas)

# ---------- Helpers para limpar tabelas vindas do tabula ----------
def _colapsar_colunas_em_dias(tabela: pd.DataFrame):
    # se já tiver 'Horário' e colunas de dias, só padroniza nomes e retorna
    colunas = list(tabela.columns)
    colunas_normalizadas = [_normalizar(c) for c in colunas]
    # detecta índices onde existe nome de dia no cabeçalho (ou parecido)
    posicoes_dias = []
    for i, coluna in enumerate(colunas):
        if any(d in _normalizar(str(coluna)) for d in DIAS_SEMANA):
            posicoes_dias.append(i)
    # se não achar posições, retorna original
    if not posicoes_dias:
        return tabela
    # construir novo df com Horário + cada dia (agrupar colunas entre posicoes_dias[i] e next)
    novas_colunas = ["Horário"]
    for indice in posicoes_dias:
        nome_coluna = str(colunas[indice])
        # normaliza para 3 letras no título
        for dia in DIAS_SEMANA:
            if dia in _normalizar(nome_coluna):
                novas_colunas.append(dia.title())
                break
        else:
            novas_colunas.append(nome_coluna[:3].title())
    # agora para cada linha, agrupar valores entre indices
    linhas = []
    for _, linha in tabela.iterrows():
        valor_horario = None
        # tenta pegar o horário de qualquer coluna que pareça hora
        for coluna in colunas:
            valor = str(linha.get(coluna,"")).strip()
            if re.match(r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', valor):
                valor_horario = valor
                break
        if valor_horario is None:
            # fallback: primeira coluna
            valor_horario = str(linha[colunas[0]]).strip()
        valores_dias = []
        for i, indice in enumerate(posicoes_dias):
            inicio = indice
            fim = posicoes_dias[i+1] if i+1 < len(posicoes_dias) else len(colunas)
            # pegar primeiro valor não vazio no grupo inicio:fim
            valor_dia = '---'
            for indice_coluna in range(inicio, fim):
                valor_celula = str(linha[colunas[indice_coluna]]).strip()
                if valor_celula and valor_celula.lower() not in ['nan','none','---']:
                    valor_dia = valor_celula
                    break
            valores_dias.append(valor_dia)
        linhas.append([valor_horario] + valores_dias)
    df_novo = pd.DataFrame(linhas, columns=novas_colunas)
    # normalizar horário
    df_novo["Horário"] = df_novo["Horário"].apply(normalizar_horario)
    return df_novo

def _parece_malformada(tabela: pd.DataFrame):
    if tabela is None or tabela.empty:
        return True
    # caso: apenas 1 linha e a primeira célula contém muitas quebras de linha quando convertido pra str
    # (aparece quando tabula junta tudo numa célula multiline)
    try:
        if tabela.shape[0] <= 1:
            # se qualquer célula contiver \n é sinal de parsing ruim
            for coluna in tabela.columns:
                valor = str(tabela.iloc[0][coluna])
                if "\n" in valor and len(valor.splitlines()) > 3:
                    return True
    except Exception:
        pass
    # caso: muitas colunas 'Unnamed' indicando split desalinhado
    contagem_sem_nome = sum(1 for coluna in tabela.columns if str(coluna).lower().startswith("unnamed"))
    if contagem_sem_nome >= 3:
        # e existem colunas de dia espalhadas -> considerar malformada (vai precisar de colapso)
        if any(any(d in _normalizar(str(coluna)) for d in DIAS_SEMANA) for coluna in tabela.columns):
            return True
    return False

# ---------- Função principal ----------
def ler_pdfs_para_excel(pasta_pdfs, saida_excel):
    print("Iniciando leitura de PDFs...")
    print("Lendo PDFs de:", pasta_pdfs)
    arquivos = [arquivo for arquivo in os.listdir(pasta_pdfs) if arquivo.lower().endswith(".pdf")]
    if not arquivos:
        print("Nenhum PDF encontrado.")
        return

    ok, vazios = 0, []
    with pd.ExcelWriter(saida_excel, engine="openpyxl") as escritor:
        for nome_arquivo in arquivos:
            caminho = os.path.join(pasta_pdfs, nome_arquivo)
            print("\n→", nome_arquivo)
            try:
                candidatos = tabula.read_pdf(
                    caminho, pages="all", multiple_tables=True,
                    lattice=True, encoding='latin-1', silent=True
                )
            except UnicodeDecodeError:
                candidatos = tabula.read_pdf(
                    caminho, pages="all", multiple_tables=True,
                    lattice=True, encoding='iso-8859-1', silent=True
                )
            except Exception as e:
                print("   ERRO geral (tabula):", e)
                candidatos = []

            candidatos_limpos = [_limpar_tabela(t) for t in candidatos if t is not None]
            candidatos_ajustados = [_ajustar_cabecalho(t) for t in candidatos_limpos if t is not None]
            tabelas_validas = [t for t in candidatos_ajustados if t is not None and _eh_grade(t)]

            tabela_final = None
            if tabelas_validas:
                tabela_final = pd.concat(tabelas_validas, ignore_index=True)

            # Se parece mal-formada, tenta fallback por texto (PyPDF2)
            if _parece_malformada(tabela_final):
                if TEM_PYPDF2:
                    texto = _extrair_texto_de_pdf(caminho)
                    df_fallback = _analisar_bloco_horario_do_texto(texto)
                    if df_fallback is not None:
                        tabela_final = df_fallback
                        print("   Fallback por texto: extraído com sucesso.")
                    else:
                        print("   Fallback por texto: não encontrou bloco de horários.")
                else:
                    print("   Fallback por texto indisponível (PyPDF2 não instalado).")

            # Se ainda existe tabela_final e possui cols desordenadas, tentar colapsar colunas em dias
            if tabela_final is not None and not tabela_final.empty:
                tabela_final = tabela_final.rename(columns={c: c for c in tabela_final.columns})
                # se tiver muitos Unnamed com dias espalhados, colapsar
                if any("unnamed" in str(coluna).lower() for coluna in tabela_final.columns):
                    tabela_final = _colapsar_colunas_em_dias(tabela_final)
                else:
                    # renomear coluna de horario se detectada
                    coluna_horario = None
                    for coluna in tabela_final.columns:
                        if "hora" in _normalizar(coluna):
                            coluna_horario = coluna
                            break
                    if coluna_horario and coluna_horario != "Horário":
                        tabela_final = tabela_final.rename(columns={coluna_horario: "Horário"})
                    if "Horário" in tabela_final.columns:
                        tabela_final["Horário"] = tabela_final["Horário"].apply(normalizar_horario)

            if tabela_final is None or tabela_final.empty:
                vazios.append(nome_arquivo)
                print("AVISO: Nenhuma grade de horários encontrada ou tabela vazia.")
                continue

            nome_aba = os.path.splitext(nome_arquivo)[0][:30]
            tabela_final.to_excel(escritor, sheet_name=nome_aba, index=False)
            ok += 1
            print(f"   OK: escrita aba {nome_aba} (shape {tabela_final.shape})")

    print("\nFinalizado. Abas criadas:", ok, " |  Sem grade:", len(vazios))
    print("Gerado:", saida_excel)

if __name__ == "__main__":
    pasta = "ALL_PDFS"
    saida = "consolidado_horarios.xlsx"
    ler_pdfs_para_excel(pasta, saida)