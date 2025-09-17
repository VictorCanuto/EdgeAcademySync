import pandas as pd
from datetime import datetime
import random

# --- FUNÇÃO HELPER PARA LIDAR COM HORÁRIOS ---
def horarios_conflitam(horario_aluno, bloco_acompanhamento):
    """Verifica se um horário de aula de um aluno conflita com um bloco de acompanhamento."""
    try:
        inicio_aluno_str, fim_aluno_str = horario_aluno.split(' - ')
        inicio_aluno = datetime.strptime(inicio_aluno_str, '%H:%M').time()
        fim_aluno = datetime.strptime(fim_aluno_str, '%H:%M').time()
        
        inicio_bloco = datetime.strptime(f"{bloco_acompanhamento[0]:02d}:00", '%H:%M').time()
        fim_bloco = datetime.strptime(f"{bloco_acompanhamento[1]:02d}:00", '%H:%M').time()
        
        return inicio_aluno < fim_bloco and fim_aluno > inicio_bloco
    except ValueError:
        return False

# --- NOVA FUNÇÃO HELPER PARA CALCULAR TAMANHOS DE GRUPO ---
def calcular_tamanhos_grupos(num_alunos, num_grupos):
    """Calcula os tamanhos dos grupos para que sejam o mais equilibrados possível."""
    if num_grupos == 0:
        return []
    tamanho_base = num_alunos // num_grupos
    resto = num_alunos % num_grupos
    tamanhos = [tamanho_base + 1] * resto + [tamanho_base] * (num_grupos - resto)
    return [t for t in tamanhos if t > 0]  # Retorna apenas tamanhos maiores que zero

# --- FUNÇÃO PARA TENTAR PERMUTAÇÃO ---
def tentar_permutacao(grupos_formados, aluno_nao_alocado, mapa_disponibilidade, slots_por_aluno):
    """Tenta trocar alunos entre grupos para acomodar um não alocado, permitindo múltiplas trocas se necessário."""
    for grupo_idx, grupo in enumerate(grupos_formados):
        slot = (grupo['Dia'], grupo['Horário'])
        if aluno_nao_alocado in mapa_disponibilidade.get(slot, set()):
            # Adiciona diretamente, permitindo desbalanceamento temporário
            grupo['Membros'].append(aluno_nao_alocado)
            return True
        
        # Tenta troca simples
        for membro in list(grupo['Membros']):
            membro_slots = slots_por_aluno[membro]
            for other_grupo_idx, other_grupo in enumerate(grupos_formados):
                if other_grupo_idx == grupo_idx:
                    continue
                other_slot = (other_grupo['Dia'], other_grupo['Horário'])
                if membro in mapa_disponibilidade.get(other_slot, set()):
                    # Troca
                    grupos_formados[grupo_idx]['Membros'].remove(membro)
                    grupos_formados[other_grupo_idx]['Membros'].append(membro)
                    grupos_formados[grupo_idx]['Membros'].append(aluno_nao_alocado)
                    return True
    return False

# --- NOVA FUNÇÃO PARA BALANCEAR GRUPOS ---
def balancear_grupos(grupos_formados, mapa_disponibilidade, slots_por_aluno, max_tentativas_balance=100):
    """Tenta balancear os tamanhos dos grupos movendo alunos entre eles, se compatível."""
    tentativas = 0
    while tentativas < max_tentativas_balance:
        tamanhos = [len(g['Membros']) for g in grupos_formados]
        max_tam = max(tamanhos)
        min_tam = min(tamanhos)
        if max_tam - min_tam <= 1:
            print("Grupos balanceados com sucesso!")
            break  # Já balanceado (diferença <=1)
        
        # Encontra grupo maior e menor
        grupo_maior_idx = tamanhos.index(max_tam)
        grupo_menor_idx = tamanhos.index(min_tam)
        
        grupo_maior = grupos_formados[grupo_maior_idx]
        grupo_menor = grupos_formados[grupo_menor_idx]
        
        slot_menor = (grupo_menor['Dia'], grupo_menor['Horário'])
        
        # Tenta mover um aluno do maior para o menor, se compatível
        movido = False
        for membro in list(grupo_maior['Membros']):
            if membro in mapa_disponibilidade.get(slot_menor, set()):
                # Move
                grupo_maior['Membros'].remove(membro)
                grupo_menor['Membros'].append(membro)
                movido = True
                print(f"Aluno {membro} movido do grupo {grupo_maior_idx+1} para {grupo_menor_idx+1} para balanceamento.")
                break
        
        if not movido:
            # Se não conseguir mover diretamente, tenta troca com alguém do menor
            for membro_maior in list(grupo_maior['Membros']):
                slot_maior = (grupo_maior['Dia'], grupo_maior['Horário'])
                for membro_menor in list(grupo_menor['Membros']):
                    if (membro_maior in mapa_disponibilidade.get(slot_menor, set()) and
                        membro_menor in mapa_disponibilidade.get(slot_maior, set())):
                        # Troca
                        grupo_maior['Membros'].remove(membro_maior)
                        grupo_menor['Membros'].remove(membro_menor)
                        grupo_maior['Membros'].append(membro_menor)
                        grupo_menor['Membros'].append(membro_maior)
                        movido = True
                        print(f"Troca realizada entre {membro_maior} e {membro_menor} para balanceamento.")
                        break
                if movido:
                    break
        
        if not movido:
            tentativas += 1
        else:
            tentativas = 0  # Reset se sucesso, para continuar balanceando se necessário

    if max_tam - min_tam > 1:
        print("Não foi possível balancear perfeitamente; mantendo como está.")

# --- FUNÇÃO PRINCIPAL DO ALGORITMO (ATUALIZADA) ---
def formar_grupos(caminho_csv, num_grupos, max_tentativas=50):
    """Algoritmo aprimorado para formar grupos de tamanhos semelhantes, priorizando alunos com menos opções. Repete até alocar todos ou atingir max."""
    try:
        df = pd.read_csv(caminho_csv)
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{caminho_csv}' não encontrado. Execute o processador.py primeiro.")
        return

    # --- 1. PREPARAÇÃO DOS DADOS ---
    todos_os_alunos = set(df['aluno'].unique())
    
    dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex']  # Sem sábado
    
    blocos_validos = {
        "Manhã (08h-11h)": (8, 11),
        "Manhã (09h-12h)": (9, 12),
        "Tarde (14h-17h)": (14, 17)
    }

    tentativas = 0
    while tentativas < max_tentativas:
        tentativas += 1
        print(f"\nTentativa {tentativas} de formação de grupos...")

        # --- 2. MAPEAMENTO DE DISPONIBILIDADE ---
        mapa_disponibilidade = {}
        for dia in dias_semana:
            for nome_bloco, horas_bloco in blocos_validos.items():
                slot_id = (dia, nome_bloco)
                alunos_disponiveis = set()
                for aluno in todos_os_alunos:
                    horarios_ocupados_aluno = df[(df['aluno'] == aluno) & 
                                                 (df['dia'] == dia) & 
                                                 (df['materia'] != '---')]['horario']
                    esta_disponivel = True
                    for horario_ocupado in horarios_ocupados_aluno:
                        if horarios_conflitam(horario_ocupado, horas_bloco):
                            esta_disponivel = False
                            break
                    if esta_disponivel:
                        alunos_disponiveis.add(aluno)
                if alunos_disponiveis:
                    mapa_disponibilidade[slot_id] = alunos_disponiveis

        # Randomizar ordem dos slots
        slots_list = list(mapa_disponibilidade.items())
        random.shuffle(slots_list)
        mapa_disponibilidade = dict(slots_list)

        # --- 2.1. CALCULAR OPÇÕES DE DISPONIBILIDADE POR ALUNO ---
        opcoes_por_aluno = {aluno: 0 for aluno in todos_os_alunos}
        slots_por_aluno = {aluno: set() for aluno in todos_os_alunos}
        for slot, disponiveis in mapa_disponibilidade.items():
            for aluno in disponiveis:
                opcoes_por_aluno[aluno] += 1
                slots_por_aluno[aluno].add(slot)

        alunos_sem_disponibilidade = {aluno for aluno in todos_os_alunos if opcoes_por_aluno[aluno] == 0}
        if alunos_sem_disponibilidade:
            print(f"AVISO: {len(alunos_sem_disponibilidade)} alunos sem disponibilidade em nenhum slot: {', '.join(sorted(alunos_sem_disponibilidade))}")

        # Média de opções para bonus
        media_opcoes = sum(opcoes_por_aluno.values()) / len(opcoes_por_aluno) if opcoes_por_aluno else 0

        # --- 3. ALGORITMO DE FORMAÇÃO DE GRUPOS BALANCEADOS ---
        alunos_nao_alocados = todos_os_alunos.copy()
        grupos_formados = []
        
        tamanhos_ideais_dos_grupos = calcular_tamanhos_grupos(len(todos_os_alunos), num_grupos)
        print(f"Iniciando formação de {len(tamanhos_ideais_dos_grupos)} grupos com tamanhos ideais: {tamanhos_ideais_dos_grupos}...")

        for i, tamanho_alvo in enumerate(tamanhos_ideais_dos_grupos):
            melhor_slot = None
            melhor_grupo_candidato = set()
            max_pontuacao = -float('inf')

            for slot, alunos_disponiveis in mapa_disponibilidade.items():
                alunos_candidatos = alunos_nao_alocados.intersection(alunos_disponiveis)
                len_candidatos = len(alunos_candidatos)
                if len_candidatos >= tamanho_alvo:
                    # Pontuação: número de candidatos + bonus para cobrir alunos com poucas opções
                    bonus = sum(1 for a in alunos_candidatos if opcoes_por_aluno[a] < media_opcoes)
                    pontuacao = len_candidatos + bonus * 2  # Peso maior para alunos difíceis
                    if pontuacao > max_pontuacao:
                        max_pontuacao = pontuacao
                        melhor_slot = slot
                        melhor_grupo_candidato = alunos_candidatos
            
            if melhor_slot is None:
                # Relaxamento com pontuação
                max_pontuacao = -float('inf')
                for slot, alunos_disponiveis in mapa_disponibilidade.items():
                    alunos_candidatos = alunos_nao_alocados.intersection(alunos_disponiveis)
                    len_candidatos = len(alunos_candidatos)
                    if len_candidatos > 0:
                        bonus = sum(1 for a in alunos_candidatos if opcoes_por_aluno[a] < media_opcoes)
                        pontuacao = len_candidatos + bonus * 2
                        if pontuacao > max_pontuacao:
                            max_pontuacao = pontuacao
                            melhor_slot = slot
                            melhor_grupo_candidato = alunos_candidatos
                if melhor_slot is None:
                    print(f"ERRO: Não há mais slots disponíveis para o {i+1}º grupo.")
                    break
                tamanho_alvo = len(melhor_grupo_candidato)
            
            # Selecionar priorizando alunos difíceis
            candidatos_ordenados = sorted(
                list(melhor_grupo_candidato),
                key=lambda a: opcoes_por_aluno[a]
            )
            membros_do_grupo = set(candidatos_ordenados[:tamanho_alvo])
            
            grupos_formados.append({
                "Grupo": i + 1, "Dia": melhor_slot[0], "Horário": melhor_slot[1], "Membros": list(membros_do_grupo)
            })
            
            alunos_nao_alocados -= membros_do_grupo

        # --- 3.1. TENTATIVA DE ALOCAR RESTANTES ---
        if alunos_nao_alocados:
            print("\nTentando alocar alunos restantes em grupos existentes...")
            nao_alocados_ordenados = sorted(alunos_nao_alocados, key=lambda a: opcoes_por_aluno[a])
            for aluno in nao_alocados_ordenados:
                if tentar_permutacao(grupos_formados, aluno, mapa_disponibilidade, slots_por_aluno):
                    alunos_nao_alocados.remove(aluno)
                    print(f"Aluno {aluno} alocado via permutação ou adição.")

        # --- 3.2. BALANCEAMENTO FINAL ---
        if not alunos_nao_alocados:
            print("\nIniciando balanceamento dos grupos...")
            balancear_grupos(grupos_formados, mapa_disponibilidade, slots_por_aluno)
            break  # Sai se alocou todos, após balancear

    # --- 4. EXIBIÇÃO DOS RESULTADOS ---
    print("\n--- GRUPOS FORMADOS ---")
    for grupo in grupos_formados:
        print(f"\n{grupo['Grupo']}º Grupo: {grupo['Dia']} - {grupo['Horário']}")
        print(f"  - {len(grupo['Membros'])} Pessoas: {', '.join(sorted(grupo['Membros']))}")

    if alunos_nao_alocados:
        print("\n--- ALUNOS QUE NÃO FORAM ALOCADOS ---")
        print(f"  - {len(alunos_nao_alocados)} Pessoas: {', '.join(sorted(alunos_nao_alocados))}")
    else:
        print("\nTodos os alunos foram alocados com sucesso!")
    return grupos_formados

# --- Bloco de Execução Principal ---
if __name__ == "__main__":
    NUMERO_DE_GRUPOS = 3
    formar_grupos('base_consolidada_ok.csv', NUMERO_DE_GRUPOS)