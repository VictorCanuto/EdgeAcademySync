# Proposta de Melhoria do Sistema AcademySync (Para Apresentação)

Este documento explica, de forma simples e direta (sem jargões técnicos), as melhorias que serão feitas no sistema **AcademySync** para torná-lo um site estável, seguro, profissional e livre de perda de dados, mantendo o custo zero de infraestrutura.

---

## O Objetivo das Melhorias
Atualmente, o AcademySync já possui um protótipo de apresentação rodando diretamente na internet de forma gratuita (atualmente utilizando o **Streamlit Community Cloud**), que lê o código do nosso repositório no **GitHub** e o transforma em uma página web.

No entanto, essa solução de apresentação gratuita possui duas grandes limitações que impedem seu uso profissional:
1. **Perda de Dados Constante:** Como o sistema atual salva as contas de usuários em um arquivo de texto local temporário (`users.json`), **toda vez que o servidor reinicia ou atualiza (o que ocorre automaticamente todos os dias na plataforma gratuita), todas as contas criadas e dados de grupos são completamente apagados**.
2. **Falta de Integração:** O site de testes atual não tem conexão com um banco de dados seguro, o que impede que diferentes computadores salvem e compartilhem as informações de forma definitiva.

Nosso objetivo é descontinuar esse protótipo temporário de apresentação e colocar o sistema **integralmente em um site web gratuito e estável de produção (utilizando a plataforma Render.com), conectado a um banco de dados profissional na nuvem**.

Para que isso seja viável e seguro, faremos três alterações fundamentais:

---

## 1. Banco de Dados na Nuvem: Nosso Arquivo Permanente e Seguro
* **O que é:** Um "cofre digital" permanente hospedado na internet, onde guardaremos as contas dos usuários e as informações dos grupos de forma segura.
* **Por que fazer assim:** Com o banco de dados na nuvem, as informações não dependem de arquivos locais temporários do servidor. Assim, mesmo que o site seja atualizado ou o servidor reinicie, os dados nunca serão perdidos. Isso garante que coordenadores de diferentes redes acessem e encontrem sempre os mesmos dados salvos.
* **Custo:** R$ 0,00 (usaremos uma plataforma profissional chamada Neon.tech na sua versão gratuita, que oferece espaço de sobra para o nosso uso).

## 2. Nova Hospedagem de Produção: Servidor Estável 24 horas
* **O que é:** Hospedar o sistema final de forma definitiva em um servidor profissional (Render.com), que também lê nosso repositório no GitHub, mas está preparado para rodar o aplicativo de forma estável, conectando-se de forma segura ao banco de dados Neon.
* **Por que fazer assim:** Isso nos permite migrar do protótipo atual do Streamlit para o sistema completo (Flask) de maneira robusta, garantindo que o site fique disponível 24 horas por dia com um link exclusivo e seguro (HTTPS).
* **Custo:** R$ 0,00.

## 3. Recuperação de Senha por E-mail: Segurança e Conveniência
* **O que é:** Um mecanismo idêntico ao de grandes sites da internet (como Netflix ou bancos). Se um usuário esquecer a senha, ele insere o seu e-mail cadastrado e recebe um link temporário e seguro em sua caixa de entrada para criar uma nova senha.
* **Por que fazer assim:** Atualmente, se um usuário esquece a senha, o sistema apenas exibe a senha diretamente na tela, o que não é seguro caso outra pessoa esteja por perto. Além disso, **ajustaremos a tela de cadastro para que o usuário informe seu e-mail ao criar a conta**, permitindo o envio automático do link de recuperação para a caixa de entrada dele com total privacidade.
* **Custo:** R$ 0,00 (utilizaremos conexões de e-mail seguras e sem custos).

---

## Benefícios Práticos para o Projeto
1. **Fim da Perda de Dados:** Os usuários não precisarão se cadastrar novamente toda vez que o servidor gratuito reiniciar.
2. **Acesso Remoto Confiável:** Qualquer coordenador ou usuário poderá acessar o gerador de grupos da sua própria casa ou de outra rede, compartilhando a mesma base de dados.
3. **Segurança da Informação:** As senhas dos usuários serão criptografadas e protegidas usando padrões modernos de segurança.
4. **Custo Zero:** Toda a infraestrutura proposta será mantida em planos gratuitos e profissionais de grandes empresas de tecnologia, sem necessidade de investimentos financeiros.

