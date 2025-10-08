import pandas as pd
from typing import Dict

def calcular_ranking_disponibilidade(df: pd.DataFrame, top_n: int = 15) -> Dict:
    if df is None or df.empty:
        return {'mais_disponiveis': pd.DataFrame(), 'menos_disponiveis': pd.DataFrame()}

    total_horarios_unicos = len(df['horario'].unique())
    dias_da_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
    total_slots_possiveis = total_horarios_unicos * len(dias_da_semana)

    # Conta horários ocupados por aluno
    horarios_ocupados = df[df['materia'] != '---'].groupby('aluno').size()
    ranking_df = horarios_ocupados.reset_index(name='horarios_ocupados')

    # Calcula os horários livres e o percentual
    ranking_df['horarios_livres'] = total_slots_possiveis - ranking_df['horarios_ocupados']
    ranking_df['percentual_livre'] = (ranking_df['horarios_livres'] / total_slots_possiveis * 100).round(1)

    # Gera os dois rankings)
    mais_disponiveis = ranking_df.sort_values(by=['horarios_livres', 'aluno'], ascending=[False, True]).head(top_n)
    menos_disponiveis = ranking_df.sort_values(by=['horarios_livres', 'aluno'], ascending=[True, True]).head(top_n)

    return {
        'mais_disponiveis': mais_disponiveis,
        'menos_disponiveis': menos_disponiveis
    }
