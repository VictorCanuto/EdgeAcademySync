from extensions import db

# Modelo de Grupo
class Grupo(db.Model):
    __tablename__ = 'grupos'
    id = db.Column(db.Integer, primary_key=True)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    dia = db.Column(db.String(120), nullable=False)
    horario = db.Column(db.String(120), nullable=False)
    
    turma = db.relationship('Turma', backref=db.backref('grupos', lazy=True, cascade="all, delete-orphan"))
