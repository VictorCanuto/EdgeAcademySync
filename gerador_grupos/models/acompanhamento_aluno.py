from extensions import db

# Modelo de Acompanhamento do Aluno: compromissos administrativos marcados
#
# Tabela separada de horarios_aluno porque representa um tipo de dado
# diferente e facilita modificações futuras
class AcompanhamentoAluno(db.Model):
    __tablename__ = 'acompanhamentos_aluno'
    __table_args__ = (
        db.UniqueConstraint('aluno_id', 'dia', 'horario', name='uq_acompanhamento_aluno_slot'),
    )

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    dia = db.Column(db.String(10), nullable=False)           # "Seg", "Ter", ...
    horario = db.Column(db.String(20), nullable=False)       # "08:00 - 08:30" (slot de 30min da grade)
    tipo = db.Column(db.String(20), nullable=False)          # AC | PSI | AP | REALOCADO | IMERSAO | CUSTOM

    aluno = db.relationship('Aluno', backref=db.backref('acompanhamentos', lazy=True, cascade="all, delete-orphan"))
