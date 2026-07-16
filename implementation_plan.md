# Plano de Implementação - Upload de PDFs e Criação de Turma na Página "Turmas"

Este plano detalha como integrar o upload de múltiplos PDFs diretamente no modal de criação da turma (disparado pelo botão `+ Nova turma` na página **Turmas**) e garantir que os dados sejam carregados imediatamente, permitindo entrar na turma depois e ver a planilha de alunos por dia de semana.

---

## Proposta de Alterações

### 1. Frontend

#### [MODIFY] [landing.html](file:///c:/Users/victo/OneDrive/Documents/Edge/AcademySync/edgesync/gerador_grupos/templates/landing.html)

##### A. Habilitar envio de arquivos no formulário do modal
Modificar o formulário do modal `#create-turma-modal` para aceitar o upload de arquivos binários (`enctype="multipart/form-data"`), adicionar o input invisível do seletor e configurar o botão *"Inserir PDFs"* para disparar o seletor.

* **Alteração do cabeçalho do formulário:**
  ```html
  <form action="{{ url_for('index') }}" method="POST" id="create-turma-form" enctype="multipart/form-data">
  ```
* **Alteração do botão e adição de input de arquivos:**
  ```html
  <!-- Input oculto para selecionar os PDFs -->
  <input type="file" id="home_pdf_files" name="pdf_files" multiple accept=".pdf" style="display: none;" onchange="handleHomePDFsSelect()">
  
  <!-- Botão Inserir PDFs que aciona o input oculto -->
  <button type="button" id="home_pdf_btn" onclick="document.getElementById('home_pdf_files').click()" class="btn btn-secondary" style="width: 100%; padding: 12px; font-weight: 600; font-size: 0.95rem; border-radius: 8px; border: 1px solid var(--border-color); background: transparent; color: var(--text-main); cursor: pointer;">
      Inserir Pdfs
  </button>
  ```

##### B. Scripts de controle do upload
Adicionar as lógicas de JavaScript no final do arquivo para gerenciar os arquivos carregados:
1. `handleHomePDFsSelect()`: Mostra a contagem de arquivos anexados no próprio botão (ex: *Inserir Pdfs (3 arquivo(s) selecionado(s))*), alterando a cor do botão para verde (`success`).
2. `closeCreateModal()`: Reseta o campo de arquivos ao fechar ou salvar para evitar envios indesejados.

* **Novas lógicas de script:**
  ```javascript
  function handleHomePDFsSelect() {
      const fileInput = document.getElementById('home_pdf_files');
      const btn = document.getElementById('home_pdf_btn');
      if (fileInput && fileInput.files.length > 0) {
          btn.textContent = `Inserir Pdfs (${fileInput.files.length} arquivo(s) selecionado(s))`;
          btn.style.borderColor = 'var(--color-success)';
          btn.style.color = 'var(--color-success)';
      } else {
          btn.textContent = 'Inserir Pdfs';
          btn.style.borderColor = 'var(--border-color)';
          btn.style.color = 'var(--text-main)';
      }
  }

  // Atualização no fechamento do modal
  const originalCloseCreateModal = closeCreateModal;
  closeCreateModal = function() {
      if (typeof originalCloseCreateModal === 'function') {
          originalCloseCreateModal();
      }
      const fileInput = document.getElementById('home_pdf_files');
      if (fileInput) fileInput.value = '';
      handleHomePDFsSelect();
  };
  ```

---

### 2. Backend

#### [MODIFY] [app.py](file:///c:/Users/victo/OneDrive/Documents/Edge/AcademySync/edgesync/gerador_grupos/app.py)

**O que será feito:** 
Modificar o tratamento do `action == 'create_turma'` na rota `index()` para ler os arquivos PDF enviados sob a chave `pdf_files`. Se houver arquivos:
1. Salva a nova `Turma` com o tipo adequado.
2. Armazena temporariamente os PDFs no disco e executa o parser `processar_pdfs_para_dataframe(filepaths)`.
3. Converte a planilha consolidada para CSV binário e salva no banco de dados no campo `Turma.base_data`.
4. Dispara a sincronização de alunos (`sincronizar_tabelas_dos_alunos`) para popular a tabela relacional de Alunos.
5. Exibe a mensagem de sucesso com a quantidade de alunos importada.

* **Código Proposto:**
  ```python
        if action == 'create_turma':
            nome = request.form.get('turma_nome', '').strip()
            tipo = request.form.get('turma_tipo', 'academy').strip()
            if not nome:
                flash('O nome da turma não pode ser vazio.', 'error')
                return redirect(url_for('index'))
                
            em_imersao = (tipo == 'imersao')
            new_turma = Turma(nome=nome, user_id=user.id, em_imersao=em_imersao)
            db.session.add(new_turma)
            db.session.commit() # Salva primeiro para gerar o ID
            
            # Processar PDFs se houver
            files = request.files.getlist('pdf_files')
            if files and files[0].filename != '':
                filepaths = []
                user_data_folder = get_user_data_folder()
                upload_folder_user = os.path.join(user_data_folder, 'uploads') if user_data_folder else 'uploads'
                os.makedirs(upload_folder_user, exist_ok=True)

                for file in files:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(upload_folder_user, filename)
                    file.save(filepath)
                    filepaths.append(filepath)
                
                base_df = processar_pdfs_para_dataframe(filepaths)
                
                # Limpar PDFs temporários
                try:
                    for fpath in filepaths:
                        if os.path.exists(fpath):
                            os.remove(fpath)
                except Exception as e:
                    print(f"AVISO: Falha ao limpar PDFs temporários: {e}")
                
                if base_df is not None and not base_df.empty:
                    csv_buffer = BytesIO()
                    base_df.to_csv(csv_buffer, index=False, encoding='utf-8')
                    new_turma.base_data = csv_buffer.getvalue()
                    db.session.commit()
                    
                    sincronizar_tabelas_dos_alunos(new_turma.id, base_df)
                    flash(f'Turma "{nome}" criada com {len(base_df["aluno"].unique())} alunos do(s) PDF(s) com sucesso!', 'success')
                else:
                    flash(f'Turma "{nome}" criada vazia. Não foi possível extrair dados dos PDFs.', 'warning')
            else:
                flash(f'Turma "{nome}" criada com sucesso!', 'success')
                
            return redirect(url_for('index'))
  ```

---

## Plano de Verificação

### Verificação Manual
1. Iniciar o servidor Flask localmente.
2. Na página **Turmas**, clicar no botão **+ Nova turma**.
3. No modal:
   - Digitar o nome: `Turma Engenharia Civil`.
   - Clicar em *"Inserir PDFs"* e selecionar 2 PDFs de horários de alunos.
   - Manter ou desmarcar a flag *"Em imersão"*.
   - Clicar em **Salvar**.
4. Verifique se o card da nova turma é gerado contendo o badge *"2 Aluno(s)"* (mostrando que foram criados com sucesso).
5. **Clique no card da turma recém-criada** e confirme que você é redirecionado para a página de detalhes, exibindo a planilha de horários por dia da semana e alunos cadastrados.
