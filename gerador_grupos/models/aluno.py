from extensions import db

# Modelo de Aluno
class Aluno(db.Model):
    __tablename__ = 'alunos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    nome_custom = db.Column(db.String(120), nullable=True)
    matricula = db.Column(db.String(50), nullable=True)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupos.id'), nullable=True)
    
    turma = db.relationship('Turma', backref=db.backref('alunos', lazy=True, cascade="all, delete-orphan"))
    grupo = db.relationship('Grupo', backref=db.backref('alunos', lazy=True))