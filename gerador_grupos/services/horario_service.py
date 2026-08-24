import pandas as pd
from extensions import db
from models.aluno import Aluno
from models.horario_aluno import HorarioAluno


SLOT_LIVRE = '---'


def _normalizar_materia(valor):
    if valor is None:
        return SLOT_LIVRE
    if isinstance(valor, float) and pd.isna(valor):
        return SLOT_LIVRE
    texto = str(valor).strip()
    if not texto or texto.lower() in ('nan', 'none'):
        return SLOT_LIVRE
    return texto


def substituir_horarios_aluno(aluno_id, df_aluno):
    """
    Substitui (delete + insert) os horários de UM aluno em `horarios_aluno`, a partir
    das linhas de `df_aluno` (colunas esperadas: 'dia', 'horario' e, opcionalmente,
    'materia').

    Não faz commit — quem chama controla a transação (permite agrupar vários alunos
    da mesma turma em um único commit).
    """
    if aluno_id is None or df_aluno is None or df_aluno.empty:
        return

    HorarioAluno.query.filter_by(aluno_id=aluno_id).delete()

    vistos = set()
    for _, row in df_aluno.iterrows():
        dia = str(row.get('dia', '')).strip()
        horario = str(row.get('horario', '')).strip()
        if not dia or not horario or dia.lower() == 'nan' or horario.lower() == 'nan':
            continue

        materia = _normalizar_materia(row.get('materia'))
        if materia == SLOT_LIVRE:
            # Só guardamos horários ocupados: slots livres ('---') não geram linha.
            continue

        chave = (dia, horario)
        if chave in vistos:
            continue
        vistos.add(chave)

        db.session.add(HorarioAluno(
            aluno_id=aluno_id,
            dia=dia,
            horario=horario,
            materia=materia,
        ))


def salvar_horarios_turma(turma_id, base_df):
    if base_df is None or base_df.empty or 'aluno' not in base_df.columns:
        return

    try:
        alunos_da_turma = Aluno.query.filter_by(turma_id=turma_id).all()
        mapa_aluno_id = {a.nome: a.id for a in alunos_da_turma}

        for nome_aluno, df_aluno in base_df.groupby('aluno'):
            aluno_id = mapa_aluno_id.get(nome_aluno)
            if aluno_id is None:
                # Aluno não encontrado na tabela relacional pula, sem
                # impedir o restante do processamento.
                continue
            substituir_horarios_aluno(aluno_id, df_aluno)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"AVISO: falha ao espelhar horarios_aluno para a turma {turma_id}: {e}")
