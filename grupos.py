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

# --- FUNÇÃO PRINCIPAL DO ALGORITMO (ATUALIZADA) ---
def formar_grupos(caminho_csv, num_grupos):
    """Algoritmo aprimorado para formar grupos de tamanhos semelhantes, priorizando alunos com menos opções."""
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

    # --- 2. MAPEAMENTO DE DISPONIBILIDADE ---
    mapa_disponibilidade = {}
    print("Mapeando disponibilidade de todos os alunos...")
    for dia in dias_semana:
        for nome_bloco, horas_bloco in blocos_validos.items():
            slot_id = (dia, nome_bloco)
            alunos_disponiveis = set()
            for aluno in todos_os_alunos:
                # Correção: Filtrar apenas horários ocupados (materia != '---')
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
            if alunos_disponiveis:  # Só adiciona slots não vazios
                mapa_disponibilidade[slot_id] = alunos_disponiveis

    # --- 2.1. CALCULAR OPÇÕES DE DISPONIBILIDADE POR ALUNO ---
    # Para priorizar alunos "difíceis" (com menos slots disponíveis)
    opcoes_por_aluno = {aluno: 0 for aluno in todos_os_alunos}
    slots_por_aluno = {aluno: set() for aluno in todos_os_alunos}
    for slot, disponiveis in mapa_disponibilidade.items():
        for aluno in disponiveis:
            opcoes_por_aluno[aluno] += 1
            slots_por_aluno[aluno].add(slot)

    # Identificar alunos sem nenhuma disponibilidade
    alunos_sem_disponibilidade = {aluno for aluno in todos_os_alunos if opcoes_por_aluno[aluno] == 0}
    if alunos_sem_disponibilidade:
        print(f"AVISO: {len(alunos_sem_disponibilidade)} alunos sem disponibilidade em nenhum slot: {', '.join(sorted(alunos_sem_disponibilidade))}")

    # --- 3. ALGORITMO DE FORMAÇÃO DE GRUPOS BALANCEADOS ---
    alunos_nao_alocados = todos_os_alunos.copy()
    grupos_formados = []
    
    tamanhos_ideais_dos_grupos = calcular_tamanhos_grupos(len(todos_os_alunos), num_grupos)
    print(f"\nIniciando formação de {len(tamanhos_ideais_dos_grupos)} grupos com tamanhos ideais: {tamanhos_ideais_dos_grupos}...")

    for i, tamanho_alvo in enumerate(tamanhos_ideais_dos_grupos):
        melhor_slot = None
        melhor_grupo_candidato = set()
        max_disponiveis_acima_do_alvo = -float('inf')

        # Encontra o melhor slot para formar um grupo de tamanho 'tamanho_alvo'
        for slot, alunos_disponiveis in mapa_disponibilidade.items():
            # Interseção para ver quais alunos NÃO ALOCADOS estão disponíveis neste slot
            alunos_candidatos = alunos_nao_alocados.intersection(alunos_disponiveis)
            
            # Verifica se este slot tem gente suficiente para formar o grupo
            if len(alunos_candidatos) >= tamanho_alvo:
                # Heurística atualizada: escolhe o slot com o MAIOR número de pessoas (para usar slots populares primeiro)
                if len(alunos_candidatos) > max_disponiveis_acima_do_alvo:
                    max_disponiveis_acima_do_alvo = len(alunos_candidatos)
                    melhor_slot = slot
                    melhor_grupo_candidato = alunos_candidatos
        
        if melhor_slot is None:
            print(f"AVISO: Não foi possível encontrar um slot com >= {tamanho_alvo} membros para o {i+1}º grupo. Buscando o slot com o máximo de candidatos disponíveis...")
            # Relaxamento: encontra o slot com o MÁXIMO de candidatos disponíveis (mesmo < alvo)
            max_disponiveis = 0
            for slot, alunos_disponiveis in mapa_disponibilidade.items():
                alunos_candidatos = alunos_nao_alocados.intersection(alunos_disponiveis)
                len_candidatos = len(alunos_candidatos)
                if len_candidatos > max_disponiveis:
                    max_disponiveis = len_candidatos
                    melhor_slot = slot
                    melhor_grupo_candidato = alunos_candidatos
            if melhor_slot is None or max_disponiveis == 0:
                print(f"ERRO: Não há mais slots disponíveis para o {i+1}º grupo.")
                continue
            tamanho_alvo = max_disponiveis  # Aloca o máximo possível neste slot
            
        # Seleciona os membros para o grupo a partir dos candidatos
        # Prioriza alunos com MENOS opções de disponibilidade (alunos "difíceis" primeiro)
        candidatos_ordenados = sorted(
            list(melhor_grupo_candidato),
            key=lambda a: opcoes_por_aluno[a]  # Ordena por número de opções (ascendente)
        )
        membros_do_grupo = set(candidatos_ordenados[:tamanho_alvo])
        
        grupos_formados.append({
            "Grupo": i + 1, "Dia": melhor_slot[0], "Horário": melhor_slot[1], "Membros": list(membros_do_grupo)
        })
        
        alunos_nao_alocados -= membros_do_grupo

    # --- 3.1. TENTATIVA DE ALOCAR RESTANTES ---
    # Se houver não alocados, tenta adicionar a grupos existentes se o slot permitir
    if alunos_nao_alocados:
        print("\nTentando alocar alunos restantes em grupos existentes...")
        for aluno in list(alunos_nao_alocados):
            alocado = False
            for grupo in grupos_formados:
                slot = (grupo['Dia'], grupo['Horário'])
                if aluno in mapa_disponibilidade.get(slot, set()):
                    grupo['Membros'].append(aluno)
                    alunos_nao_alocados.remove(aluno)
                    alocado = True
                    print(f"Aluno {aluno} adicionado ao {grupo['Grupo']}º grupo.")
                    break
            if not alocado:
                print(f"Aluno {aluno} não pôde ser adicionado a nenhum grupo existente.")

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