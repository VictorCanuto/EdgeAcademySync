from typing import List, Dict, Any, Set, Tuple

def _get_nome_membro(membro: Any) -> str:
    # Garante que sempre retornamos o nome como string.
    if isinstance(membro, dict):
        return membro.get('nome', '')
    return str(membro)

def sugerir_trocas(
    aluno: str,
    grupos_formados: List[Dict[str, Any]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> Dict[str, Any]:
    sugestoes = {"mover_para_grupo": [], "troca_simples": []}

    # 1. Encontrar o grupo atual do aluno 'A'
    grupo_atual_info = next(({'idx': i, 'grupo': g}
                             for i, g in enumerate(grupos_formados)
                             if any(_get_nome_membro(m) == aluno for m in g['Membros'])), None)

    if not grupo_atual_info:
        return sugestoes

    grupo_atual = grupo_atual_info['grupo']
    grupo_atual_idx = grupo_atual_info['idx']
    slot_atual = (grupo_atual['Dia'], grupo_atual['Horário'])
    slots_disponiveis_aluno_a = slots_por_aluno.get(aluno, set())

    # 2. Iterar sobre outros grupos para encontrar sugestões
    for idx, g_destino in enumerate(grupos_formados):
        if idx == grupo_atual_idx:
            continue
            
        slot_destino = (g_destino['Dia'], g_destino['Horário'])

        # --- LÓGICA DE MOVER ---
        # O aluno A PODE participar do slot de destino?
        # A condição foi invertida de 'not in' para 'in'.
        pode_mover_para_destino = slot_destino in slots_disponiveis_aluno_a

        if pode_mover_para_destino:
            sugestoes["mover_para_grupo"].append({
                "aluno_a": aluno,
                "grupo_a_id": grupo_atual['Grupo'],
                "aluno_b": None,
                "grupo_b_id": g_destino['Grupo'],
                "texto": f"Mover para: Grupo {g_destino['Grupo']}" # Texto para exibição
            })

        # --- LÓGICA DE TROCA ---
        for outro_aluno in g_destino['Membros']:
            outro_aluno_nome = _get_nome_membro(outro_aluno)
            if outro_aluno_nome == aluno:
                continue

            slots_disponiveis_outro_aluno = slots_por_aluno.get(outro_aluno_nome, set())

            # O 'outro_aluno' (B) PODE participar do slot do grupo atual?
            # A condição foi invertida para 'in'.
            outro_pode_mover_para_origem = slot_atual in slots_disponiveis_outro_aluno

            # A troca só é válida se AMBOS puderem ir para os slots um do outro
            if pode_mover_para_destino and outro_pode_mover_para_origem:
                sugestoes["troca_simples"].append({
                    "aluno_a": aluno,
                    "grupo_a_id": grupo_atual['Grupo'],
                    "aluno_b": outro_aluno_nome,
                    "grupo_b_id": g_destino['Grupo'],
                    "texto": f"Trocar com: {outro_aluno_nome} (Grupo {g_destino['Grupo']})" # Texto para exibição
                })
                
    return sugestoes

# Coloque esta função logo abaixo de 'sugerir_trocas'
def executar_troca(
    grupos: List[Dict[str, Any]],
    aluno_a: str,
    grupo_a_id: int,
    aluno_b: str = None,
    grupo_b_id: int = None
) -> List[Dict[str, Any]]:
    
    # 1. Normalizar membros e criar cópia para modificação
    grupos_modificados = []
    for g in grupos:
        g_copia = g.copy()
        g_copia['Membros'] = [_get_nome_membro(m) for m in g_copia['Membros']]
        grupos_modificados.append(g_copia)

    # 2. Encontrar os índices dos grupos (A é obrigatório)
    g_idx_a = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_a_id), None)
    
    if g_idx_a is None:
        return grupos # Grupo de origem não encontrado.

    grupo_a = grupos_modificados[g_idx_a]
    
    # Caso de TROCA SIMPLES (aluno_b existe)
    if aluno_b:
        if grupo_b_id is None:
            return grupos
            
        g_idx_b = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_b_id), None)

        if g_idx_b is None:
            return grupos
            
        grupo_b = grupos_modificados[g_idx_b]

        # 3. Execução da TROCA A <-> B
        if aluno_a in grupo_a['Membros'] and aluno_b in grupo_b['Membros']:
            # Troca
            grupo_a['Membros'].remove(aluno_a)
            grupo_a['Membros'].append(aluno_b)
            grupo_b['Membros'].remove(aluno_b)
            grupo_b['Membros'].append(aluno_a)

    # Caso de MOVER (aluno_b é None)
    elif grupo_b_id is not None:
        g_idx_b = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_b_id), None)
        
        if g_idx_b is None:
            return grupos
            
        grupo_b = grupos_modificados[g_idx_b]
        
        # 3. Execução do MOVIMENTO A -> B
        if aluno_a in grupo_a['Membros']:
            # Movimento
            grupo_a['Membros'].remove(aluno_a)
            grupo_b['Membros'].append(aluno_a)
        
    return grupos_modificados