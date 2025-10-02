# services/__init__.py
from .pdf_reader import ler_pdfs_para_excel
from .pdf_processor import processar_excel, criar_base_de_dados_consolidada
from .pdf_parser import processar_pdfs_para_dataframe, processar_pdfs_para_dataframe_original

# Importe as outras funções que o app.py precisa
try:
    from .group_generator import formar_grupos
except ImportError:
    print("Aviso: group_generator não encontrado")

try:
    from .group_manager import sugerir_trocas, executar_troca
except ImportError:
    print("Aviso: group_manager não encontrado")

try:
    from .analytics_manager import calcular_ranking_disponibilidade
except ImportError:
    print("Aviso: analytics_manager não encontrado")

__all__ = [
    'ler_pdfs_para_excel',
    'processar_excel', 
    'criar_base_de_dados_consolidada',
    'processar_pdfs_para_dataframe',
    'processar_pdfs_para_dataframe_original',
    'formar_grupos',
    'sugerir_trocas', 
    'executar_troca',
    'calcular_ranking_disponibilidade'
]