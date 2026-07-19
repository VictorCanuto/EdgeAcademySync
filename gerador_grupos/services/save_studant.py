import pandas as pd
from models.aluno import Aluno
from extensions import db


def save_studant(df: pd.DataFrame, turma_id: int):
    if df is None or df.empty or 'aluno' not in df.columns:
        return

    agg = {'matricula': 'first'} if 'matricula' in df.columns else {}
    studants = df.groupby('aluno').agg(agg).reset_index() if agg else df[['aluno']].drop_duplicates()

    existentes = {
        (a.nome, a.matricula)
        for a in Aluno.query.all()
    }

    for _, row in studants.iterrows():
        nome = row['aluno']

        matricula = None
        if 'matricula' in row.index:
            val = str(row['matricula']).strip()
            if val and val.lower() not in ('nan', 'none'):
                matricula = val

        chave = (nome, matricula)
        if chave in existentes:
            continue

        db.session.add(Aluno(
            nome=nome,
            nome_custom=str(nome).replace('_', ' '),
            matricula=matricula,
            turma_id=turma_id,
        ))
        existentes.add(chave)

    db.session.commit()
