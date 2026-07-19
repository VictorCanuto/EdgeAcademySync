from extensions import db

# Modelo de Usuário
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    security_question = db.Column(db.String(256), nullable=True)
    security_answer_hash = db.Column(db.String(256), nullable=True)
    
    # Armazenamento em banco de dados para evitar perda de dados por discos efêmeros
    base_data = db.Column(db.LargeBinary, nullable=True)      # Conteúdo do CSV consolidado
    groups_result = db.Column(db.LargeBinary, nullable=True)  # Dicionário do Pickle serializado
