from extensions import db

# Modelo de Turma
class Turma(db.Model):
    __tablename__ = 'turmas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    base_data = db.Column(db.LargeBinary, nullable=True)      # Conteúdo do CSV consolidado
    groups_result = db.Column(db.LargeBinary, nullable=True)  # Dicionário do Pickle serializado
    
    em_imersao = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('turmas', lazy=True, cascade="all, delete-orphan"))
