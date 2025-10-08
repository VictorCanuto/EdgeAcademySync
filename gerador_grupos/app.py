import os
import pickle
import json
from flask import (Flask, request, render_template, session, redirect, url_for, flash, send_file, render_template_string)
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
import uuid
from functools import wraps
import secrets
import string
import shutil 

# --- Gerenciamento de Usuários (Arquivo JSON) ---
USERS_FILE = 'users.json'

def load_users():
    """Carrega os usuários do arquivo JSON. Se o arquivo não existir, retorna um dicionário vazio."""
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users_data):
    """Salva o dicionário de usuários no arquivo JSON."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

from services.pdf_parser import processar_pdfs_para_dataframe
from services.group_generator import formar_grupos
from services.group_manager import sugerir_trocas, executar_troca
from services.analytics_manager import calcular_ranking_disponibilidade

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from werkzeug.security import check_password_hash, generate_password_hash

template_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(template_dir, 'templates'),
            static_folder=os.path.join(template_dir, 'static'))

app.config['SECRET_KEY'] = 'ACADEMYSYNC_KEY'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_DATA_FOLDER'] = 'session_data'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_DATA_FOLDER'], exist_ok=True)

# --- Funções de Autenticação e Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_user_data_folder():
    """Retorna o caminho para a pasta de dados do usuário logado."""
    if 'username' in session:
        user_folder = os.path.join(app.config['SESSION_DATA_FOLDER'], session['username'])
        os.makedirs(user_folder, exist_ok=True)
        return user_folder
    return None

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

# --- Rotas de Autenticação ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()

        if username in users:
            flash('Este nome de usuário já existe.', 'danger')
            return redirect(url_for('register'))

        # Salva a senha criptografada dentro de um dicionário
        hashed_password = generate_password_hash(password)
        users[username] = {'password': hashed_password} 
        save_users(users)

        flash('Conta criada com sucesso! Faça o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users_data = load_users()

        if username in users_data and check_password_hash(users_data[username]['password'], password):
            # Define a sessão para o usuário logado
            session['username'] = username

            try:
                # Pega a pasta de uploads do usuário
                user_uploads_folder = get_user_data_folder()
                
                if os.path.exists(user_uploads_folder):
                    # Lista tudo que está dentro da pasta
                    for filename in os.listdir(user_uploads_folder):
                        file_path = os.path.join(user_uploads_folder, filename)
                        
                        # Remove o item, seja ele um arquivo ou uma pasta
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                            
            except Exception as e:
                # Se a limpeza falhar, apenas avisa no console, mas não impede o login
                print(f"AVISO: Falha ao limpar a pasta de uploads para '{username}'. Erro: {e}")

            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'error')
            
    return render_template('login.html')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    username = session.get('username')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if new_password != confirm_password:
        flash('A nova senha e a confirmação não correspondem.', 'danger')
        return redirect(url_for('index'))

    users = load_users()
    user_data = users.get(username)

    if user_data and check_password_hash(user_data['password'], current_password):
        hashed_new_password = generate_password_hash(new_password)
        users[username]['password'] = hashed_new_password 
        save_users(users)
        flash('Senha alterada com sucesso!', 'success')
    else:
        flash('A senha atual está incorreta.', 'danger')

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    try:
        # Verifica se o usuário estava logado e se um arquivo CSV foi gerado
        if 'username' in session and 'base_data_filename' in session:
            
            user_data_folder = get_user_data_folder()
            filename_to_delete = session.get('base_data_filename')

            if user_data_folder and filename_to_delete:
                filepath = os.path.join(user_data_folder, filename_to_delete)
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
    except Exception as e:
        # Imprime um erro no console do servidor se a limpeza falhar, mas não impede o logout
        print(f"AVISO: Não foi possível remover o arquivo de sessão. Erro: {e}")

    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# --- ROTA PARA ESQUECI A SENHA ---
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        users = load_users()

        if username in users:
            # Gera uma nova senha aleatória
            new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
            
            # SALVA a nova senha de forma segura
            hashed_new_password = generate_password_hash(new_password)
            users[username]['password'] = hashed_new_password
            save_users(users)

            flash(f'Sua nova senha é: {new_password}. Anote-a e faça o login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Usuário não encontrado.', 'danger')
    
    return render_template('forgot_password.html')

# --- Rotas Principais ---
@app.route('/', methods=['GET', 'POST'])
@login_required # Este decorator FORÇA o login para acessar a esta página
def index():
    user_data_folder = get_user_data_folder()
    if not user_data_folder:
        return redirect(url_for('login'))
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'process_pdfs':
            files = request.files.getlist('pdf_files')
            if not files or files[0].filename == '':
                flash('Nenhum arquivo selecionado.', 'error')
                return redirect(request.url)

            filepaths = []
            upload_folder_user = os.path.join(user_data_folder, 'uploads')
            os.makedirs(upload_folder_user, exist_ok=True)

            for file in files:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                filepaths.append(filepath)
            
            base_df = processar_pdfs_para_dataframe(filepaths)
    
            if base_df is not None and not base_df.empty:
                session_filename = f"{uuid.uuid4()}.csv"
                session_filepath = os.path.join(user_data_folder, session_filename)
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
            
            data_filepath = os.path.join(user_data_folder, data_filename)
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
            result_filepath = os.path.join(user_data_folder, result_filename)
            with open(result_filepath, 'wb') as f:
                pickle.dump(result, f)
            
            session['groups_result_filename'] = result_filename
            flash('Grupos gerados com sucesso!', 'success')
            
            return redirect(url_for('index'))

    # --- LÓGICA GET ---
    base_data_info, groups_result, ranking_data = None, None, None
    data_filename = session.get('base_data_filename')
    if data_filename:
        filepath = os.path.join(user_data_folder, data_filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            alunos = sorted([str(a).replace('_', ' ') for a in df['aluno'].unique()])
            base_data_info = {"alunos": len(alunos), "dias": len(df['dia'].unique()), "horarios": len(df['horario'].unique()), "lista_alunos": alunos}
            ranking_data = calcular_ranking_disponibilidade(df.copy())

    result_filename = session.get('groups_result_filename')
    if result_filename:
        filepath = os.path.join(user_data_folder, result_filename)
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
    user_data_folder = get_user_data_folder()
    result_filename = session.get('groups_result_filename')
    
    if not result_filename:
        flash('Sessão expirada ou dados não encontrados. Por favor, gere os grupos novamente.', 'error')
        return redirect(url_for('index'))

    filepath = os.path.join(user_data_folder, result_filename)
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
@login_required 
def clear_session():
    user_data_folder = get_user_data_folder()
    if user_data_folder and os.path.exists(user_data_folder):
        shutil.rmtree(user_data_folder)
    session.pop('base_data_filename', None)
    session.pop('groups_result_filename', None)
    
    flash('Os dados dos PDFs foram limpos com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/download/csv')
def download_csv():
    user_data_folder = get_user_data_folder()
    result_filename = session.get('groups_result_filename')
    if not result_filename: return "Nenhum grupo gerado.", 404
    filepath = os.path.join(user_data_folder, result_filename)
    with open(filepath, 'rb') as f:
        result = pickle.load(f)
    df = grupos_para_dataframe(result['grupos'])
    buffer = BytesIO(df.to_csv(index=False, encoding='utf-8').encode())
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name='grupos.csv')

@app.route('/download/pdf')
def download_pdf():
    user_data_folder = get_user_data_folder()
    result_filename = session.get('groups_result_filename')
    if not result_filename: return "Nenhum grupo gerado.", 404
    filepath = os.path.join(user_data_folder, result_filename)
    with open(filepath, 'rb') as f:
        result = pickle.load(f)
    pdf_buffer = montar_pdf_grupos(result['grupos'])
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='grupos.pdf')

@app.route('/aluno/<nome_aluno>')
def get_aluno_schedule(nome_aluno):
    user_data_folder = get_user_data_folder()
    data_filename = session.get('base_data_filename')
    if not data_filename:
        return render_template_string("<h3>Erro</h3><p>Dados não encontrados na sessão.</p>"), 404

    filepath = os.path.join(user_data_folder, data_filename)
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