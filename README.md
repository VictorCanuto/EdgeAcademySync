# AcademySync — Edge Academy Study Groups

O **AcademySync** é uma plataforma corporativa avançada desenvolvida para gerenciar, extrair dados e agrupar estudantes da **Edge Academy** em grupos de estudo baseados em compatibilidade de horários. O sistema elimina processos manuais e complexidades de agendamento através de algoritmos heurísticos rápidos de correspondência de agenda.

---

## 🚀 Principais Funcionalidades

### 1. Painel de Controle Multiturmas (Landing Page)
- Criação, edição e exclusão de **Turmas** independentes.
- Cada turma atua como um workspace isolado (banco de dados, arquivos e resultados segregados).
- Indicadores visuais rápidos nos cards das turmas (ex: contagem de alunos e grupos ativos).

### 2. Upload e Processamento de Atestados (PDF)
- Leitura automatizada das grades horárias extraídas diretamente dos PDFs de matrícula dos alunos.
- Processador nativo em Python (`pypdf`), livre de dependências externas como Java.
- **Barra de progresso de upload em tempo real** no frontend com feedbacks de status dedicados.

### 3. Gerador Heurístico de Grupos de Estudo
- Agrupamento instantâneo (em menos de **0,01s**) com base na intersecção de janelas livres dos alunos.
- Lógica inteligente que calcula a distribuição balanceada de estudantes por grupo.
- Editor de grade flexível para adicionar, remover e renomear grupos sob demanda.

### 4. Interface Interativa Premium (Workspace)
- Workspace completo no estilo *Glassmorphism* com blurs e degradês sofisticados.
- Planilha dinâmica interativa para verificação rápida de conflitos de horário.
- Quadro Kanban interativo com recurso de *drag-and-drop* (arrastar e soltar) para transferir alunos entre grupos de forma manual.
- Gaveta lateral de pendências e notificações (Alerts Drawer).
- Suporte nativo a **Modo Escuro (Dark Mode)** persistido localmente.

### 5. Autenticação e Segurança
- Cadastro e login seguros com confirmação de senha obrigatória no registro.
- Botões com ícones de olho (mostrar/ocultar) integrados a todos os campos de senha.
- **Perguntas de Segurança (Security Questions) Autônomas:** Fluxo integrado para redefinição de senha seguro, independente de servidores de e-mail de terceiros (SMTP).

---

## 🛠️ Stack Tecnológica

- **Backend:** Python, Flask, SQLAlchemy (ORMs e Migrações Dinâmicas).
- **Frontend:** Vanilla HTML5, CSS3 (Design System baseado em variáveis e CSS Grid/Flexbox) e Vanilla Javascript (ES6+).
- **Processamento de Dados:** Pandas, PyPDF, NumPy.
- **Geração de Arquivos:** ReportLab (Exportação em PDF), CSV.
- **Banco de Dados:** SQLite (Desenvolvimento local) e PostgreSQL (Produção no Neon).

---

## 💻 Como Rodar o Projeto Localmente

Siga os passos abaixo para preparar o ambiente e rodar o projeto na sua máquina de desenvolvimento:

### Pré-requisitos
- Python instalado na versão **3.10** ou superior.
- Git instalado.

### Passo 1: Clonar o Repositório
```bash
git clone https://github.com/VictorCanuto/edgesync.git
cd edgesync
```

### Passo 2: Configurar o Ambiente Virtual (venv)
Crie um ambiente isolado para instalar as dependências do projeto:

- **No Windows (PowerShell/CMD):**
  ```powershell
  python -m venv .venv
  ```
- **No Linux/macOS:**
  ```bash
  python3 -m venv .venv
  ```

### Passo 3: Ativar o Ambiente Virtual
- **No Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **No Windows (CMD):**
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **No Linux/macOS:**
  ```bash
  source .venv/bin/activate
  ```

### Passo 4: Instalar as Dependências
Instale todos os pacotes requeridos listados no gerenciador de pacotes:
```bash
pip install -r gerador_grupos/requirements.txt
```

### Passo 5: Iniciar o Servidor Local
Execute o script principal do Flask para rodar a aplicação:
```bash
python gerador_grupos/app.py
```
O servidor local iniciará na porta `5000`. Acesse:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 👥 Colaboração e Testes na Rede Local (LAN)

Como o servidor local é iniciado ouvindo todas as interfaces (`host='0.0.0.0'`), seus colegas de equipe podem acessar o seu servidor local estando conectados no mesmo Wi-Fi/Rede.

1. Descubra o IP local da sua máquina (`ipconfig` no Windows ou `ifconfig` no Linux).
2. Peça para o colega acessar o endereço no navegador substituindo por seu IP:
   `http://<SEU_IP_LOCAL>:5000` (Ex: `http://192.168.1.15:5000`).

---

## 🧪 Como Rodar Testes de Integração
Para garantir que as alterações no código não quebraram nenhuma funcionalidade crítica antes de enviar para o repositório remoto:
```bash
python test_app_integration.py
```
Aguarde a execução de todo o fluxo. Se todas as validações forem bem-sucedidas, a mensagem `[SUCCESS] TODOS OS TESTES PASSARAM COM SUCESSO!` será exibida.
