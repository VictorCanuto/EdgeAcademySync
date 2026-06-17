import os
import sys
import pickle
from io import BytesIO
import shutil

# Adiciona o diretório gerador_grupos ao PATH com prioridade para evitar importar o app.py do Streamlit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gerador_grupos'))

from app import app, db, User

def test_flow():
    print("Iniciando testes de integração da aplicação...")
    
    # Usar o test_client do Flask
    client = app.test_client()
    
    # 1. Testar Registro de Usuário
    username = "test_user_e2e"
    email = "test_user_e2e@example.com"
    password = "securepassword"
    
    # Limpar qualquer resquício de teste anterior
    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()
            print(f"Usuário antigo '{username}' removido para reiniciar testes.")

    # Cadastrar novo usuário
    response = client.post('/register', data={
        'username': username,
        'email': email,
        'password': password,
        'security_question': 'Qual a sua cidade natal?',
        'security_answer': 'São Paulo'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user is not None, "Usuário não foi cadastrado com sucesso"
    print("[OK] Registro de usuario testado com sucesso.")
    
    # 2. Testar Login
    response = client.post('/login', data={
        'username_or_email': username,
        'password': password
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('username') == username, "Login falhou (username não está na sessão)"
    print("[OK] Login do usuario realizado com sucesso.")

    # 3. Testar Upload de PDFs
    # Vamos pegar 3 arquivos do diretório pdfs
    pdf_dir = os.path.join(os.path.dirname(__file__), 'pdfs')
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')][:3]
    
    if not pdf_files:
        print("Erro: Nenhum arquivo PDF encontrado na pasta pdfs para teste.")
        return
        
    upload_data = {}
    file_handlers = []
    
    for i, filename in enumerate(pdf_files):
        filepath = os.path.join(pdf_dir, filename)
        f = open(filepath, 'rb')
        file_handlers.append(f)
        upload_data[f'pdf_files'] = (f, filename)
        
    # Adicionar o campo action do formulário
    upload_data['action'] = 'process_pdfs'
    
    print(f"Enviando {len(pdf_files)} PDFs para processamento...")
    response = client.post('/', data=upload_data, content_type='multipart/form-data', follow_redirects=True)
    
    # Fechar handlers
    for f in file_handlers:
        f.close()
        
    assert response.status_code == 200
    print("[OK] Upload e processamento de PDFs concluido.")
    
    # Verificar se os dados foram salvos no Neon DB
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user.base_data is not None
        print(f"[OK] Confirmado: Dados consolidados salvos no Banco de Dados (Tamanho: {len(user.base_data)} bytes).")

    # 4. Testar Geração de Grupos
    # Enviar a requisição POST com 2 blocos de horário para gerar exatamente 2 grupos
    group_data = {
        'action': 'generate_groups',
        'bloco_nome[]': ['Manhã', 'Tarde'],
        'bloco_inicio[]': ['8', '14'],
        'bloco_fim[]': ['12', '18'],
        'bloco_dias[]': ['Seg', 'Seg']
    }
    
    print("Gerando grupos de turmas...")
    response = client.post('/', data=group_data, follow_redirects=True)
    
    assert response.status_code == 200
    print("[OK] Logica de geracao de grupos executada.")
    
    # Verificar se o Pickle do resultado foi salvo no Neon DB
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user.groups_result is not None
        result = pickle.loads(user.groups_result)
        print(f"[OK] Confirmado: Grupos persistidos no Banco de Dados.")
        print(f"  Turmas Geradas:")
        for g in result.get('grupos', []):
            membros = [m.get('nome') if isinstance(m, dict) else str(m) for m in g.get('Membros', [])]
            print(f"    - Grupo {g.get('Grupo')} ({g.get('Dia')} {g.get('Horário')}): {', '.join(membros)}")

    # 5. Testar download dos resultados
    response = client.get('/download/csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    print("[OK] Download do CSV gerado com sucesso.")

    response = client.get('/download/pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    print("[OK] Download do PDF gerado com sucesso.")

    # 6. Limpeza do usuário de teste
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            print("[OK] Usuario de testes limpo do banco de dados com sucesso.")
            
    print("\n[SUCCESS] TODOS OS TESTES PASSARAM COM SUCESSO!")

if __name__ == '__main__':
    test_flow()
