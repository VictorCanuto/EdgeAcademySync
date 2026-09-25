from extensions import db
from models.aluno import Aluno
from models.acompanhamento_aluno import AcompanhamentoAluno


TIPO_CODES = {
    'ac': 'AC',
    'psi': 'PSI',
    'ap': 'AP',
    'r': 'REALOCADO',
    'im': 'IMERSAO',
}

# Status que NÃO representam um compromisso/acompanhamento: aula comum
# marcada manualmente, ou o slot voltando a ficar livre.
STATUS_SEM_ACOMPANHAMENTO = ('class', 'free')


def eh_status_acompanhamento(novo_status):
    """True quando o status marcado na grade é um compromisso (AC/PSI/AP/
    Realocado/Imersão/personalizado) e deve ser espelhado em acompanhamentos_aluno."""
    if not novo_status:
        return False
    return novo_status not in STATUS_SEM_ACOMPANHAMENTO


def resolver_tipo(novo_status):
    """Mapeia o status curto usado pelo frontend ('ac', 'psi', ...) para o
    código salvo na coluna 'tipo'. Qualquer status fora do mapa conhecido
    (rótulo personalizado digitado pelo usuário) vira 'CUSTOM'."""
    return TIPO_CODES.get(novo_status, 'CUSTOM')


def _normalizar_nome(nome):
    return str(nome or '').replace('_', ' ').strip().lower()


def resolver_aluno_id(turma_id, aluno_key):
    """Busca o id do Aluno na turma"""
    alvo = _normalizar_nome(aluno_key)
    if not alvo:
        return None
    for a in Aluno.query.filter_by(turma_id=turma_id).all():
        if _normalizar_nome(a.nome) == alvo or _normalizar_nome(a.nome_custom) == alvo:
            return a.id
    return None


def salvar_acompanhamento(aluno_id, dia, horario, tipo, descricao):
    """Cria ou atualiza (upsert) o compromisso do aluno naquele slot."""
    if aluno_id is None:
        return
    existente = AcompanhamentoAluno.query.filter_by(
        aluno_id=aluno_id, dia=dia, horario=horario
    ).first()
    if existente:
        existente.tipo = tipo
        existente.descricao = descricao
    else:
        db.session.add(AcompanhamentoAluno(
            aluno_id=aluno_id,
            dia=dia,
            horario=horario,
            tipo=tipo,
            descricao=descricao,
        ))


def remover_acompanhamento(aluno_id, dia, horario):
    """Remove o compromisso do aluno naquele slot, se existir."""
    if aluno_id is None:
        return
    AcompanhamentoAluno.query.filter_by(
        aluno_id=aluno_id, dia=dia, horario=horario
    ).delete()


def remover_todos_do_aluno(aluno_id):
    """Remove todos os compromissos do aluno"""
    if aluno_id is None:
        return
    AcompanhamentoAluno.query.filter_by(aluno_id=aluno_id).delete()
