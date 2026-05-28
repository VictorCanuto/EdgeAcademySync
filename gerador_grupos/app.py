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
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

import re

from services.pdf_parser import processar_pdfs_para_dataframe
from services.group_generator import formar_grupos, horarios_conflitam
from services.group_manager import sugerir_trocas, executar_troca
from services.analytics_manager import calcular_ranking_disponibilidade

HORARIOS_PADRAO = {
    7: "07:30 - 08:20",
    8: "08:20 - 09:10",
    9: "09:20 - 10:10",
    10: "10:10 - 11:00",
    11: "11:10 - 12:00",
    12: "12:00 - 12:50",
    13: "13:30 - 14:20",
    14: "14:20 - 15:10",
    15: "15:20 - 16:10",
    16: "16:10 - 17:00",
    17: "17:10 - 18:00",
    18: "18:00 - 18:50"
}

def obter_hora_inicio(horario_val):
    if pd.isna(horario_val):
        return None
    try:
        val_str = str(horario_val).strip()
        if ':' in val_str:
            return int(val_str.split(':')[0])
        else:
            return int(float(val_str))
    except (ValueError, TypeError, IndexError):
        return None

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from werkzeug.security import check_password_hash, generate_password_hash

template_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(template_dir, 'templates'),
            static_folder=os.path.join(template_dir, 'static'))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ACADEMYSYNC_KEY')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_DATA_FOLDER'] = 'session_data'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_DATA_FOLDER'], exist_ok=True)

# --- Configuração do Banco de Dados PostgreSQL/SQLite ---
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    # SQLAlchemy exige 'postgresql://' em vez de 'postgres://'
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo de Usuário
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Armazenamento em banco de dados para evitar perda de dados por discos efêmeros
    base_data = db.Column(db.LargeBinary, nullable=True)      # Conteúdo do CSV consolidado
    groups_result = db.Column(db.LargeBinary, nullable=True)  # Dicionário do Pickle serializado

# Inicializa as tabelas do banco de dados se não existirem
with app.app_context():
    db.create_all()

# --- Funções de Autenticação e Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_user_data_folder():
    """Retorna o caminho para a pasta de dados do usuário logado (usado temporariamente para processar uploads)."""
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

# --- Auxiliares de E-mail e Tokens ---
def get_serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'])

def generate_reset_token(email):
    s = get_serializer()
    return s.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=900): # 15 minutos
    s = get_serializer()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=expiration)
        return email
    except (SignatureExpired, BadSignature):
        return None

def enviar_email_recuperacao(email_destino, link_recuperacao):
    mail_server = os.environ.get('MAIL_SERVER')
    mail_port = os.environ.get('MAIL_PORT')
    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_username)
    
    if not all([mail_server, mail_port, mail_username, mail_password]):
        print("AVISO: Configurações de SMTP incompletas. Não foi possível enviar o e-mail de recuperação.")
        return False
        
    msg = EmailMessage()
    msg['Subject'] = 'Recuperação de Senha - AcademySync'
    msg['From'] = mail_sender
    msg['To'] = email_destino
    
    corpo = f"""Olá,

Você solicitou a redefinição de sua senha no AcademySync.
Para redefinir sua senha, clique no link abaixo (válido por 15 minutos):

{link_recuperacao}

Se você não solicitou esta redefinição, por favor ignore este e-mail.

Atenciosamente,
Equipe AcademySync
"""
    msg.set_content(corpo)
    
    try:
        port = int(mail_port)
        if port == 465:
            server = smtplib.SMTP_SSL(mail_server, port)
        else:
            server = smtplib.SMTP(mail_server, port)
            server.starttls()
            
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"ERRO ao enviar e-mail de recuperação para {email_destino}: {e}")
        return False

# --- Rotas de Autenticação ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Este nome de usuário já existe.', 'danger')
            return redirect(url_for('register'))

        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('Este e-mail já está cadastrado.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Conta criada com sucesso! Faça o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
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

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, current_password):
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
    else:
        flash('A senha atual está incorreta.', 'danger')

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_reset_token(user.email)
            link_recuperacao = url_for('reset_password', token=token, _external=True)
            enviado = enviar_email_recuperacao(user.email, link_recuperacao)
            
            if enviado:
                flash('Um link de recuperação foi enviado para o seu e-mail.', 'success')
                return redirect(url_for('login'))
            else:
                if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite') or not os.environ.get('MAIL_SERVER'):
                    flash(f'[DEBUG LOCAL] Erro SMTP ou servidor não configurado. Link de redefinição: {link_recuperacao}', 'warning')
                else:
                    flash('Erro ao enviar e-mail de recuperação. Tente novamente mais tarde.', 'danger')
        else:
            flash('Se o e-mail estiver cadastrado, um link de recuperação será enviado.', 'info')
            return redirect(url_for('login'))
            
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash('O link de recuperação é inválido ou expirou.', 'danger')
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('As senhas não correspondem.', 'danger')
            return render_template('reset_password.html', token=token)
            
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Sua senha foi redefinida com sucesso!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Usuário não encontrado.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('reset_password.html', token=token)


# --- API de Horários para UI/UX Dinâmica ---

@app.route('/aluno/schedules_json')
@login_required
def get_schedules_json():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.base_data:
        return json.dumps({}), 200
        
    try:
        df = pd.read_csv(BytesIO(user.base_data))
        
        # Mapear dias da semana
        dias_completos = {'Seg': 'Segunda', 'Ter': 'Terça', 'Qua': 'Quarta', 'Qui': 'Quinta', 'Sex': 'Sexta', 'Sab': 'Sábado'}
        
        # Estruturar dados por aluno
        schedules = {}
        
        # Inicializar todos os alunos
        alunos_unicos = sorted(df['aluno'].unique())
        for aluno in alunos_unicos:
            nome_limpo = aluno.replace('_', ' ')
            schedules[nome_limpo] = {}
            # Inicializar com free
            for dia in ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']:
                for h in range(7, 23):
                    schedules[nome_limpo][f"{dia}_{h}"] = 'free'
                    
        # Preencher do DataFrame
        for _, row in df.iterrows():
            nome_limpo = str(row['aluno']).replace('_', ' ')
            dia_completo = dias_completos.get(row['dia'], row['dia'])
            
            horario_int = obter_hora_inicio(row['horario'])
            if horario_int is None:
                continue
                
            materia = str(row['materia'])
            
            key = f"{dia_completo}_{horario_int}"
            if nome_limpo in schedules:
                if pd.isna(row['materia']) or materia == '---' or materia.strip() == '':
                    schedules[nome_limpo][key] = 'free'
                elif 'Acompanhamento' in materia or materia == 'P':
                    schedules[nome_limpo][key] = 'follow'
                else:
                    # Qualquer outro texto de matéria indica aula ocupada (X)
                    schedules[nome_limpo][key] = 'class'
                    
        return json.dumps(schedules), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route('/aluno/update_schedule', methods=['POST'])
@login_required
def update_student_schedule():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.base_data:
        return json.dumps({"error": "Dados não encontrados"}), 404
        
    data = request.json
    aluno_nome = data.get('aluno')
    dia = data.get('dia')
    horario = int(data.get('horario'))
    novo_status = data.get('status')
    
    try:
        df = pd.read_csv(BytesIO(user.base_data))
        
        dia_abrev_map = {'Segunda': 'Seg', 'Terça': 'Ter', 'Quarta': 'Qua', 'Quinta': 'Qui', 'Sexta': 'Sex', 'Sábado': 'Sab'}
        dia_abrev = dia_abrev_map.get(dia, dia)
        
        # Filtrar o aluno com tratamento de underline e comparação flexível de horário
        aluno_key = aluno_nome.replace(' ', '_')
        cond_horario = df['horario'].apply(lambda h: obter_hora_inicio(h) == horario)
        condicao = (df['aluno'].str.lower() == aluno_key.lower()) & (df['dia'] == dia_abrev) & cond_horario
        
        materia_val = '---'
        if novo_status == 'class':
            materia_val = 'Aula de Graduação'
        elif novo_status == 'follow':
            materia_val = 'Acompanhamento Individual'
        elif novo_status != 'free':
            materia_val = novo_status # Rótulo customizado
            
        if not df[condicao].empty:
            df.loc[condicao, 'materia'] = materia_val
        else:
            # Caso a célula não exista na base, criar uma nova linha formatada
            horario_salvar = HORARIOS_PADRAO.get(horario, f"{horario:02d}:00 - {horario:02d}:50")
            new_row = pd.DataFrame([{'aluno': aluno_key, 'dia': dia_abrev, 'horario': horario_salvar, 'materia': materia_val}])
            df = pd.concat([df, new_row], ignore_index=True)
            
        # Salvar CSV atualizado
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8')
        user.base_data = csv_buffer.getvalue()
        
        # Se houver grupos formados, atualizar o cache de compatibilidade e detectar conflito
        conflito_gerado = False
        grupo_afetado = None
        
        if user.groups_result:
            result = pickle.loads(user.groups_result)
            slots_por_aluno = result.get('slots_por_aluno', {})
            
            # Recomputar a disponibilidade deste aluno para todos os blocos cadastrados
            slots_por_aluno[aluno_key] = set()
            blocos = result.get('blocos', [])
            
            # Obter as aulas ocupadas do aluno do DataFrame atualizado
            aluno_df = df[df['aluno'].str.lower() == aluno_key.lower()]
            aluno_busy = aluno_df[aluno_df['materia'] != '---']
            
            # Agrupar horários ocupados por dia
            ocupados_dia = {}
            for _, row in aluno_busy.iterrows():
                d_val = str(row['dia'])
                if d_val not in ocupados_dia:
                    ocupados_dia[d_val] = []
                ocupados_dia[d_val].append(row['horario'])
                
            for b in blocos:
                nome_bloco = b.get("nome")
                ini = int(b["inicio"])
                fim = int(b["fim"])
                dias = b.get("dias") or b.get("dia") or []
                if isinstance(dias, str):
                    dias = [d.strip() for d in dias.split(",") if d.strip()]
                label = f"{nome_bloco} ({ini:02d}h-{fim:02d}h)"
                
                for dia in dias:
                    busy_hours = ocupados_dia.get(dia, [])
                    livre = True
                    for h in busy_hours:
                        if horarios_conflitam(h, ini, fim):
                            livre = False
                            break
                    if livre:
                        slots_por_aluno[aluno_key].add((dia, label))
            
            # Encontrar grupo do aluno
            grupos = result.get('grupos', [])
            aluno_grupo = None
            for g in grupos:
                membros_nomes = [_get_nome_membro(m) for m in g.get('Membros', [])]
                if aluno_nome.lower() in [m.lower() for m in membros_nomes]:
                    aluno_grupo = g
                    break
            
            if aluno_grupo and novo_status != 'free':
                g_dia = aluno_grupo.get('Dia')
                g_horario_str = aluno_grupo.get('Horário')
                if g_dia == dia_abrev:
                    try:
                        # Extrai horas usando regex (compatível com os blocos)
                        match = re.search(r'(\d+)h-(\d+)h', g_horario_str)
                        if match:
                            h_inicio = int(match.group(1))
                            h_fim = int(match.group(2))
                        else:
                            h_inicio = int(g_horario_str.split(' - ')[0].split(':')[0])
                            h_fim = int(g_horario_str.split(' - ')[1].split(':')[0])
                        if horario >= h_inicio and horario < h_fim:
                            conflito_gerado = True
                            grupo_afetado = aluno_grupo.get('Grupo')
                    except Exception:
                        pass
            
            result['slots_por_aluno'] = slots_por_aluno
            user.groups_result = pickle.dumps(result)
            
        db.session.commit()
        return json.dumps({
            "success": True,
            "conflito": conflito_gerado,
            "grupo": grupo_afetado
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return json.dumps({"error": str(e)}), 500


# --- Rotas Principais ---
@app.route('/', methods=['GET', 'POST'])
@login_required # Este decorator FORÇA o login para acessar a esta página
def index():
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('login'))
        
    user_data_folder = get_user_data_folder()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'process_pdfs':
            files = request.files.getlist('pdf_files')
            if not files or files[0].filename == '':
                flash('Nenhum arquivo selecionado.', 'error')
                return redirect(request.url)

            filepaths = []
            upload_folder_user = os.path.join(user_data_folder, 'uploads') if user_data_folder else 'uploads'
            os.makedirs(upload_folder_user, exist_ok=True)

            for file in files:
                filename = secure_filename(file.filename)
                filepath = os.path.join(upload_folder_user, filename)
                file.save(filepath)
                filepaths.append(filepath)
            
            base_df = processar_pdfs_para_dataframe(filepaths)
            
            # Limpa os PDFs temporários salvos no disco
            try:
                for fpath in filepaths:
                    if os.path.exists(fpath):
                        os.remove(fpath)
            except Exception as e:
                print(f"AVISO: Falha ao limpar PDFs temporários: {e}")
    
            if base_df is not None and not base_df.empty:
                # Salva o DataFrame no Banco de Dados em formato binário (CSV encoded bytes)
                csv_buffer = BytesIO()
                base_df.to_csv(csv_buffer, index=False, encoding='utf-8')
                user.base_data = csv_buffer.getvalue()
                db.session.commit()
                
                flash(f'{len(base_df["aluno"].unique())} alunos processados com sucesso!', 'success')
            else:
                flash('Não foi possível extrair dados válidos dos PDFs.', 'error')
            
            return redirect(url_for('index'))

        elif action == 'generate_groups':
            if not user.base_data:
                flash('Primeiro processe os arquivos PDF.', 'error')
                return redirect(url_for('index'))
            
            try:
                base_df = pd.read_csv(BytesIO(user.base_data))
            except Exception as e:
                flash('Erro ao ler os dados de alunos salvos no banco. Processe os PDFs novamente.', 'error')
                user.base_data = None
                db.session.commit()
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
            result['blocos'] = blocos
            
            alunos_sem_grupo = result.get('alunos_sem_grupo')
            if alunos_sem_grupo:
                display_limit = 5
                nomes_display = ", ".join(al.replace('_', ' ') for al in alunos_sem_grupo[:display_limit])
                extra_count = len(alunos_sem_grupo) - display_limit
                msg = (f"{len(alunos_sem_grupo)} aluno(s) não foram alocados por conflito de horário: {nomes_display}")
                if extra_count > 0:
                    msg += f" e mais {extra_count}."
                flash(msg, 'warning')

            # Salva o resultado dos grupos no Banco de Dados em formato Pickle binário
            user.groups_result = pickle.dumps(result)
            db.session.commit()
            
            flash('Grupos gerados com sucesso!', 'success')
            return redirect(url_for('index'))

    # --- LÓGICA GET ---
    base_data_info, groups_result, ranking_data = None, None, None
    
    if user.base_data:
        try:
            df = pd.read_csv(BytesIO(user.base_data))
            alunos = sorted([str(a).replace('_', ' ') for a in df['aluno'].unique()])
            base_data_info = {"alunos": len(alunos), "dias": len(df['dia'].unique()), "horarios": len(df['horario'].unique()), "lista_alunos": alunos}
            ranking_data = calcular_ranking_disponibilidade(df.copy())
        except Exception as e:
            print(f"Erro ao ler base_data do banco: {e}")

    if user.groups_result:
        try:
            groups_result = pickle.loads(user.groups_result)
            
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
        except Exception as e:
            print(f"Erro ao carregar groups_result do banco: {e}")

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
@login_required
def trocar_aluno():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.groups_result:
        flash('Dados de grupos não encontrados. Por favor, gere os grupos novamente.', 'error')
        return redirect(url_for('index'))

    try:
        result = pickle.loads(user.groups_result)
    except Exception as e:
        flash('Erro ao carregar os dados dos grupos do banco de dados.', 'error')
        return redirect(url_for('index'))
    
    grupos = result['grupos']
    
    # 2. Obter dados do formulário de forma segura
    aluno_a = request.form.get('aluno_a')
    aluno_b = request.form.get('aluno_b') # Será None no caso de "mover"

    grupo_a_id_str = request.form.get('grupo_a_id')
    grupo_b_id_str = request.form.get('grupo_b_id')

    # Valida e converte os IDs
    grupo_a_id = int(grupo_a_id_str) if grupo_a_id_str else None
    grupo_b_id = int(grupo_b_id_str) if grupo_b_id_str else None

    # Verifica se os dados essenciais estão presentes
    if not aluno_a or not grupo_a_id or (aluno_b and not grupo_b_id) or (not aluno_b and not grupo_b_id):
        flash('Informação incompleta para realizar a movimentação.', 'error')
        return redirect(url_for('index'))

    # 3. Executar a lógica de troca/movimentação
    grupos_modificados = executar_troca(aluno_a, grupo_a_id, grupos, aluno_b, grupo_b_id)
    
    # 4. Salvar os novos dados no banco
    result['grupos'] = grupos_modificados
    user.groups_result = pickle.dumps(result)
    db.session.commit()
        
    if aluno_b:
        flash(f'Troca entre {aluno_a} e {aluno_b} realizada com sucesso!', 'success')
    else:
        flash(f'Aluno {aluno_a} movido para o Grupo {grupo_b_id} com sucesso!', 'success')
        
    return redirect(url_for('index'))

@app.route('/clear')
@login_required 
def clear_session():
    user = User.query.filter_by(username=session['username']).first()
    if user:
        user.base_data = None
        user.groups_result = None
        db.session.commit()
        
    user_data_folder = get_user_data_folder()
    if user_data_folder and os.path.exists(user_data_folder):
        shutil.rmtree(user_data_folder)
    
    flash('Os dados foram limpos com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/download/csv')
@login_required
def download_csv():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.groups_result:
        return "Nenhum grupo gerado.", 404
        
    try:
        result = pickle.loads(user.groups_result)
    except Exception as e:
        return "Erro ao carregar dados do banco.", 500
        
    df = grupos_para_dataframe(result['grupos'])
    buffer = BytesIO(df.to_csv(index=False, encoding='utf-8').encode())
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name='grupos.csv')

@app.route('/download/pdf')
@login_required
def download_pdf():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.groups_result:
        return "Nenhum grupo gerado.", 404
        
    try:
        result = pickle.loads(user.groups_result)
    except Exception as e:
        return "Erro ao carregar dados do banco.", 500
        
    pdf_buffer = montar_pdf_grupos(result['grupos'])
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='grupos.pdf')

@app.route('/aluno/<nome_aluno>')
@login_required
def get_aluno_schedule(nome_aluno):
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.base_data:
        return render_template_string("<h3>Erro</h3><p>Dados não encontrados no banco.</p>"), 404

    try:
        df = pd.read_csv(BytesIO(user.base_data))
    except Exception as e:
        return render_template_string("<h3>Erro</h3><p>Erro ao ler dados do banco.</p>"), 500
    
    # Comparar o nome da URL (com espaços) com a coluna do df
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
    
    for dia_abrev in dias_map.keys():
        if dia_abrev not in schedule_pivot.columns:
            schedule_pivot[dia_abrev] = '---'
            
    schedule_pivot.rename(columns=dias_map, inplace=True)
    schedule_pivot = schedule_pivot[list(dias_map.values())]

    return render_template("_aluno_schedule.html", aluno=nome_aluno, schedule=schedule_pivot)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
