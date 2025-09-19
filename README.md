# EdgeSync: Otimizador de Grupos
✨ Novas Funcionalidades no app.py:

Implementada agenda geral interativa com visualização completa da disponibilidade de alunos por horário. A nova feature permite ver quantos alunos estão livres em cada slot horário e clicar para listar quais alunos específicos estão disponíveis. Sistema de cores intuitivo onde tons mais verdes indicam maior disponibilidade para formação de grupos.
.
.

EdgeSync é uma ferramenta interna desenvolvida para o programa Edge Academy, com o objetivo de otimizar a formação de equipes de projeto. A aplicação automatiza o processo de análise de horários de múltiplos alunos e fornece uma interface interativa para identificar a disponibilidade em comum de qualquer grupo selecionado.

## 🎯 Sobre o Projeto
O principal desafio que este projeto resolve é a complexa tarefa de cruzar os horários de dezenas de alunos para formar grupos de estudo ou de projeto que tenham janelas de tempo compatíveis para se reunir. O processo, antes manual e suscetível a erros, é transformado em um fluxo de dados automatizado e uma ferramenta de visualização instantânea.

## ✨ Funcionalidades
* Extração Automática de Dados: Coleta de tabelas de horários diretamente de arquivos PDF de comprovantes de matrícula.

* Processamento e Limpeza: Consolida, limpa e padroniza os dados de múltiplos alunos em uma base de dados única e confiável.

* Interface Web Interativa: Uma aplicação web local, desenvolvida com Streamlit, para uma experiência de usuário amigável.

* Visualização Individual: Exibe a grade de horários de qualquer aluno selecionado, com um código de cores para horários disponíveis e ocupados.

* Cruzamento de Horários em Grupo: Permite a seleção de múltiplos alunos e gera uma grade de disponibilidade combinada, mostrando apenas os horários em que todos no grupo estão livres.

## 🛠️ Tecnologias Utilizadas
* Linguagem: Python 3.10+

* Bibliotecas Principais:

    * Pandas: Para manipulação, limpeza e estruturação de todos os dados.

    * Streamlit: Para a criação da interface web interativa.

    * Tabula-py: Para a extração das tabelas dos arquivos PDF.

    * OpenPyXL / XlsxWriter: Motores utilizados pelo Pandas para escrever os arquivos Excel.

    * re (Regex): Para a limpeza e padronização de strings de texto.

## ⚙️ Arquitetura do Projeto
O sistema funciona como um pipeline de dados em três etapas principais, cada uma representada por um script:

`PDFs` ➔ `reader.py` ➔ `consolidado_horarios.xlsx` ➔ `processador.py` ➔ `base_consolidada.csv` ➔ `app.py` ➔ `Interface Web`

1. `reader.py` (O Coletor):

    * Lê múltiplos arquivos PDF de uma pasta de entrada.

    * Extrai a tabela de horários de cada um.

    * Salva os dados brutos em um único arquivo Excel (consolidado_horarios.xlsx), onde cada aba corresponde a um aluno.

2. `processador.py` (O Organizador):

    * Lê o arquivo Excel gerado na etapa anterior.

    * Limpa, filtra e padroniza os dados, resolvendo inconsistências de formatação.

    * Transforma a estrutura dos dados para um formato ideal para análise.

    * Salva a base de dados final e limpa em base_consolidada.csv.

3. `app.py` (A Interface):

    * Lê a base de dados limpa (base_consolidada.csv).

    * Renderiza a interface web interativa com os menus de seleção.

    * Executa a lógica de cruzamento de horários e exibe as grades visuais para o usuário.

# 🚀 Como Executar o Projeto
Siga os passos abaixo para configurar e executar o projeto em sua máquina.

#### Pré-requisitos
* Python 3.10 ou superior instalado.

* Java JDK instalado (é uma dependência obrigatória da biblioteca tabula-py).

#### Instalação de Dependências
1. Clone o repositório (ou simplesmente tenha a pasta do projeto em sua máquina).

```
git clone https://github.com/lucasqtl/edgesync
cd edgesync
```

2. Crie e ative um ambiente virtual:

```
#Criar o ambiente
python -m venv venv

#Ativar no Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Ativar no macOS/Linux
source venv/bin/activate
```
3. Instale as bibliotecas necessárias:

O arquivo chamado requirements.txt possui as dependências utilizadas.

 Instale todas de uma vez com o comando:

```
pip install -r requirements.txt
```
### Execução Passo a Passo
* Passo 1: Coleta de Dados Brutos

Crie uma pasta chamada ALL_PDFS (ou o nome que preferir) e coloque todos os comprovantes de matrícula em PDF dentro dela.

No arquivo reader.py, certifique-se de que a variável pasta_dos_pdfs aponta para esta pasta.
```
python reader.py
```
Ao final, o arquivo consolidado_horarios.xlsx será criado.

* Passo 2: Processamento e Limpeza

Para os PDFs que o reader.py não conseguir processar, recomenda-se a criação de planilhas manuais.

Execute o script para gerar a base de dados final:

```
python processador.py
```
Ao final, o arquivo base_consolidada.csv estará pronto.

* Passo 3: Iniciar a Aplicação

Com a base de dados pronta, inicie a interface interativa:

```
streamlit run app.py
```
Uma aba será aberta no seu navegador com a aplicação pronta para uso.
