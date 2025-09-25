# app.py — EdgeSync (refatorado)
# - remove duplicações da UI
# - não usa st.rerun() nas ações (tabs não “voltam”)
# - export PDF sem showPage() extra
# - usa session_state para mover/trocar/recolocar alunos

import streamlit as st
import pandas as pd
from io import BytesIO
from grupos import formar_grupos, sugerir_trocas, balancear_grupos  # sua lógica existente
import re
import base64
import os
from reader import ler_pdfs_para_excel, normalizar_horario
from processador import criar_base_de_dados_consolidada

#------
import plotly.express as px

from openpyxl import Workbook

st.set_page_config(page_title="AcademySync", layout="wide")

# --- Converter imagens para base64 ---
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_light = get_base64_image("logos/modo claro.png")
logo_dark = get_base64_image("logos/modo dark.png")

# --- Logo Centralizado no Topo (modo claro/escuro) ---
st.markdown(
    f"""
    <style>
        .logo-container {{
            display: flex;
            justify-content: center;
        }}
        .logo-light {{
            display: block;
        }}
        .logo-dark {{
            display: none;
        }}
        @media (prefers-color-scheme: dark) {{
            .logo-light {{ display: none; }}
            .logo-dark {{ display: block; }}
        }}
    </style>
    <div class="logo-container">
        <img class="logo-light" src="data:image/png;base64,{logo_light}" width="600">
        <img class="logo-dark" src="data:image/png;base64,{logo_dark}" width="600">
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------- PDFs ----------------
st.subheader("Carregar comprovantes (PDF) e gerar base")
uploaded = st.file_uploader("Envie um ou mais PDFs", type=["pdf"], accept_multiple_files=True)
col_up_a, col_up_b = st.columns([0.7, 0.3])
with col_up_b:
    if st.button("Processar PDFs"):
        pasta = "ALL_PDFS"
        os.makedirs(pasta, exist_ok=True)
        for f in os.listdir(pasta):
            if f.lower().endswith(".pdf"):
                try:
                    os.remove(os.path.join(pasta, f))
                except Exception:
                    pass
        if not uploaded:
            st.warning("Nenhum arquivo enviado.")
        else:
            for uf in uploaded:
                try:
                    with open(os.path.join(pasta, uf.name), "wb") as out:
                        out.write(uf.getbuffer())
                except Exception as e:
                    st.error(f"Falha ao salvar {uf.name}: {e}")

            xlsx_out = "consolidado_horarios.xlsx"
            ler_pdfs_para_excel(pasta, xlsx_out)
            base_df = criar_base_de_dados_consolidada(xlsx_out)
            if base_df is None or base_df.empty:
                st.error("Nenhum dado válido gerado a partir dos PDFs.")
            else:
                base_df.to_csv("base_consolidada.csv", index=False)
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.success("Base atualizada com sucesso! Você pode navegar nas abas abaixo.")

# ---------------- Carregamento & Normalização ----------------
@st.cache_data
def carregar_dados():
    """Lê 'base_consolidada.csv' gerado por reader/processador e normaliza strings."""
    try:
        df = pd.read_csv("base_consolidada.csv")
    except FileNotFoundError:
        return None
    for col in ("aluno", "dia", "horario", "materia"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    # Normaliza horários para formato consistente
    if 'horario' in df.columns:
        df['horario'] = df['horario'].apply(normalizar_horario)
    # Normaliza dias (Seg, Ter, ...)
    if 'dia' in df.columns:
        df['dia'] = df['dia'].astype(str).str.strip().str.title()
    df.dropna(subset=["horario"], inplace=True)
    return df

# ---------------- Estado e utilidades ----------------
def _ensure_states():
    st.session_state.setdefault("removidos", [])
    st.session_state.setdefault("grupos_result", None)

def _find_group_index_by_id(grupos, group_id):
    for idx, g in enumerate(grupos):
        if g.get("Grupo") == group_id:
            return idx
    return None

def _add_removido(nome: str):
    nome = (nome or "").strip()
    if nome and nome not in st.session_state["removidos"]:
        st.session_state["removidos"].append(nome)

def _del_removido(nome: str):
    try:
        st.session_state["removidos"].remove((nome or "").strip())
    except ValueError:
        pass

# ---------------- Ações (sem st.rerun) ----------------
def apply_move_session(aluno, target_group_id):
    aluno = (aluno or "").strip()
    res = st.session_state.get("grupos_result")
    if not res:
        st.warning("Gere os grupos primeiro.")
        return
    grupos = res["grupos"]

    src_idx = None
    for i, g in enumerate(grupos):
        if any(m.strip() == aluno for m in g["Membros"]):
            src_idx = i
            break
    tgt_idx = _find_group_index_by_id(grupos, target_group_id)
    if tgt_idx is None:
        st.warning("Grupo de destino não encontrado.")
        return
    if src_idx == tgt_idx and src_idx is not None:
        st.info("Aluno já está nesse grupo.")
        return

    if src_idx is not None:
        for m in list(grupos[src_idx]["Membros"]):
            if m.strip() == aluno:
                grupos[src_idx]["Membros"].remove(m)
                break
        grupos[src_idx]["Membros"].sort()

    if not any(m.strip() == aluno for m in grupos[tgt_idx]["Membros"]):
        grupos[tgt_idx]["Membros"].append(aluno)
        grupos[tgt_idx]["Membros"].sort()

    _del_removido(aluno)
    st.session_state["grupos_result"]["grupos"] = grupos
    st.toast(f"{aluno} alocado no Grupo {grupos[tgt_idx]['Grupo']}")

def apply_swap_session(aluno_a, aluno_b, group_b_id):
    aluno_a, aluno_b = (aluno_a or "").strip(), (aluno_b or "").strip()
    res = st.session_state.get("grupos_result")
    if not res:
        st.warning("Gere os grupos primeiro.")
        return
    grupos = res["grupos"]

    a_idx = None
    for i, g in enumerate(grupos):
        if any(m.strip() == aluno_a for m in g["Membros"]):
            a_idx = i; break
    b_idx = _find_group_index_by_id(grupos, group_b_id)
    if b_idx is None or a_idx is None:
        st.warning("Grupos de origem/destino não encontrados."); return
    if not any(m.strip() == aluno_b for m in grupos[b_idx]["Membros"]):
        st.warning(f"{aluno_b} não está no Grupo {group_b_id}."); return

    for m in list(grupos[a_idx]["Membros"]):
        if m.strip() == aluno_a:
            grupos[a_idx]["Membros"].remove(m); break
    for m in list(grupos[b_idx]["Membros"]):
        if m.strip() == aluno_b:
            grupos[b_idx]["Membros"].remove(m); break

    grupos[a_idx]["Membros"].append(aluno_b)
    grupos[b_idx]["Membros"].append(aluno_a)
    grupos[a_idx]["Membros"].sort(); grupos[b_idx]["Membros"].sort()

    _del_removido(aluno_a); _del_removido(aluno_b)
    st.session_state["grupos_result"]["grupos"] = grupos
    st.toast(f"Troca realizada: {aluno_a} ⇄ {aluno_b}")

# ---------------- Export helpers ----------------
def grupos_para_dataframe(grupos):
    """Converte os grupos em DataFrame longo (uma linha por membro)."""
    linhas = []
    for g in grupos:
        gid, dia, hor = g.get("Grupo"), g.get("Dia"), g.get("Horário")
        membros = sorted(g.get("Membros", []), key=lambda x: x.strip().lower())
        if membros:
            for m in membros: linhas.append({"Grupo": gid, "Dia": dia, "Horário": hor, "Aluno": m})
        else:
            linhas.append({"Grupo": gid, "Dia": dia, "Horário": hor, "Aluno": ""})
    df = pd.DataFrame(linhas, columns=["Grupo", "Dia", "Horário", "Aluno"])
    return df.sort_values(["Grupo", "Aluno"], kind="stable").reset_index(drop=True) if not df.empty else df

def montar_pdf_grupos(grupos):
    """Gera PDF em memória com lista de grupos e alunos (sem showPage extra)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, altura = A4
    margem = 2*cm
    y = altura - margem

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margem, y, "Grupos de Acompanhamento")
    y -= 1.0*cm

    c.setFont("Helvetica", 11)
    for g in grupos:
        header = f"Grupo {g.get('Grupo')} — {g.get('Dia')} ({g.get('Horário')})"
        c.setFont("Helvetica-Bold", 11); c.drawString(margem, y, header); y -= 0.6*cm
        c.setFont("Helvetica", 11)

        membros = sorted(g.get("Membros", []), key=lambda x: x.strip().lower())
        if not membros:
            c.drawString(margem+0.5*cm, y, "— (sem alunos)"); y -= 0.5*cm
        else:
            for m in membros:
                c.drawString(margem+0.5*cm, y, f"• {m}"); y -= 0.5*cm
                if y <= margem:
                    c.showPage(); y = altura - margem; c.setFont("Helvetica", 11)

        y -= 0.3*cm
        if y <= margem:
            c.showPage(); y = altura - margem; c.setFont("Helvetica", 11)

    # sem c.showPage() final → evita “página espelhada”
    c.save(); buf.seek(0)
    return buf.getvalue()

# ---------------- Visualizações auxiliares ----------------
def criar_grid_visual(grid_booleana_ocupado, titulo):
    def fmt(ocupado): return "INDISPONÍVEL" if ocupado else "DISPONÍVEL"
    def style_cell(ocupado):
        base = "text-align:center;border:1px solid #D3D3D3;"
        return base + ("background-color:#FFC7CE;color:#9C0006;" if ocupado
                       else "background-color:#C6EFCE;color:#006100;")
    st.header(titulo)
    st.table(grid_booleana_ocupado.style.map(style_cell).format(fmt))

from datetime import datetime

def _parse_time(s: str):
    return datetime.strptime(s.strip(), "%H:%M").time()

def horarios_conflitam(horario_a: str, horario_b: str) -> bool:
    """Verifica se dois intervalos (ex.: '09:20 - 10:10') se sobrepõem."""
    try:
        ini_a, fim_a = [x.strip() for x in horario_a.split("-")]
        ini_b, fim_b = [x.strip() for x in horario_b.split("-")]
        ini_a, fim_a = _parse_time(ini_a), _parse_time(fim_a)
        ini_b, fim_b = _parse_time(ini_b), _parse_time(fim_b)
        return ini_a < fim_b and fim_a > ini_b
    except Exception:
        return False

def criar_agenda_geral_completa(df):
    try:
        df = df.drop_duplicates(subset=["aluno", "dia", "horario", "materia"]).copy()
        df["horario"] = df["horario"].apply(normalizar_horario)

        horarios = sorted(df["horario"].unique())
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
        alunos = df["aluno"].unique()
        agenda = pd.DataFrame(0, index=horarios, columns=dias)

        for h in horarios:
            for d in dias:
                livres = 0
                for a in alunos:
                    subset = df[(df.aluno == a) & (df.dia == d)]
                    ocupado = False
                    for h_aluno, materia in zip(subset["horario"], subset["materia"]):
                        if materia not in ["", "---"] and horarios_conflitam(h, h_aluno):
                            ocupado = True
                            break
                    if not ocupado:
                        livres += 1
                agenda.loc[h, d] = livres
        return agenda
    except Exception as e:
        st.error(f"Erro ao criar agenda: {e}")
        return pd.DataFrame()

def obter_alunos_disponiveis_especifico(df, dia, horario):
    """Obtém alunos disponíveis usando a mesma lógica da criar_agenda_geral_completa (conflitos de intervalo)."""
    livres = []
    for a in df["aluno"].unique():
        df_a = df[(df.aluno == a) & (df.dia == dia)]
        ocupado = False
        for h_aluno, materia in zip(df_a['horario'], df_a['materia']):
            if materia not in [None, '', '---'] and horarios_conflitam(horario, h_aluno):
                ocupado = True
                break
        if not ocupado:
            livres.append(a)
    return sorted(livres)


def visualizar_agenda_geral_completa(df):
    st.header("📊 Agenda Geral Completa - Alunos Disponíveis por Horário")
    
    # Verifica se há dados duplicados
    duplicatas = df.duplicated(subset=['aluno', 'dia', 'horario']).sum()
    if duplicatas > 0:
        st.warning(f"⚠️ Encontradas {duplicatas} entradas duplicadas na base de dados")
        # Remove duplicatas para exibição
        df = df.drop_duplicates(subset=['aluno', 'dia', 'horario'])
    
    agenda = criar_agenda_geral_completa(df)
    
    if agenda.empty:
        st.error("Não foi possível gerar a agenda. Verifique os dados.")
        return
    
    def fmt_cell(v): 
        return f"{int(v)} DISPONÍVEIS" if v > 0 else "Livre"
    
    def sty_cell(v):
        base = "text-align:center;border:1px solid #D3D3D3;cursor:pointer;padding:8px;"
        if v == 0:   
            cor = "background-color:#F8F9FA;color:#6C757D;font-weight:normal;"
        elif v <= 15:
            cor = "background-color:#F8D7DA;color:#721C24;font-weight:bold;"
        elif v <= 19:
            cor = "background-color:#FFF3CD;color:#856404;font-weight:bold;"
        elif v <= 24:
            cor = "background-color:#D4EDDA;color:#155724;font-weight:bold;"
        else:      
            cor = "background-color:#28A745;color:white;font-weight:bold;"
        return base + cor
    
    st.table(agenda.style.map(sty_cell).format(fmt_cell).set_table_styles([]))
    
    st.subheader("🔍 Ver alunos disponíveis em horário específico")
    col1, col2 = st.columns(2)
    with col1:  
        h_sel = st.selectbox("Horário:", options=agenda.index.tolist(), key="horario_select")
    with col2:  
        d_sel = st.selectbox("Dia:", options=agenda.columns.tolist(), key="dia_select")
    
    alunos_disp = obter_alunos_disponiveis_especifico(df, d_sel, h_sel)
    st.write(f"**{len(alunos_disp)} alunos disponíveis em {h_sel} ({d_sel})**")
    
    if alunos_disp:
        # Mostra estatísticas
        st.info(f"Total de alunos únicos na base: {len(df['aluno'].unique())}")
        
        cols = st.columns(2 if len(alunos_disp) > 10 else 1)
        for i, a in enumerate(alunos_disp): 
            cols[i % len(cols)].write(f"• {a}")
    else:
        st.info("Nenhum aluno disponível neste horário.")

# ---------------- App (única seção) ----------------
_ensure_states()
base = carregar_dados()
col1, col2 = st.columns([0.9, 0.1])
with col1:
    st.title("AcademySync")

tab1, tab2, tab3, tab4 = st.tabs(["Cruzamento de Grupo", "Visualização Individual", "Agenda Geral", "Relatório de Grupos"])

# ----- Tab 1
with tab1:
    if base is None:
        st.error("Sem base de dados. Adicione os arquivos PDF e aperte em processar.")
    else:
        alunos = sorted(base["aluno"].unique())
        # garante lista de horários normalizada para exibição
        horarios = sorted(base["horario"].unique())
        dias = ["Seg","Ter","Qua","Qui","Sex","Sab"]

        selec = st.multiselect("Selecione um ou mais alunos para ver a disponibilidade:",
                               options=alunos, key="tab1_select")
        if not selec:
            st.info("Por favor, selecione pelo menos um aluno para começar.")
        elif len(selec) == 1:
            a = selec[0]
            # Cria grid por conflito de intervalos (mais robusto que igualdade exata)
            grid = pd.DataFrame(False, index=horarios, columns=dias)
            df_a = base[base.aluno == a]
            for _, row in df_a.iterrows():
                dia_row = str(row.get('dia', '')).strip().title()
                h_aluno = row.get('horario')
                materia = str(row.get('materia', '---')).strip()
                if not dia_row or dia_row not in dias:
                    continue
                if materia in ['', '---', 'nan', 'None']:
                    continue
                for H in horarios:
                    try:
                        if horarios_conflitam(H, h_aluno):
                            grid.at[H, dia_row] = True
                    except Exception:
                        continue
            criar_grid_visual(grid, f"Grade de Horários de {a}")
        else:
            # combinação de múltiplos alunos (OR dos grids individuais)
            grid_comb = pd.DataFrame(False, index=horarios, columns=dias)
            for a in selec:
                df_a = base[base.aluno == a]
                if df_a.empty: continue
                grid = pd.DataFrame(False, index=horarios, columns=dias)
                for _, row in df_a.iterrows():
                    dia_row = str(row.get('dia', '')).strip().title()
                    h_aluno = row.get('horario')
                    materia = str(row.get('materia', '---')).strip()
                    if not dia_row or dia_row not in dias:
                        continue
                    if materia in ['', '---', 'nan', 'None']:
                        continue
                    for H in horarios:
                        try:
                            if horarios_conflitam(H, h_aluno):
                                grid.at[H, dia_row] = True
                        except Exception:
                            continue
                grid_comb |= grid
            criar_grid_visual(grid_comb, f"Disponibilidade Combinada ({len(selec)} alunos)")
# ----- Tab 2
with tab2:
    st.header("Formação de Grupos (Dinâmica)")
    st.caption("Defina quantos grupos deseja e configure blocos com dias e janelas de horário.")

    num_grupos = st.number_input("Número de grupos", 1, 20, 3, 1)

    st.markdown("### Blocos de horários (visual)")
    st.session_state.setdefault("blocos_df", pd.DataFrame([
        {"nome":"Manhã",  "inicio":8,  "fim":11, "dias_str":"Seg, Ter, Qua, Qui, Sex"},
        {"nome":"Manhã2", "inicio":9,  "fim":12, "dias_str":"Seg, Ter, Qua, Qui, Sex"},
        {"nome":"Tarde",  "inicio":14, "fim":17, "dias_str":"Seg, Ter, Qua, Qui, Sex"},
    ]))
    dias_opts = ["Seg","Ter","Qua","Qui","Sex","Sab"]

    c1, c2 = st.columns([0.25,0.75])
    with c1:
        if st.button("➕ Adicionar bloco"):
            st.session_state["blocos_df"] = pd.concat(
                [st.session_state["blocos_df"],
                 pd.DataFrame([{"nome":"Novo bloco","inicio":8,"fim":11,"dias_str":"Seg, Ter, Qua, Qui, Sex"}])],
                ignore_index=True
            )
    with c2: st.caption("Edite: nome, início, fim e dias (texto: Seg, Ter, Qua...).")

    blocos_df = st.data_editor(st.session_state["blocos_df"], key="editor_blocos",
                               width="stretch", num_rows="dynamic", hide_index=True)

    def _parse_dias(s):
        if not isinstance(s,str): return []
        partes = [p.strip().title() for p in s.replace(";", ",").split(",") if p.strip()]
        return [p for p in partes if p in dias_opts]

    blocos_validos = []
    for _, row in blocos_df.iterrows():
        try:
            ini, fim = int(row["inicio"]), int(row["fim"])
            if ini >= fim: continue
            dias_l = _parse_dias(row.get("dias_str",""))
            if not dias_l: continue
            nome = str(row.get("nome") or f"{ini:02d}h-{fim:02d}h")
            blocos_validos.append({"nome":nome, "inicio":ini, "fim":fim, "dias":dias_l})
        except Exception:
            continue

    if base is not None:
        m1,m2,m3 = st.columns(3)
        m1.metric("Alunos únicos", len(base["aluno"].unique()))
        m2.metric("Dias únicos",   len(base["dia"].unique()))
        m3.metric("Horários únicos", len(base["horario"].unique()))

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Gerar Grupos de Acompanhamento"):
            if base is None:
                st.error("Base de dados não carregada.")
            elif not blocos_validos:
                st.error("Configure pelo menos um bloco válido.")
            else:
                st.session_state["grupos_result"] = formar_grupos(
                    base, num_grupos=num_grupos, blocos=blocos_validos
                )
                st.success("Grupos gerados!")

    with col_b:
        if st.button("Rebalancear"):
            res = st.session_state.get("grupos_result")
            if res:
                balancear_grupos(res["grupos"], res["mapa_disponibilidade"], res["slots_por_aluno"])
                for g in res["grupos"]: g["Membros"].sort()
                st.toast("Grupos reequilibrados!")
            else:
                st.info("Gere os grupos primeiro.")

    with col_c:
        if st.button("Limpar Resultado"):
            st.session_state["grupos_result"] = None
            st.session_state["removidos"].clear()

    # Render dos grupos / ações / export
    res = st.session_state.get("grupos_result")
    if res:
        grupos = res["grupos"]
        mapa_disponibilidade = res["mapa_disponibilidade"]
        slots_por_aluno = res["slots_por_aluno"]

        for g in grupos:
            st.subheader(f"Grupo {g['Grupo']} — {g['Dia']} ({g['Horário']}) — {len(g['Membros'])} alunos")
            for i, membro in enumerate(sorted(g["Membros"], key=lambda x: x.strip()), 1):
                col1,col2 = st.columns([0.8,0.2])
                with col1: st.write(f"{i}. {membro}")
                with col2:
                    if st.button("Remover", key=f"rm__{g['Grupo']}__{membro}"):
                        idxg = _find_group_index_by_id(grupos, g["Grupo"])
                        for m in list(grupos[idxg]["Membros"]):
                            if m.strip()==membro.strip():
                                grupos[idxg]["Membros"].remove(m); break
                        grupos[idxg]["Membros"].sort()
                        _add_removido(membro.strip())
                        st.toast(f"{membro} removido do Grupo {g['Grupo']}")

                with st.expander(f"Sugestões para {membro}", expanded=False):
                    sugs = sugerir_trocas(membro.strip(), grupos, mapa_disponibilidade, slots_por_aluno)
                    mv = sugs.get("mover_para_grupo", [])
                    tr = sugs.get("troca_simples", [])

                    if not mv and not tr:
                        st.info("Sem sugestões para este aluno.")

                    if mv:
                        st.markdown("**Mover para:**")
                        for idx_mv, s in enumerate(mv):
                            label = f"Grupo {s['para_grupo']} ({s['dia']} • {s['horario']})"
                            if st.button(f"Mover → {label}", key=f"mv__{membro}__{s['para_grupo']}__{idx_mv}"):
                                apply_move_session(membro, s["para_grupo"])

                    if tr:
                        st.markdown("**Trocas 1-para-1:**")
                        for idx_tr, s in enumerate(tr):
                            label = f"Trocar com {s['trocar_com']} — Grupo {s['grupo_destino']} ({s['dia_destino']} • {s['horario_destino']})"
                            if st.button(f"Trocar ⇄ {label}", key=f"swap__{membro}__{s['trocar_com']}__{idx_tr}"):
                                apply_swap_session(membro, s["trocar_com"], s["grupo_destino"])

        st.divider()

        # Banco de removidos
        st.subheader("🗃️ Banco de removidos")
        if not st.session_state["removidos"]:
            st.caption("Nenhum aluno removido.")
        else:
            c1,c2,c3 = st.columns([0.4,0.3,0.3])
            with c1:
                aluno_rec = st.selectbox("Aluno", options=st.session_state["removidos"], key="recolocar_nome")
            with c2:
                gid = st.selectbox("Recolocar no grupo",
                                   options=[g["Grupo"] for g in grupos],
                                   format_func=lambda x: f"Grupo {x}",
                                   key="recolocar_gid")
            with c3:
                if st.button("Recolocar"):
                    apply_move_session(aluno_rec, gid)

        st.divider()

        # Troca manual
        st.subheader("🔁 Troca manual 1–1")
        todos_membros = [m for g in grupos for m in g["Membros"]]
        c1,c2,c3 = st.columns([0.4,0.3,0.3])
        with c1: aA = st.selectbox("Aluno A", options=sorted(todos_membros), key="swap_a")
        with c2: gB = st.selectbox("Grupo do Aluno B",
                                   options=[g["Grupo"] for g in grupos],
                                   format_func=lambda x: f"Grupo {x}", key="swap_b_gid")
        with c3:
            membros_b = next((sorted(g["Membros"]) for g in grupos if g["Grupo"]==gB), [])
            aB = st.selectbox("Aluno B", options=membros_b, key="swap_b")
        if st.button("Executar troca A ⇄ B"):
            apply_swap_session(aA, aB, gB)

        st.divider()

        # Exportação
        st.subheader("📤 Exportar")
        df_export = grupos_para_dataframe(grupos)
        c1,c2 = st.columns(2)
        with c1:
            st.download_button("Baixar CSV",
                               data=df_export.to_csv(index=False).encode("utf-8"),
                               file_name="grupos.csv", mime="text/csv")
        with c2:
            try:
                pdf_bytes = montar_pdf_grupos(grupos)
                st.download_button("Baixar PDF", data=pdf_bytes,
                                   file_name="grupos.pdf", mime="application/pdf")
            except Exception:
                with st.expander("Como habilitar PDF (ReportLab)"):
                    st.info("Instale no mesmo ambiente:\n\n```bash\npython -m pip install reportlab\n```")

# ----- Tab 2
with tab2:
    if base is None:
        st.error("Sem base de dados. Adicione os arquivos PDF e aperte em processar.")
    else:
        alunos = sorted(base["aluno"].unique())
        horarios = sorted(base["horario"].unique())
        dias = ["Seg","Ter","Qua","Qui","Sex","Sab"]

        selec = st.multiselect("Selecione um ou mais alunos para ver a disponibilidade:",
                               options=alunos, key="tab1_select")
        if not selec:
            st.info("Por favor, selecione pelo menos um aluno para começar.")
        elif len(selec)==1:
            a = selec[0]
            piv = base[base.aluno==a].pivot_table(index="horario", columns="dia",
                                                  values="materia", aggfunc="first")
            grid = (piv.notna() & (piv!='---')).reindex(index=horarios, columns=dias, fill_value=False)
            criar_grid_visual(grid, f"Grade de Horários de {a}")
        else:
            grid = pd.DataFrame(False, index=horarios, columns=dias)
            for a in selec:
                df_a = base[base.aluno==a]
                if df_a.empty: continue
                piv = df_a.pivot_table(index="horario", columns="dia", values="materia", aggfunc="first")
                grid |= (piv.notna() & (piv!='---')).reindex(index=horarios, columns=dias, fill_value=False)
            criar_grid_visual(grid, f"Disponibilidade Combinada ({len(selec)} alunos)")


# ----- Tab 3
with tab3:
    if base is None:
        st.error("Sem base de dados. Adicione os arquivos PDF e aperte em processar.")
    else:
        visualizar_agenda_geral_completa(base)

# --- NOVA ABA: RELATÓRIO E VISUALIZAÇÃO DE RESULTADOS ---
with tab4:
    st.header("📊 Relatório e Análise de Grupos")
    
    res = st.session_state.get("grupos_result")
    if not res:
        st.info("Gere os grupos na aba 'Cruzamento de Grupo' primeiro para ver o relatório.")
    else:
        grupos = res["grupos"]
        base_alunos = base["aluno"].unique()
        
        # --- ESTATÍSTICAS GERAIS ---
        st.subheader("📈 Estatísticas Gerais")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Total de alunos únicos na base
        total_alunos_base = len(base_alunos)
        
        # Alocados nos grupos
        alunos_alocados = [m for g in grupos for m in g["Membros"]]
        total_alocados = len(alunos_alocados)
        percentual_alocados = (total_alocados / total_alunos_base * 100) if total_alunos_base > 0 else 0
        
        with col1:
            st.metric("Total de Alunos", total_alunos_base)
        with col2:
            st.metric("Alunos Alocados", total_alocados)
        with col3:
            st.metric("Taxa de Alocação", f"{percentual_alocados:.1f}%")
        with col4:
            st.metric("Grupos Formados", len(grupos))
        
        # --- DISTRIBUIÇÃO DETALHADA POR GRUPO ---
        st.subheader("👥 Distribuição por Grupo")
    






        
        # Criar tabela detalhada
        dados_grupos = []
        for g in grupos:
            dados_grupos.append({
                "Grupo": g["Grupo"],
                "Dia": g["Dia"],
                "Horário": g["Horário"],
                "Total Alunos": len(g["Membros"]),
                "Membros": ", ".join(sorted(g["Membros"]))
            })
        
        df_grupos = pd.DataFrame(dados_grupos)
        st.dataframe(df_grupos[["Grupo", "Dia", "Horário", "Total Alunos", "Membros"]], 
                    width="stretch",
                    height=min(400, 50 * len(df_grupos) + 50))

    




        
        # --- ALUNOS NÃO ALOCADOS ---
        alunos_nao_alocados = [a for a in base_alunos if a not in alunos_alocados]
        if alunos_nao_alocados:
            st.subheader("⚠️ Alunos Não Alocados")
            st.warning(f"{len(alunos_nao_alocados)} alunos não foram alocados em grupos:")
            
            cols = st.columns(2)
            for i, aluno in enumerate(sorted(alunos_nao_alocados)):
                cols[i % 2].write(f"• {aluno}")
        
        # --- ESTATÍSTICAS DE DISPONIBILIDADE ---
        # --- ESTATÍSTICAS DE DISPONIBILIDADE ---
        st.subheader("⏰ Ranking de Disponibilidade")

        # Calcular disponibilidade por aluno
        disponibilidade_alunos = []
        for aluno in base_alunos:
            df_aluno = base[base.aluno == aluno]
            total_horarios = len(base["horario"].unique()) * len(base["dia"].unique())
            horarios_ocupados = len(df_aluno[df_aluno.materia != '---'])
            horarios_livres = total_horarios - horarios_ocupados
            percentual_livre = (horarios_livres / total_horarios * 100) if total_horarios > 0 else 0
            
            disponibilidade_alunos.append({
                "Aluno": aluno,
                "Horários Livres": horarios_livres,
                "Horários Ocupados": horarios_ocupados,
                "% Livre": percentual_livre
            })

        df_disponibilidade = pd.DataFrame(disponibilidade_alunos)

        # Ordenar por disponibilidade (do maior para o menor)
        df_disponibilidade_ordenado = df_disponibilidade.sort_values("Horários Livres", ascending=False)

        # Dividir na metade exata
        total_alunos = len(base_alunos)
        metade = total_alunos // 2  # Divisão inteira

        # Primeira metade: mais disponíveis
        mais_disponiveis = df_disponibilidade_ordenado.head(metade)

        # Segunda metade: menos disponíveis (inverter ordem para mostrar do pior para o melhor)
        menos_disponiveis = df_disponibilidade_ordenado.tail(total_alunos - metade).iloc[::-1]

        col_top1, col_top2 = st.columns(2)

        with col_top1:
            st.write(f"**🏆 Mais Disponíveis ({len(mais_disponiveis)} alunos)**")
            st.dataframe(mais_disponiveis[["Aluno", "Horários Livres", "% Livre"]]
                        .style.format({"% Livre": "{:.1f}%"}), 
                        width="stretch", hide_index=True)

        with col_top2:
            st.write(f"**⏳ Menos Disponíveis ({len(menos_disponiveis)} alunos)**")
            st.dataframe(menos_disponiveis[["Aluno", "Horários Livres", "% Livre"]]
                        .style.format({"% Livre": "{:.1f}%"}), 
                        width="stretch", hide_index=True)

        # Mostrar estatísticas
        st.write(f"** Total de alunos no sistema: {total_alunos}**")
        st.write(f"** Divisão: {len(mais_disponiveis)} mais disponíveis vs {len(menos_disponiveis)} menos disponíveis**")
        
        # --- VISUALIZAÇÃO DE GRADES POR GRUPO ---
        st.subheader("👥 Visualização de Grades por Grupo")
        
        grupo_selecionado = st.selectbox(
            "Selecione um grupo para ver a grade combinada:",
            options=[g["Grupo"] for g in grupos],
            format_func=lambda x: f"Grupo {x} - {next(g['Dia'] for g in grupos if g['Grupo'] == x)} {next(g['Horário'] for g in grupos if g['Grupo'] == x)}"
        )
        
        if grupo_selecionado:
            grupo = next(g for g in grupos if g["Grupo"] == grupo_selecionado)
            membros_grupo = grupo["Membros"]
            
            st.write(f"**Membros do Grupo {grupo_selecionado}:**")
            for membro in sorted(membros_grupo):
                st.write(f"• {membro}")
            
            # Criar grade combinada do grupo
            if membros_grupo:
                horarios = sorted(base["horario"].unique())
                dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
                
                # Grade combinada (TRUE se pelo menos um membro está indisponível)
                grid_combinada = pd.DataFrame(False, index=horarios, columns=dias)
                
                for membro in membros_grupo:
                    df_membro = base[base.aluno == membro]
                    if not df_membro.empty:
                        piv = df_membro.pivot_table(index="horario", columns="dia", 
                                                  values="materia", aggfunc="first")
                        grid_membro = (piv.notna() & (piv != '---')).reindex(
                            index=horarios, columns=dias, fill_value=False)
                        grid_combinada |= grid_membro
                
                # Visualizar grade combinada
                st.write(f"**Grade Combinada do Grupo {grupo_selecionado}:**")
                criar_grid_visual(grid_combinada, f"Disponibilidade Combinada - Grupo {grupo_selecionado}")
                
                # Horário do grupo
                dia_grupo = grupo["Dia"]
                horario_grupo = grupo["Horário"]
                
                # Verificar se o horário do grupo é viável
                if dia_grupo in dias and horario_grupo in horarios:
                    grupo_disponivel = not grid_combinada.loc[horario_grupo, dia_grupo]
                    
                    if grupo_disponivel:
                        st.success("✅ O horário deste grupo é viável para todos os membros!")
                    else:
                        st.error("❌ Conflito de horário: algum membro não está disponível no horário do grupo!")
            else:
                st.info("Este grupo não possui membros.")
        
        # --- BOTÃO DE EXPORTAÇÃO DO RELATÓRIO ---
        st.divider()
        st.subheader("📤 Exportar Relatório Completo")
        
        # Preparar dados para exportação
        @st.cache_data
        def exportar_relatorio_completo(grupos, df_disponibilidade, alunos_nao_alocados):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Grupos
                df_grupos.to_excel(writer, sheet_name='Grupos', index=False)
                
                # Sheet 2: Disponibilidade
                df_disponibilidade.sort_values("Horários Livres", ascending=False).to_excel(
                    writer, sheet_name='Disponibilidade', index=False)
                
                # Sheet 3: Não Alocados
                pd.DataFrame({"Alunos Não Alocados": sorted(alunos_nao_alocados)}).to_excel(
                    writer, sheet_name='Não_Alocados', index=False)
            
            output.seek(0)
            return output.getvalue()
        
        excel_data = exportar_relatorio_completo(grupos, df_disponibilidade, alunos_nao_alocados)
        st.download_button(
            label="📊 Baixar Relatório Completo (Excel)",
            data=excel_data,
            file_name="relatorio_grupos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )