# Bot South Roleplay 🎮 creditos para thziim

Bot de Discord completo desenvolvido em Python para o servidor **South Roleplay**.

---

## 📌 Canais e Cargos Configurados

- **Painel de Atendimento:** 
- **Categoria dos Tickets:** 
- **Canal de Logs (.txt):**
- **Canal de Notas do Suporte:** `
- **Cargos de Suporte / Autorizados:**

---

## 🚀 Funcionalidades Completas

1. **Painel de Atendimento Interativo:**
   - Opções: **📱 Suporte APK** e **🤝 Parceria**.
   - Ao clicar, abre um formulário (Modal) para o usuário detalhar o problema ou proposta antes de criar o canal.
   - Os tickets são criados dentro da categoria configurada (`como id do canal `).
   - Visibilidade restrita exclusivamente ao cliente que abriu e aos cargos de suporte.

2. **Auto-Resposta Inteligente (10 Segundos):**
   - Caso nenhum membro da equipe de suporte responda nos primeiros 10 segundos, o bot envia uma saudação de acordo com o relógio de Brasília (*Bom dia*, *Boa tarde* ou *Boa noite*) avisando que a equipe pode estar ocupada e responderá o mais breve possível.

3. **Controle de Ticket & Avaliação (1 a 10):**
   - Botão **🔒 Finalizar Ticket**: Disponível para a equipe de suporte finalizar o atendimento.
   - Botão **🔔 Chamar Suporte**: Para alertar os membros da equipe.
   - **Menu de Avaliação (1 a 10):** Ao finalizar, o cliente seleciona sua nota e pode deixar um comentário opcional sobre a experiência.
   - **Logs em .txt:** Toda a conversa do canal é exportada em arquivo `.txt` e enviada:
     - No privado (DM) do cliente.
     - No canal de logs (`canala do codigo4`).
   - **Canal de Notas:** A nota de 1 a 10 e o comentário do cliente são enviados em Embed no canal de avaliações (`1canal da nota`).
   - **Regra dos 10 Minutos:** Se o cliente não responder a avaliação em até 10 minutos no canal, o bot envia os logs e a avaliação na DM dele e exclui o canal automaticamente. Se responder na hora, o canal é encerrado e deletado em 5 segundos.

4. **Sistema Anti-Link Automático:**
   - Bloqueia links de outros servidores Discord, canais/vídeos do YouTube e links externos em qualquer canal.
   - Apenas os cargos autorizados de suporte podem enviar links.

---

## ⚙️ Como Iniciar

1. Abra a pasta `c:\xampp\htdocs\BOT DO SOUTH ROLEPLAY`
2. Dê dois cliques no arquivo **`iniciar.bat`**.
