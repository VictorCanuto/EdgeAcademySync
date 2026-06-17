import os
import sys
import pickle
from io import BytesIO
import shutil

# Adiciona o diretório gerador_grupos ao PATH com prioridade para evitar importar o app.py do Streamlit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gerador_grupos'))

from app import app, db, User, Turma

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

    # Cadastrar novo usuário com senhas diferentes (deve falhar)
    response_mismatch = client.post('/register', data={
        'username': username + "_fail",
        'email': "fail_" + email,
        'password': password,
        'confirm_password': password + "_mismatch",
        'security_question': 'Qual a sua cidade natal?',
        'security_answer': 'São Paulo'
    }, follow_redirects=True)
    
    assert response_mismatch.status_code == 200
    with app.app_context():
        failed_user = User.query.filter_by(username=username + "_fail").first()
        assert failed_user is None, "Usuário com senhas incompatíveis foi incorretamente cadastrado"
    print("[OK] Teste de impedimento de senhas incompatíveis passou com sucesso.")

    # Cadastrar novo usuário com senhas iguais (deve ter sucesso)
    response = client.post('/register', data={
        'username': username,
        'email': email,
        'password': password,
        'confirm_password': password,
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
    # 2.5 Criar uma Turma de teste
    response = client.post('/', data={
        'action': 'create_turma',
        'turma_nome': 'Turma Teste E2E'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        turma = Turma.query.filter_by(nome='Turma Teste E2E', user_id=user.id).first()
        assert turma is not None, "Turma não foi criada com sucesso"
        turma_id = turma.id
    print("[OK] Criação de turma testada com sucesso.")

    # 2.6 Testar Edição de Nome da Turma
    response = client.post('/', data={
        'action': 'edit_turma',
        'turma_id': str(turma_id),
        'turma_nome': 'Turma Teste E2E Alterada'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        # Using Session.get instead of Query.get to satisfy the SQLAlchemy warning
        from sqlalchemy import inspect
        turma = db.session.get(Turma, turma_id)
        assert turma.nome == 'Turma Teste E2E Alterada', "Nome da turma não foi editado com sucesso"
    print("[OK] Edição de nome de turma testada com sucesso.")

    # Voltar ao nome original
    response = client.post('/', data={
        'action': 'edit_turma',
        'turma_id': str(turma_id),
        'turma_nome': 'Turma Teste E2E'
    }, follow_redirects=True)
    assert response.status_code == 200


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
    response = client.post(f'/turma/{turma_id}', data=upload_data, content_type='multipart/form-data', follow_redirects=True)
    
    # Fechar handlers
    for f in file_handlers:
        f.close()
        
    assert response.status_code == 200
    print("[OK] Upload e processamento de PDFs concluido.")
    
    # Verificar se os dados foram salvos na Turma
    with app.app_context():
        turma = db.session.get(Turma, turma_id)
        assert turma.base_data is not None
        print(f"[OK] Confirmado: Dados consolidados salvos no Banco de Dados da Turma (Tamanho: {len(turma.base_data)} bytes).")

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
    response = client.post(f'/turma/{turma_id}', data=group_data, follow_redirects=True)
    
    assert response.status_code == 200
    print("[OK] Logica de geracao de grupos executada.")
    
    # Verificar se o Pickle do resultado foi salvo na Turma
    with app.app_context():
        turma = db.session.get(Turma, turma_id)
        assert turma.groups_result is not None
        result = pickle.loads(turma.groups_result)
        print(f"[OK] Confirmado: Grupos persistidos no Banco de Dados da Turma.")
        print(f"  Turmas Geradas:")
        for g in result.get('grupos', []):
            membros = [m.get('nome') if isinstance(m, dict) else str(m) for m in g.get('Membros', [])]
            print(f"    - Grupo {g.get('Grupo')} ({g.get('Dia')} {g.get('Horário')}): {', '.join(membros)}")

    # 5. Testar download dos resultados
    response = client.get(f'/download/csv/{turma_id}')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    print("[OK] Download do CSV gerado com sucesso.")

    response = client.get(f'/download/pdf/{turma_id}')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    print("[OK] Download do PDF gerado com sucesso.")

    # 5.5 Testar Exclusão de Turma
    response = client.post('/', data={
        'action': 'delete_turma',
        'turma_id': str(turma_id)
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        turma = db.session.get(Turma, turma_id)
        assert turma is None, "Turma não foi excluída com sucesso"
    print("[OK] Exclusão de turma testada com sucesso.")

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
