from typing import List, Dict, Any, Set, Tuple, Optional

def _get_nome_membro(membro: Any) -> str:
    # Sua função existente para extrair o nome. Assumindo que retorna a string do nome.
    if isinstance(membro, dict):
        return membro.get('nome', '')
    return str(membro)

def _normalize_name_for_match(name: str) -> str:
    """Padroniza o nome para comparação: substitui underscores por espaços e deixa em minúsculas."""
    if not isinstance(name, str):
        return ''
    return name.replace('_', ' ').strip().lower()

def _find_exact_member_name(members_list: List[str], target_normalized_name: str) -> Optional[str]:
    """
    Busca o nome exato na lista de membros (ex: 'Nome Aluno' vs 'Nome_Aluno')
    usando a versão normalizada para comparação.
    Retorna a string exata presente na lista, ou None se não encontrar.
    """
    for member_name in members_list:
        # Assume que os membros são strings
        if _normalize_name_for_match(member_name) == target_normalized_name:
            return member_name
    return None

def sugerir_trocas(
    aluno: str,
    grupos_formados: List[Dict[str, Any]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> Dict[str, Any]:
    sugestoes = {"mover_para_grupo": [], "troca_simples": []}

    # Normalize o nome do aluno 'A'
    aluno_a_normalized = _normalize_name_for_match(aluno) 

    # 1. Encontrar o grupo atual do aluno 'A'
    # Use a função de normalização na busca!
    grupo_atual_info = next(({'idx': i, 'grupo': g}
                             for i, g in enumerate(grupos_formados)
                             # CORREÇÃO AQUI: Compare nomes normalizados
                             if any(_normalize_name_for_match(_get_nome_membro(m)) == aluno_a_normalized 
                                    for m in g['Membros'])), None)

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

# -----------------------------------
# FUNÇÃO EXECUTAR_TROCA COMPLETA 
# -----------------------------------
def executar_troca(
    aluno_a: str,
    grupo_a_id: str,
    grupos: List[Dict[str, Any]],
    aluno_b: Optional[str] = None,
    grupo_b_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    
    # Faz uma cópia para evitar modificar a lista original diretamente
    grupos_modificados = [g.copy() for g in grupos] 

    # Normaliza os nomes de entrada para comparação
    aluno_a_normalized = _normalize_name_for_match(aluno_a)
    aluno_b_normalized = _normalize_name_for_match(aluno_b) if aluno_b else None
    
    # 1. Encontrar Grupo A (Origem)
    g_idx_a = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_a_id), None)
    
    if g_idx_a is None:
        return grupos # Grupo de origem não encontrado.

    grupo_a = grupos_modificados[g_idx_a]
    
    # 2. Encontrar a string exata do Aluno A na lista de membros
    exact_aluno_a = _find_exact_member_name(grupo_a['Membros'], aluno_a_normalized)

    # Se não encontrar o aluno, retorna sem fazer nada
    if not exact_aluno_a:
        # Aqui você poderia logar um erro, mas por enquanto, apenas retorna a lista original
        print(f"Erro: Aluno A '{aluno_a}' não encontrado no Grupo '{grupo_a_id}'.")
        return grupos

    # Caso de TROCA SIMPLES (aluno_b existe)
    if aluno_b:
        if grupo_b_id is None:
            return grupos
            
        g_idx_b = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_b_id), None)

        if g_idx_b is None:
            return grupos
            
        grupo_b = grupos_modificados[g_idx_b]

        # 2.1. Encontrar a string exata do Aluno B na lista de membros
        exact_aluno_b = _find_exact_member_name(grupo_b['Membros'], aluno_b_normalized)

        # 3. Execução da TROCA A <-> B
        # Agora verifica se a versão exata do aluno B foi encontrada
        if exact_aluno_b:
            # Troca
            grupo_a['Membros'].remove(exact_aluno_a) # Remove a string EXATA
            grupo_a['Membros'].append(exact_aluno_b) # Adiciona a string EXATA
            grupo_b['Membros'].remove(exact_aluno_b) # Remove a string EXATA
            grupo_b['Membros'].append(exact_aluno_a) # Adiciona a string EXATA

    # Caso de MOVER (aluno_b é None)
    elif grupo_b_id is not None:
        g_idx_b = next((i for i, g in enumerate(grupos_modificados) if g['Grupo'] == grupo_b_id), None)
        
        if g_idx_b is None:
            return grupos
            
        grupo_b = grupos_modificados[g_idx_b]

        # 3. Execução do MOVER A -> B
        # O 'exact_aluno_a' já foi encontrado antes do bloco condicional
        
        # Movimentação
        grupo_a['Membros'].remove(exact_aluno_a) # Remove a string EXATA
        grupo_b['Membros'].append(exact_aluno_a) # Adiciona a string EXATA
            
    # Retorna a lista de grupos modificada
    return grupos_modificados