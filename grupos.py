
import pandas as pd
from datetime import datetime
import random
from typing import List, Dict, Tuple, Any, Set, Optional, Union

# -------------------------------
# Helpers de horário
# -------------------------------
def _parse_interval(hh: int) -> datetime.time:
    return datetime.strptime(f"{hh:02d}:00", "%H:%M").time()

def horarios_conflitam(horario_aluno: str, bloco_inicio_h: int, bloco_fim_h: int) -> bool:
    """
    Verifica se um horário de aula (ex.: "15:20 - 16:10") conflita com um bloco [inicio_h, fim_h].
    """
    try:
        inicio_aluno_str, fim_aluno_str = horario_aluno.split(' - ')
        inicio_aluno = datetime.strptime(inicio_aluno_str, '%H:%M').time()
        fim_aluno = datetime.strptime(fim_aluno_str, '%H:%M').time()
        inicio_bloco = _parse_interval(bloco_inicio_h)
        fim_bloco = _parse_interval(bloco_fim_h)
        return inicio_aluno < fim_bloco and fim_aluno > inicio_bloco
    except Exception:
        return False

def calcular_tamanhos_grupos(num_alunos: int, num_grupos: int) -> List[int]:
    """
    Divide num_alunos em num_grupos tamanhos o mais equilibrados possível.
    """
    if num_grupos <= 0:
        return []
    base = num_alunos // num_grupos
    resto = num_alunos % num_grupos
    tamanhos = [base + 1] * resto + [base] * (num_grupos - resto)
    return [t for t in tamanhos if t > 0]

# -------------------------------
# Lógica de permuta/movimentação
# -------------------------------
def tentar_permutacao(
    grupos_formados: List[Dict[str, Any]],
    aluno_nao_alocado: str,
    mapa_disponibilidade: Dict[Tuple[str, str], Set[str]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> bool:
    """
    Tenta inserir um aluno não alocado em algum grupo existente, via adição direta ou troca simples.
    """
    for g_idx, grupo in enumerate(grupos_formados):
        slot = (grupo['Dia'], grupo['Horário'])
        if aluno_nao_alocado in mapa_disponibilidade.get(slot, set()):
            grupo['Membros'].append(aluno_nao_alocado)
            return True

        for membro in list(grupo['Membros']):
            for other_idx, other in enumerate(grupos_formados):
                if other_idx == g_idx:
                    continue
                other_slot = (other['Dia'], other['Horário'])
                if (membro in mapa_disponibilidade.get(other_slot, set()) and
                    aluno_nao_alocado in mapa_disponibilidade.get(slot, set())):
                    grupos_formados[g_idx]['Membros'].remove(membro)
                    grupos_formados[other_idx]['Membros'].append(membro)
                    grupos_formados[g_idx]['Membros'].append(aluno_nao_alocado)
                    return True
    return False

def balancear_grupos(
    grupos_formados: List[Dict[str, Any]],
    mapa_disponibilidade: Dict[Tuple[str, str], Set[str]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]],
    max_tentativas_balance: int = 100
) -> None:
    """
    Tenta aproximar os tamanhos, movendo alunos entre grupos quando possível.
    """
    tent = 0
    while tent < max_tentativas_balance:
        tamanhos = [len(g['Membros']) for g in grupos_formados]
        if not tamanhos:
            break
        mx, mn = max(tamanhos), min(tamanhos)
        if mx - mn <= 1:
            break

        i_max = tamanhos.index(mx)
        i_min = tamanhos.index(mn)
        g_max = grupos_formados[i_max]
        g_min = grupos_formados[i_min]
        slot_min = (g_min['Dia'], g_min['Horário'])

        movido = False
        for m in list(g_max['Membros']):
            if m in mapa_disponibilidade.get(slot_min, set()):
                g_max['Membros'].remove(m)
                g_min['Membros'].append(m)
                movido = True
                break

        if not movido:
            slot_max = (g_max['Dia'], g_max['Horário'])
            for ma in list(g_max['Membros']):
                for mi in list(g_min['Membros']):
                    if (ma in mapa_disponibilidade.get(slot_min, set()) and
                        mi in mapa_disponibilidade.get(slot_max, set())):
                        g_max['Membros'].remove(ma)
                        g_min['Membros'].remove(mi)
                        g_max['Membros'].append(mi)
                        g_min['Membros'].append(ma)
                        movido = True
                        break
                if movido: break

        if not movido:
            tent += 1
        else:
            tent = 0

# -------------------------------
# Sugestão de trocas (para UI)
# -------------------------------
def sugerir_trocas(
    aluno: str,
    grupos_formados: List[Dict[str, Any]],
    mapa_disponibilidade: Dict[Tuple[str, str], Set[str]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> Dict[str, Any]:
    """
    Gera sugestões de remanejamento para um aluno:
      - Movê-lo para outro grupo cujo slot ele possa participar.
      - Troca 1-para-1 com alguém de outro grupo, garantindo compatibilidade de ambos.
    Retorna um dicionário com listas de sugestões.
    """
    sugestoes = {"mover_para_grupo": [], "troca_simples": []}

    # Descobrir de qual grupo o aluno faz parte, se fizer
    grupo_atual_idx = None
    for idx, g in enumerate(grupos_formados):
        if aluno in g['Membros']:
            grupo_atual_idx = idx
            break

    # Slots onde o aluno pode participar
    slots_do_aluno = slots_por_aluno.get(aluno, set())

    # 1) Sugerir "mover para" (sem troca), se slot bater
    for idx, g in enumerate(grupos_formados):
        slot = (g['Dia'], g['Horário'])
        if idx != grupo_atual_idx and (slot in slots_do_aluno):
            sugestoes["mover_para_grupo"].append({
                "para_grupo": g['Grupo'],
                "dia": g['Dia'],
                "horario": g['Horário'],
                "impacto_tamanhos": {
                    "origem_diminuiria": True if grupo_atual_idx is not None else False,
                    "destino_aumentaria": True
                }
            })

    # 2) Sugerir trocas 1-para-1
    if grupo_atual_idx is not None:
        grupo_atual = grupos_formados[grupo_atual_idx]
        slot_atual = (grupo_atual['Dia'], grupo_atual['Horário'])
        for idx, g in enumerate(grupos_formados):
            if idx == grupo_atual_idx:
                continue
            slot_dest = (g['Dia'], g['Horário'])
            for outro in g['Membros']:
                # "aluno" precisa poder ir para slot_dest
                # "outro" precisa poder vir para slot_atual
                if (slot_dest in slots_por_aluno.get(aluno, set()) and
                    slot_atual in slots_por_aluno.get(outro, set())):
                    sugestoes["troca_simples"].append({
                        "trocar_com": outro,
                        "grupo_destino": g['Grupo'],
                        "dia_destino": g['Dia'],
                        "horario_destino": g['Horário']
                    })

    return sugestoes

# -------------------------------
# Formação de grupos (dinâmica)
# -------------------------------
def _carregar_df(caminho_csv_ou_df: Union[str, pd.DataFrame]) -> pd.DataFrame:
    if isinstance(caminho_csv_ou_df, pd.DataFrame):
        return caminho_csv_ou_df.copy()
    return pd.read_csv(caminho_csv_ou_df)

def formar_grupos(
    caminho_csv_ou_df: Union[str, pd.DataFrame],
    num_grupos: int,
    blocos: List[Dict[str, Any]],
    max_tentativas: int = 50
) -> Dict[str, Any]:
    """
    blocos: lista de dicionários no formato:
        {
            "nome": "Manhã (08-11)",   # opcional; se ausente, geramos automaticamente
            "inicio": 8,               # int (hora)
            "fim": 11,                 # int (hora)
            "dias": ["Seg","Ter","Qua","Qui","Sex"]   # lista de dias (abreviações)
        }
    Retorna:
        {
          "grupos": [ {Grupo, Dia, Horário, Membros} ... ],
          "slots_por_aluno": {aluno: set((dia,horlabel),...) },
          "mapa_disponibilidade": {(dia,horlabel): set(alunos)}
        }
    """
    df = _carregar_df(caminho_csv_ou_df)
    todos_os_alunos: Set[str] = set(df['aluno'].unique())

    # Normaliza blocos
    blocos_norm = []
    for b in blocos:
        nome = b.get("nome")
        ini = int(b["inicio"])
        fim = int(b["fim"])
        dias = b.get("dias") or b.get("dia") or []
        if isinstance(dias, str):
            dias = [d.strip() for d in dias.split(",") if d.strip()]
        if not nome:
            nome = f"{ini:02d}h-{fim:02d}h"
        # Garante que dias é lista
        if not isinstance(dias, list):
            dias = list(dias)
        blocos_norm.append({"nome": nome, "inicio": ini, "fim": fim, "dias": dias})

    tentativas = 0
    mapa_disponibilidade: Dict[Tuple[str, str], Set[str]] = {}
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]] = {a: set() for a in todos_os_alunos}

    grupos_formados: List[Dict[str, Any]] = []
    alunos_nao_alocados: Set[str] = set()

    while tentativas < max_tentativas:
        tentativas += 1
        # 1) Mapeia disponibilidade por slot (dia x bloco)
        mapa_disponibilidade.clear()
        for b in blocos_norm:
            label = f"{b['nome']} ({b['inicio']:02d}h-{b['fim']:02d}h)"
            for dia in b['dias']:
                slot_id = (dia, label)
                disponiveis = set()
                for aluno in todos_os_alunos:
                    busy = df[(df['aluno'] == aluno) & (df['dia'] == dia) & (df['materia'] != '---')]['horario']
                    livre = True
                    for h in busy:
                        if horarios_conflitam(h, b['inicio'], b['fim']):
                            livre = False
                            break
                    if livre:
                        disponiveis.add(aluno)
                if disponiveis:
                    mapa_disponibilidade[slot_id] = disponiveis

        # Embaralha slots
        items = list(mapa_disponibilidade.items())
        random.shuffle(items)
        mapa_disponibilidade = dict(items)

        # 2) Opções por aluno
        opcoes_por_aluno = {a: 0 for a in todos_os_alunos}
        slots_por_aluno = {a: set() for a in todos_os_alunos}
        for slot, disponiveis in mapa_disponibilidade.items():
            for a in disponiveis:
                opcoes_por_aluno[a] += 1
                slots_por_aluno[a].add(slot)
        media_op = (sum(opcoes_por_aluno.values()) / len(opcoes_por_aluno)) if opcoes_por_aluno else 0

        # 3) Formação de grupos
        alunos_nao_alocados = set(todos_os_alunos)
        grupos_formados = []
        tamanhos_alvos = calcular_tamanhos_grupos(len(todos_os_alunos), num_grupos)

        for i, t_alvo in enumerate(tamanhos_alvos):
            melhor_slot = None
            melhor_cand = set()
            best_score = -1e9
            for slot, disponiveis in mapa_disponibilidade.items():
                cand = alunos_nao_alocados.intersection(disponiveis)
                if len(cand) >= t_alvo:
                    bonus = sum(1 for a in cand if opcoes_por_aluno[a] < media_op)
                    score = len(cand) + 2*bonus
                    if score > best_score:
                        best_score = score
                        melhor_slot = slot
                        melhor_cand = cand
            if melhor_slot is None:
                # relaxa
                best_score = -1e9
                for slot, disponiveis in mapa_disponibilidade.items():
                    cand = alunos_nao_alocados.intersection(disponiveis)
                    if len(cand) > 0:
                        bonus = sum(1 for a in cand if opcoes_por_aluno[a] < media_op)
                        score = len(cand) + 2*bonus
                        if score > best_score:
                            best_score = score
                            melhor_slot = slot
                            melhor_cand = cand
                if melhor_slot is None:
                    break
                t_alvo = len(melhor_cand)

            escolhidos = sorted(list(melhor_cand), key=lambda a: opcoes_por_aluno[a])[:t_alvo]
            grupos_formados.append({
                "Grupo": i+1,
                "Dia": melhor_slot[0],
                "Horário": melhor_slot[1],
                "Membros": escolhidos
            })
            alunos_nao_alocados -= set(escolhidos)

        # 3.1 Tenta alocar restantes
        if alunos_nao_alocados:
            nao_alocados_ord = sorted(list(alunos_nao_alocados), key=lambda a: opcoes_por_aluno[a])
            for a in nao_alocados_ord:
                if tentar_permutacao(grupos_formados, a, mapa_disponibilidade, slots_por_aluno):
                    alunos_nao_alocados.remove(a)

        # 3.2 Balanceamento
        if not alunos_nao_alocados:
            balancear_grupos(grupos_formados, mapa_disponibilidade, slots_por_aluno)
            break

    return {
        "grupos": grupos_formados,
        "slots_por_aluno": slots_por_aluno,
        "mapa_disponibilidade": mapa_disponibilidade
    }

if __name__ == "__main__":
    # Exemplo básico de uso com blocos dinâmicos
    blocos_exemplo = [
        {"nome": "Manhã", "inicio": 8, "fim": 11, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
        {"nome": "Manhã 2", "inicio": 9, "fim": 12, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
        {"nome": "Tarde", "inicio": 14, "fim": 17, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
    ]
    res = formar_grupos('base_consolidada_ok.csv', num_grupos=3, blocos=blocos_exemplo)
    print(res["grupos"])
