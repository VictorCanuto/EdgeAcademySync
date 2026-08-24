from extensions import db

# Modelo de Horário do Aluno
# Fase 1 da migração "grade/vetor" -> tabela relacional (ver plano de execução).
# Nenhum dado é migrado ainda: esta tabela só é criada vazia via db.create_all().
class HorarioAluno(db.Model):
    __tablename__ = 'horarios_aluno'
    __table_args__ = (
        db.UniqueConstraint('aluno_id', 'dia', 'horario', name='uq_horario_aluno_slot'),
    )

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    dia = db.Column(db.String(10), nullable=False)            # "Seg", "Ter", ...
    horario = db.Column(db.String(20), nullable=False)        # "08:00 - 08:50"
    materia = db.Column(db.String(120), nullable=True, default='---')

    aluno = db.relationship('Aluno', backref=db.backref('horarios', lazy=True, cascade="all, delete-orphan"))
