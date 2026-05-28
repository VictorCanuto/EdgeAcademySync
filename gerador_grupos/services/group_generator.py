
import pandas as pd
from datetime import datetime
import random
from typing import List, Dict, Tuple, Any, Set, Optional, Union

# -------------------------------
# Helpers de horário
# -------------------------------
def _parse_interval(hh: int) -> datetime.time:
    return datetime.strptime(f"{hh:02d}:00", "%H:%M").time()

def horarios_conflitam(horario_a: Any, inicio: int, fim: int) -> bool:
    """Verifica se 'horario_a' (ex.: '09:20 - 10:10' ou 9 ou '9') conflita com o intervalo [inicio, fim] (em horas inteiras)."""
    if horario_a is None:
        return False
        
    horario_str = str(horario_a).strip()
    if "-" in horario_str:
        try:
            from datetime import datetime
            def _parse_time(s: str):
                return datetime.strptime(s.strip(), "%H:%M").time()

            ini_a, fim_a = [x.strip() for x in horario_str.split("-")]
            ini_a, fim_a = _parse_time(ini_a), _parse_time(fim_a)

            ini_b = datetime.strptime(f"{inicio:02d}:00", "%H:%M").time()
            fim_b = datetime.strptime(f"{fim:02d}:00", "%H:%M").time()

            return ini_a < fim_b and fim_a > ini_b
        except Exception:
            pass
            
    try:
        if ':' in horario_str:
            hora_inicio = int(horario_str.split(':')[0])
        else:
            hora_inicio = int(float(horario_str))
        
        return hora_inicio < fim and (hora_inicio + 1) > inicio
    except Exception:
        return False

def balancear_grupos(
    grupos_formados: List[Dict[str, Any]],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> None:
    """
    Balanceia os grupos movendo alunos dos maiores para os menores,
    garantindo que o aluno movido tenha disponibilidade no novo slot.
    Continua até que a diferença entre o maior e o menor grupo seja <= 1.
    """
    if not grupos_formados:
        return

    while True:
        # Ordena os grupos pelo tamanho, do menor para o maior
        grupos_formados.sort(key=lambda g: len(g['Membros']))
        
        g_menor = grupos_formados[0]
        g_maior = grupos_formados[-1]

        tamanho_menor = len(g_menor['Membros'])
        tamanho_maior = len(g_maior['Membros'])

        # Se a diferença for 1 ou 0, o balanceamento está concluído.
        if tamanho_maior - tamanho_menor <= 1:
            break

        slot_menor = (g_menor['Dia'], g_menor['Horário'])
        aluno_movido = False

        # Tenta mover um aluno do maior grupo para o menor
        for aluno in list(g_maior['Membros']):
            # Verifica se o aluno tem disponibilidade para o slot do grupo menor
            if slot_menor in slots_por_aluno.get(aluno, set()):
                g_maior['Membros'].remove(aluno)
                g_menor['Membros'].append(aluno)
                aluno_movido = True
                break  # Sai do loop de alunos pois já moveu um

        # Se não conseguiu mover ninguém, o balanceamento está travado. Interrompe.
        if not aluno_movido:
            break

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

    # Pré-computa horários ocupados por aluno e dia para evitar filtros lentos do Pandas no loop
    ocupados = {}
    for aluno in todos_os_alunos:
        for dia in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]:
            ocupados[(aluno, dia)] = []
            
    df_busy = df[df['materia'] != '---']
    for _, row in df_busy.iterrows():
        al_val = str(row['aluno'])
        dia_val = str(row['dia'])
        ocupados[(al_val, dia_val)] = ocupados.get((al_val, dia_val), []) + [row['horario']]

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
                    busy = ocupados.get((aluno, dia), [])
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

        # 3.1 Tenta alocar restantes de forma inteligente
        if alunos_nao_alocados:
            alunos_nao_alocados = tentar_alocar_restantes(
                grupos_formados, 
                alunos_nao_alocados, 
                slots_por_aluno
            )

        # 3.2 Balanceamento robusto final
        balancear_grupos(grupos_formados, slots_por_aluno)

        # Se todos foram alocados, terminamos a busca.
        if not alunos_nao_alocados:
            break

    # Adiciona a lista de alunos não alocados ao resultado final
    resultado = {
        "grupos": grupos_formados,
        "slots_por_aluno": slots_por_aluno,
        "mapa_disponibilidade": mapa_disponibilidade,
        "alunos_sem_grupo": sorted(list(alunos_nao_alocados)) # Adiciona isso
    }
    
    return resultado

if __name__ == "__main__":
    # Exemplo básico de uso com blocos dinâmicos
    blocos_exemplo = [
        {"nome": "Manhã", "inicio": 8, "fim": 11, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
        {"nome": "Manhã 2", "inicio": 9, "fim": 12, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
        {"nome": "Tarde", "inicio": 14, "fim": 17, "dias": ["Seg","Ter","Qua","Qui","Sex"]},
    ]
    res = formar_grupos('base_consolidada_ok.csv', num_grupos=3, blocos=blocos_exemplo)
    print(res["grupos"])



def calcular_tamanhos_grupos(total_alunos: int, num_grupos: int) -> List[int]:
    """Divide o total de alunos em grupos de tamanhos equilibrados."""
    base, resto = divmod(total_alunos, num_grupos)
    return [base + 1 if i < resto else base for i in range(num_grupos)]

def tentar_alocar_restantes(
    grupos: List[Dict[str, Any]],
    alunos_nao_alocados: Set[str],
    slots_por_aluno: Dict[str, Set[Tuple[str, str]]]
) -> Set[str]:
    """
    Tenta alocar os alunos restantes, priorizando os menores grupos.
    Retorna o conjunto de alunos que AINDA não foram alocados.
    """
    ainda_nao_alocados = set(alunos_nao_alocados)
    
    for aluno in list(ainda_nao_alocados):
        melhor_grupo_para_alocar = None
        menor_tamanho = float('inf')

        # Encontra o menor grupo onde o aluno pode entrar
        for g in grupos:
            slot = (g["Dia"], g["Horário"])
            tamanho_atual = len(g["Membros"])
            
            if slot in slots_por_aluno.get(aluno, set()) and tamanho_atual < menor_tamanho:
                menor_tamanho = tamanho_atual
                melhor_grupo_para_alocar = g
        
        # Se encontrou um grupo, aloca o aluno
        if melhor_grupo_para_alocar:
            melhor_grupo_para_alocar["Membros"].append(aluno)
            ainda_nao_alocados.remove(aluno)
            
    return ainda_nao_alocados
