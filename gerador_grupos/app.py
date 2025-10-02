import os
import pickle
from flask import Flask, request, render_template, session, redirect, url_for, flash, send_file
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

app = Flask(__name__)
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

def _get_nome_membro(membro):
    return membro.get('nome') if isinstance(membro, dict) else str(membro)

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

            filepaths = [os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)) for f in files]
            for file, path in zip(files, filepaths):
                file.save(path)

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
            blocos = []
            form_input_blocos = []
            for i in range(5):
                nome = request.form.get(f'bloco_{i}_nome')
                inicio = request.form.get(f'bloco_{i}_inicio')
                fim = request.form.get(f'bloco_{i}_fim')
                dias_str = request.form.get(f'bloco_{i}_dias')
                form_input_blocos.append({'nome': nome, 'inicio': inicio, 'fim': fim, 'dias': dias_str})
                if nome and inicio and fim and dias_str:
                    try:
                        blocos.append({
                            "nome": nome, "inicio": int(inicio), "fim": int(fim),
                            "dias": [d.strip().title() for d in dias_str.split(',')]
                        })
                    except (ValueError, TypeError): continue
            
            session['form_input'] = {'num_grupos': num_grupos, 'blocos': form_input_blocos}
            if not blocos:
                flash('Pelo menos um bloco de horário válido é necessário.', 'error')
                return redirect(url_for('index'))

            result = formar_grupos(base_df, num_grupos=num_grupos, blocos=blocos)
            
            result_filename = f"{uuid.uuid4()}.pkl"
            result_filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
            with open(result_filepath, 'wb') as f:
                pickle.dump(result, f)
            
            session['groups_result_filename'] = result_filename
            flash('Grupos gerados com sucesso!', 'success')
            
            return redirect(url_for('index'))

    base_data_info = None
    groups_result = None
    ranking_data = None

    data_filename = session.get('base_data_filename')
    if data_filename:
        filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], data_filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            alunos = sorted(df['aluno'].unique())
            base_data_info = {
                "alunos": len(alunos),
                "dias": len(df['dia'].unique()),
                "horarios": len(df['horario'].unique()),
                "lista_alunos": alunos
            }
            ranking_data = calcular_ranking_disponibilidade(df)

    result_filename = session.get('groups_result_filename')
    if result_filename:
        filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                groups_result = pickle.load(f)
            
            for group in groups_result['grupos']:
                membros_com_sugestoes = []
                for membro in group['Membros']:
                    sugs = sugerir_trocas(membro, groups_result['grupos'], groups_result['slots_por_aluno'])
                    membros_com_sugestoes.append({'nome': membro, 'sugestoes': sugs})
                group['Membros'] = membros_com_sugestoes

    return render_template('index.html', base_data_info=base_data_info, groups_result=groups_result, ranking_data=ranking_data)

@app.route('/trocar', methods=['POST'])
def trocar_aluno():
    result_filename = session.get('groups_result_filename')
    if not result_filename:
        flash('Sessão expirada ou resultado não encontrado.', 'error')
        return redirect(url_for('index'))

    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], result_filename)
    try:
        with open(filepath, 'rb') as f:
            result = pickle.load(f)
    except FileNotFoundError:
        flash('Arquivo de sessão não encontrado. Gere os grupos novamente.', 'error')
        return redirect(url_for('index'))

    aluno_a = request.form.get('aluno_a')
    grupo_a_id = int(request.form.get('grupo_a_id'))
    aluno_b = request.form.get('aluno_b')
    grupo_b_id = int(request.form.get('grupo_b_id'))
    
    grupos_atualizados = executar_troca(result['grupos'], aluno_a, grupo_a_id, aluno_b, grupo_b_id)
    result['grupos'] = grupos_atualizados

    with open(filepath, 'wb') as f:
        pickle.dump(result, f)

    if aluno_b:
        flash(f'Troca entre {aluno_a} e {aluno_b} realizada com sucesso!', 'success')
    else:
        flash(f'{aluno_a} movido para o Grupo {grupo_b_id} com sucesso!', 'success')
        
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
        return "Dados não encontrados.", 404

    filepath = os.path.join(app.config['SESSION_DATA_FOLDER'], data_filename)
    if not os.path.exists(filepath):
        return "Arquivo de dados não encontrado.", 404

    df = pd.read_csv(filepath)
    aluno_df = df[df['aluno'] == nome_aluno]

    if aluno_df.empty:
        return "Aluno não encontrado.", 404

    schedule_pivot = aluno_df.pivot_table(
        index='horario', columns='dia', values='materia',
        aggfunc='first', fill_value='---'
    )

    ordem_dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
    ordem_horarios = sorted(df['horario'].unique())
    schedule_pivot = schedule_pivot.reindex(columns=ordem_dias, index=ordem_horarios, fill_value='---')

    return render_template('_aluno_schedule.html', schedule=schedule_pivot, aluno=nome_aluno)

if __name__ == '__main__':
    app.run(debug=True)