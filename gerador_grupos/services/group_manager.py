from typing import List, Dict, Any, Set, Tuple

def _get_nome_membro(membro: Any) -> str:
    if isinstance(membro, dict):
        return membro.get('nome', '')
    return str(membro)

def sugerir_trocas(
    aluno: str,
    grupos_formados: List[Dict[str, Any]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> Dict[str, Any]:
    sugestoes = {"mover_para_grupo": [], "troca_simples": []}

    grupo_atual_info = next(({'idx': i, 'grupo': g} 
                             for i, g in enumerate(grupos_formados) 
                             if any(_get_nome_membro(m) == aluno for m in g['Membros'])), None)
    
    if not grupo_atual_info:
        return sugestoes

    grupo_atual_idx = grupo_atual_info['idx']
    grupo_atual = grupo_atual_info['grupo']
    slot_atual = (grupo_atual['Dia'], grupo_atual['Horário'])
    slots_do_aluno = slots_por_aluno.get(aluno, set())

    for idx, g_destino in enumerate(grupos_formados):
        if idx == grupo_atual_idx:
            continue
        slot_destino = (g_destino['Dia'], g_destino['Horário'])
        if slot_destino in slots_do_aluno:
            sugestoes["mover_para_grupo"].append({
                "aluno_origem": aluno,
                "grupo_origem_id": grupo_atual['Grupo'],
                "grupo_destino_id": g_destino['Grupo'],
            })

    for idx, g_destino in enumerate(grupos_formados):
        if idx == grupo_atual_idx:
            continue
        slot_destino = (g_destino['Dia'], g_destino['Horário'])
        
        for membro_destino in g_destino['Membros']:
            outro_aluno_nome = _get_nome_membro(membro_destino)
            if not outro_aluno_nome:
                continue

            if (slot_destino in slots_do_aluno and
                slot_atual in slots_por_aluno.get(outro_aluno_nome, set())):
                sugestoes["troca_simples"].append({
                    "aluno_a": aluno,
                    "grupo_a_id": grupo_atual['Grupo'],
                    "aluno_b": outro_aluno_nome,
                    "grupo_b_id": g_destino['Grupo'],
                })
    return sugestoes


def executar_troca(
    grupos: List[Dict[str, Any]],
    aluno_a: str,
    grupo_a_id: int,
    aluno_b: str = None,
    grupo_b_id: int = None
) -> List[Dict[str, Any]]:
    for g in grupos:
        g['Membros'] = [_get_nome_membro(m) for m in g['Membros']]

    g_idx_a = next((i for i, g in enumerate(grupos) if g['Grupo'] == grupo_a_id), None)
    g_idx_b = next((i for i, g in enumerate(grupos) if g['Grupo'] == grupo_b_id), None)

    if g_idx_a is None or g_idx_b is None:
        return grupos

    if aluno_b:
        if aluno_a in grupos[g_idx_a]['Membros'] and aluno_b in grupos[g_idx_b]['Membros']:
            grupos[g_idx_a]['Membros'].remove(aluno_a)
            grupos[g_idx_b]['Membros'].remove(aluno_b)
            grupos[g_idx_a]['Membros'].append(aluno_b)
            grupos[g_idx_b]['Membros'].append(aluno_a)
    else:
        if aluno_a in grupos[g_idx_a]['Membros']:
            grupos[g_idx_a]['Membros'].remove(aluno_a)
            grupos[g_idx_b]['Membros'].append(aluno_a)
            
    return grupos