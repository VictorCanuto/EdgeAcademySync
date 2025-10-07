import os
import pickle
from flask import (Flask, request, render_template, session, redirect, url_for, flash, send_file, render_template_string)
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
import uuid


from services.pdf_parser import processar_pdfs_para_dataframe
from services.group_generator import formar_grupos
from services.group_manager import sugerir_trocas, executar_troca
from services.analytics_manager import calcular_ranking_disponibilidade

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

template_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(template_dir, 'templates'),
            static_folder=os.path.join(template_dir, 'static'))

app.config['SECRET_KEY'] = 'ACADEMYSYNC_KEY'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_DATA_FOLDER'] = 'session_data'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_DATA_FOLDER'], exist_ok=True)


def grupos_para_dataframe(grupos):
    linhas = []
    for g in grupos:
        membros_nomes = [_get_nome_membro(m) for m in g.get("Membros", [])]
        for m in sorted(membros_nomes):
            linhas.append({"Grupo": g.get("Grupo"), "Dia": g.get("Dia"), "Horário": g.get("Horário"), "Aluno": m})
    return pd.DataFrame(linhas)

def montar_pdf_grupos(grupos):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, altura = A4; margem = 2*cm; y = altura - margem
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margem, y, "Grupos Formados")
    y -= 1.0 * cm
    for g in sorted(grupos, key=lambda x: x.get("Grupo", 0)):
        header = f"Grupo {g.get('Grupo')} — {g.get('Dia')} ({g.get('Horário')})"
        c.setFont("Helvetica-Bold", 11); c.drawString(margem, y, header); y -= 0.6 * cm
        c.setFont("Helvetica", 10)
        membros_nomes = [_get_nome_membro(m) for m in g.get("Membros", [])]
        for m in sorted(membros_nomes):
            c.drawString(margem + 0.5 * cm, y, f"• {m}"); y -= 0.5 * cm
            if y <= margem: c.showPage(); y = altura - margem
        y -= 0.3 * cm
        if y <= margem: c.showPage(); y = altura - margem
    c.save(); buf.seek(0)
    return buf

def _get_nome_membro(membro: any) -> str:
    if isinstance(membro, dict):
        return membro.get('nome', '')
    return str(membro)

# --- Rotas Principais ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'process_pdfs':
            files = request.files.getlist('pdf_files')
            if not files or files[0].filename == '':
                flash('Nenhum arquivo selecionado.', 'error')
                return redirect(request.url)

            filepaths = []
            for file in files:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                filepaths.append(filepath)
            
            base_df = processar_pdfs_para_dataframe(filepaths)
    
            if base_df is not None and not base_df.empty:
                session_filename = f"{uuid.uuid4()}.csv"
                session_filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], session_filename)
                base_df.to_csv(session_filepath, index=False)
                session['base_data_filename'] = session_filename
                flash(f'{len(base_df["aluno"].unique())} alunos processados com sucesso!', 'success')
            else:
                flash('Não foi possível extrair dados válidos dos PDFs.', 'error')
            
            return redirect(url_for('index'))

        elif action == 'generate_groups':
            data_filename = session.get('base_data_filename')
            if not data_filename:
                flash('Primeiro processe os arquivos PDF.', 'error')
                return redirect(url_for('index'))
            
            data_filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], data_filename)
            try:
                base_df = pd.read_csv(data_filepath)
            except FileNotFoundError:
                flash('Arquivo de dados da sessão não encontrado. Processe os PDFs novamente.', 'error')
                session.pop('base_data_filename', None)
                return redirect(url_for('index'))

            num_grupos = int(request.form.get('num_grupos', 3))
            
            # Leitura dos blocos do formulário
            nomes_blocos = request.form.getlist('bloco_nome[]')
            horas_inicio = request.form.getlist('bloco_inicio[]')
            horas_fim = request.form.getlist('bloco_fim[]')
            dias_semana = request.form.getlist('bloco_dias[]')

            blocos = []
            if not all([nomes_blocos, horas_inicio, horas_fim, dias_semana]):
                flash('Erro ao ler os blocos de horário. Tente novamente.', 'error')
                return redirect(url_for('index'))

            for i in range(len(nomes_blocos)):
                try:
                    # O campo de dias agora é um select, então pegamos o valor diretamente
                    dias = [dias_semana[i]] if dias_semana[i] else []
                    
                    bloco = {
                        "nome": nomes_blocos[i],
                        "inicio": int(horas_inicio[i]),
                        "fim": int(horas_fim[i]),
                        "dias": dias
                    }
                    if all(bloco.values()): # Garante que nenhum campo está vazio
                        blocos.append(bloco)
                except (ValueError, IndexError):
                    flash(f'Bloco de horário inválido encontrado. Verifique os dados.', 'warning')
                    continue
            
            if not blocos:
                flash('Pelo menos um bloco de horário válido é necessário.', 'error')
                return redirect(url_for('index'))

            result = formar_grupos(base_df, num_grupos=num_grupos, blocos=blocos)
            
            alunos_sem_grupo = result.get('alunos_sem_grupo')
            if alunos_sem_grupo:
                display_limit = 5
                nomes_display = ", ".join(al.replace('_', ' ') for al in alunos_sem_grupo[:display_limit])
                extra_count = len(alunos_sem_grupo) - display_limit
                msg = (f"{len(alunos_sem_grupo)} aluno(s) não foram alocados por conflito de horário: {nomes_display}")
                if extra_count > 0:
                    msg += f" e mais {extra_count}."
                flash(msg, 'warning')

            result_filename = f"{uuid.uuid4()}.pkl"
            result_filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
            with open(result_filepath, 'wb') as f:
                pickle.dump(result, f)
            
            session['groups_result_filename'] = result_filename
            flash('Grupos gerados com sucesso!', 'success')
            
            return redirect(url_for('index'))

    # --- LÓGICA GET ---
    base_data_info, groups_result, ranking_data = None, None, None
    data_filename = session.get('base_data_filename')
    if data_filename:
        filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], data_filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            alunos = sorted([str(a).replace('_', ' ') for a in df['aluno'].unique()])
            base_data_info = {"alunos": len(alunos), "dias": len(df['dia'].unique()), "horarios": len(df['horario'].unique()), "lista_alunos": alunos}
            ranking_data = calcular_ranking_disponibilidade(df.copy())

    result_filename = session.get('groups_result_filename')
    if result_filename:
        filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                groups_result = pickle.load(f)
            
            grupos_originais = groups_result.get('grupos', [])
            slots_por_aluno = groups_result.get('slots_por_aluno', {})
            grupos_para_template = []
            for group in grupos_originais:
                novo_grupo = group.copy()
                membros_com_sugestoes = []
                for membro_item in group.get('Membros', []):
                    nome_aluno = _get_nome_membro(membro_item)
                    sugs = sugerir_trocas(nome_aluno, grupos_originais, slots_por_aluno)
                    membros_com_sugestoes.append({'nome': nome_aluno.replace('_', ' '), 'sugestoes': sugs})
                novo_grupo['Membros'] = membros_com_sugestoes
                grupos_para_template.append(novo_grupo)
            groups_result['grupos'] = grupos_para_template

    # Listas de opções para os menus de seleção no formulário
    horarios_disponiveis = list(range(7, 23))
    nomes_blocos_opcoes = ["Manhã", "Tarde", "Noite", "Extra"]
    dias_semana_opcoes = [
        {"valor": "Seg", "texto": "Segunda-feira"},
        {"valor": "Ter", "texto": "Terça-feira"},
        {"valor": "Qua", "texto": "Quarta-feira"},
        {"valor": "Qui", "texto": "Quinta-feira"},
        {"valor": "Sex", "texto": "Sexta-feira"},
        {"valor": "Sab", "texto": "Sábado"}
    ]

    return render_template('index.html', 
                           base_data_info=base_data_info, 
                           groups_result=groups_result, 
                           ranking_data=ranking_data,
                           horarios_disponiveis=horarios_disponiveis,
                           nomes_blocos_opcoes=nomes_blocos_opcoes,    
                           dias_semana_opcoes=dias_semana_opcoes)     

@app.route('/trocar_aluno', methods=['POST'])
def trocar_aluno():
    # 1. Carregar dados da sessão
    result_filename = session.get('groups_result_filename')
    
    if not result_filename:
        flash('Sessão expirada ou dados não encontrados. Por favor, gere os grupos novamente.', 'error')
        return redirect(url_for('index'))

    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
    if not os.path.exists(filepath):
        flash('Arquivo de dados da sessão não encontrado. Por favor, gere os grupos novamente.', 'error')
        return redirect(url_for('index'))

    with open(filepath, 'rb') as f:
        result = pickle.load(f)
    
    grupos = result['grupos']
    
    # 2. Obter dados do formulário de forma segura
    aluno_a = request.form.get('aluno_a')
    aluno_b = request.form.get('aluno_b') # Será None no caso de "mover"

    grupo_a_id_str = request.form.get('grupo_a_id')
    grupo_b_id_str = request.form.get('grupo_b_id')

    # Valida e converte os IDs, tratando strings vazias ou None
    grupo_a_id = int(grupo_a_id_str) if grupo_a_id_str else None
    grupo_b_id = int(grupo_b_id_str) if grupo_b_id_str else None

    # Verifica se os dados essenciais estão presentes
    if not aluno_a or not grupo_a_id or (aluno_b and not grupo_b_id) or (not aluno_b and not grupo_b_id):
        flash('Informação incompleta para realizar a movimentação.', 'error')
        return redirect(url_for('index'))

    # 3. Executar a lógica de troca/movimentação
    grupos_modificados = executar_troca(aluno_a, grupo_a_id, grupos, aluno_b, grupo_b_id)
    
    # 4. Salvar os novos dados na sessão
    result['grupos'] = grupos_modificados
    with open(filepath, 'wb') as f:
        pickle.dump(result, f)
        
    # Mensagem de sucesso específica
    if aluno_b:
        flash(f'Troca entre {aluno_a} e {aluno_b} realizada com sucesso!', 'success')
    else:
        flash(f'Aluno {aluno_a} movido para o Grupo {grupo_b_id} com sucesso!', 'success')
        
    return redirect(url_for('index'))

@app.route('/clear')
def clear_session():
    for folder in [app.config['UPLOAD_FOLDER'], app.config['SESSION_DATA_FOLDER']]:
        for filename in os.listdir(folder):
            os.remove(os.path.join(folder, filename))
    session.clear()
    flash('Todos os dados foram limpos.', 'success')
    return redirect(url_for('index'))

@app.route('/download/csv')
def download_csv():
    result_filename = session.get('groups_result_filename')
    if not result_filename: return "Nenhum grupo gerado.", 404
    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
    with open(filepath, 'rb') as f:
        result = pickle.load(f)
    df = grupos_para_dataframe(result['grupos'])
    buffer = BytesIO(df.to_csv(index=False, encoding='utf-8').encode())
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name='grupos.csv')

@app.route('/download/pdf')
def download_pdf():
    result_filename = session.get('groups_result_filename')
    if not result_filename: return "Nenhum grupo gerado.", 404
    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
    with open(filepath, 'rb') as f:
        result = pickle.load(f)
    pdf_buffer = montar_pdf_grupos(result['grupos'])
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='grupos.pdf')

@app.route('/aluno/<nome_aluno>')
def get_aluno_schedule(nome_aluno):
    data_filename = session.get('base_data_filename')
    if not data_filename:
        return render_template_string("<h3>Erro</h3><p>Dados não encontrados na sessão.</p>"), 404

    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], data_filename)
    if not os.path.exists(filepath):
        return render_template_string("<h3>Erro</h3><p>Arquivo de dados da sessão não encontrado.</p>"), 404

    df = pd.read_csv(filepath)
    
    # Comparar o nome da URL (com espaços) com a coluna do df (convertendo '_' para ' ' na hora)
    # Isto garante que a busca sempre funcione, independentemente do formato.
    aluno_df = df[df['aluno'].str.replace('_', ' ').str.lower() == nome_aluno.lower()]

    if aluno_df.empty:
        return render_template_string(f"<h3>Aluno não encontrado</h3><p>O aluno '{nome_aluno}' não foi encontrado nos dados carregados.</p>"), 404
    
    # Pivoting (usando a coluna 'horario')
    schedule_pivot = aluno_df.pivot_table(
        index='horario', 
        columns='dia', 
        values='materia',
        aggfunc='first', 
        fill_value='---'
    ).sort_index()

    # Garantir que os dias da semana sejam exibidos corretamente
    dias_map = {
        'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta',
        'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado'
    }
    
    # Garantir que todas as colunas abreviadas existam
    for dia_abrev in dias_map.keys():
        if dia_abrev not in schedule_pivot.columns:
            schedule_pivot[dia_abrev] = '---'
            
    # Renomear colunas para o nome completo
    schedule_pivot.rename(columns=dias_map, inplace=True)
    
    # Reordenar as colunas pela ordem correta dos dias por extenso
    schedule_pivot = schedule_pivot[list(dias_map.values())]

    return render_template("_aluno_schedule.html", aluno=nome_aluno, schedule=schedule_pivot)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)