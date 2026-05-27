# Plano de Implementação: Banco de Dados, Hospedagem e Recuperação de Senha por E-mail

Este plano detalha as etapas necessárias para migrar o projeto **AcademySync** para um banco de dados persistente na nuvem, realizar a hospedagem gratuita na internet e implementar um sistema de recuperação de senha seguro via e-mail.

---

## 1. Integração de Banco de Dados Gratuito (Neon.tech - PostgreSQL)

Substituiremos o armazenamento em arquivo local `users.json` e a persistência temporária de arquivos de sessão (`CSV` e `Pickle` na pasta `session_data`) por um banco de dados **PostgreSQL** hospedado gratuitamente no **Neon.tech**, utilizando **Flask-SQLAlchemy** como ORM. 

### Por que salvar os dados de sessão no banco?
Como plataformas de hospedagem em nuvem gratuitas utilizam discos efêmeros (que apagam arquivos locais sempre que o servidor reinicia), guardar os CSVs e Pickles no disco local faria com que o usuário perdesse seus grupos criados diariamente. Salvando esses arquivos como campos binários (`BLOB`) diretamente no banco de dados vinculados ao usuário, garantimos que:
1. Os dados nunca se percam nos reinícios normais do servidor.
2. O usuário consiga acessar seu trabalho de qualquer computador ou rede após fazer o login.

### Passos a serem realizados:

1. **Atualizar dependências:**
   Adicionar no arquivo `gerador_grupos/requirements.txt`:
   ```text
   Flask-SQLAlchemy
   psycopg2-binary
   itsdangerous
   ```

2. **Criar a conta no Neon.tech:**
   * Acessar [neon.tech](https://neon.tech/) e criar uma conta grátis.
   * Criar um novo projeto e copiar a **Connection String** (URL de conexão que começa com `postgresql://...`).

3. **Modificar o código do Flask (`gerador_grupos/app.py`):**
   * Configurar o Flask-SQLAlchemy para carregar a URL do banco a partir de variáveis de ambiente (`DATABASE_URL`).
   * Adicionar um fallback automático para um banco SQLite local (`sqlite:///usuarios.db`) caso nenhuma URL na nuvem seja fornecida, permitindo desenvolvimento local offline.
   * Definir a tabela `User` no banco de dados com a seguinte estrutura:
     ```python
     class User(db.Model):
         id = db.Column(db.Integer, primary_key=True)
         username = db.Column(db.String(80), unique=True, nullable=False)
         email = db.Column(db.String(120), unique=True, nullable=False)
         password_hash = db.Column(db.String(256), nullable=False)
         
         # Campos para persistência de dados de sessão na nuvem (sem arquivos locais)
         base_data = db.Column(db.LargeBinary, nullable=True)      # Conteúdo do CSV consolidado
         groups_result = db.Column(db.LargeBinary, nullable=True)  # Dicionário do Pickle serializado
     ```
   * Adicionar a inicialização automática das tabelas executando `db.create_all()` dentro do contexto da aplicação Flask (`with app.app_context(): db.create_all()`) logo após a declaração do banco.
   * Adaptar as funções de registro (`/register`), login (`/login`) e alteração de senha (`/change_password`) para interagir com o banco de dados via ORM. A rota `/register` deve agora capturar e armazenar o campo `email`.
   * Modificar a lógica das rotas `/`, `/trocar_aluno`, `/clear`, `/download/csv`, `/download/pdf` e `/aluno/<nome_aluno>` para ler e salvar os dados diretamente nos campos `base_data` e `groups_result` do registro do usuário logado no banco de dados, eliminando completamente a leitura e escrita local de arquivos na pasta `session_data`.

4. **Modificar as Interfaces do Usuário (HTML):**
   * **[MODIFY] [register.html](file:///c:/Users/victo/OneDrive/Documents/Edge/AcademySync/edgesync/gerador_grupos/templates/register.html):** Adicionar um novo campo do tipo `email` obrigatório para o usuário inserir seu e-mail de contato no momento do cadastro.
   * **[MODIFY] [forgot_password.html](file:///c:/Users/victo/OneDrive/Documents/Edge/AcademySync/edgesync/gerador_grupos/templates/forgot_password.html):** Substituir o campo de entrada do nome de usuário pelo campo de `e-mail` cadastrado.
   * **[NEW] [reset_password.html](file:///c:/Users/victo/OneDrive/Documents/Edge/AcademySync/edgesync/gerador_grupos/templates/reset_password.html):** Criar uma nova interface de redefinição contendo formulário com dois campos: "Nova Senha" e "Confirmar Nova Senha".

---

## 2. Hospedagem Gratuita na Internet (Render.com)

Hospedaremos a aplicação Flask na plataforma **Render.com** na camada gratuita (Web Service).

### Passos a serem realizados:

1. **Adicionar servidor de produção:**
   Adicionar `gunicorn` em `gerador_grupos/requirements.txt` (usado para rodar a aplicação em produção).

2. **Configurar o Repositório Git:**
   * Inicializar/garantir o repositório git na pasta raiz do projeto.
   * Criar um repositório no GitHub (público ou privado) e subir o código.

3. **Configuração no Render.com:**
   * Acessar [render.com](https://render.com/), fazer login e criar um novo **Web Service**.
   * Conectar sua conta do GitHub e selecionar o repositório do projeto.
   * Configurar os parâmetros do Web Service:
     * **Root Directory:** `gerador_grupos` (isso indica que o aplicativo está dentro desta subpasta).
     * **Environment/Runtime:** `Python`.
     * **Build Command:** `pip install -r requirements.txt`.
     * **Start Command:** `gunicorn app:app`.
   * **Environment Variables (Variáveis de Ambiente):**
     * `DATABASE_URL`: Inserir a Connection String copiada do Neon.tech.
     * `SECRET_KEY`: Uma chave de segurança para assinar as sessões da aplicação.
     * Configurações de e-mail (detalhadas na seção 3).

---

## 3. Recuperação de Senha por E-mail

Substituiremos a lógica atual (que gera uma senha e exibe na tela) por um fluxo de redefinição de senha real e seguro via e-mail utilizando tokens expiráveis.

### Passos a serem realizados:

1. **Configurar o Serviço de E-mail (SMTP):**
   * Usaremos um servidor SMTP para enviar os e-mails de recuperação.
   * **Opção Recomendada (Grátis):** Criar uma conta gratuita no [Resend.com](https://resend.com/) ou usar uma conta Gmail pessoal configurando uma **Senha de App** (App Password).
   * As chaves de e-mail serão salvas em variáveis de ambiente:
     * `MAIL_SERVER` (ex: `smtp.gmail.com` ou `smtp.resend.com`)
     * `MAIL_PORT` (ex: `587` ou `465`)
     * `MAIL_USERNAME`
     * `MAIL_PASSWORD` (Senha de app)
     * `MAIL_DEFAULT_SENDER`

2. **Implementar a Lógica de Token de Redefinição:**
   * Utilizar a biblioteca `itsdangerous` (já instalada com o Flask) para gerar um token criptografado e seguro contendo o ID do usuário.
   * Definir que o token expire em **15 minutos**.

3. **Criar a Rota e o Formulário de Solicitação (`/forgot_password`):**
   * O usuário insere o e-mail cadastrado.
   * Se o e-mail existir no banco de dados, gera o token, monta o link (`https://seu-app.onrender.com/reset_password/<token>`) e envia por e-mail com instruções.

4. **Criar a Rota e Tela de Redefinição (`/reset_password/<token>`):**
   * Valida se o token não expirou e é legítimo.
   * Exibe um formulário para o usuário digitar a nova senha.
   * Atualiza a senha criptografada do usuário no banco de dados Neon.

---

## Plano de Verificação

### Testes Locais:
1. Validar a criação do banco local SQLite e as operações de registro/login de usuários.
2. Simular o upload de PDFs e a geração de grupos, verificando se os dados são salvos e carregados com sucesso diretamente a partir do banco de dados SQLite local, sem criar arquivos de sessão locais na pasta `session_data`.
3. Simular o envio de e-mails usando o modo debug do Flask ou um servidor SMTP de testes local (`python -m smtpd -n -c DebuggingServer localhost:1025`).
4. Testar a redefinição de senha garantindo que o link gerado expira após o tempo configurado.

### Testes em Produção:
1. Verificar a conexão bem-sucedida do servidor do Render com o banco do Neon.
2. Realizar login em navegadores ou computadores diferentes e certificar-se de que os dados e grupos gerados aparecem idênticos em ambos.
3. Solicitar uma recuperação de senha, verificar o recebimento do e-mail na caixa de entrada e concluir a redefinição.
