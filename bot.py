import discord
from discord.ext import commands
import asyncio
import io
import re
from datetime import datetime, timezone, timedelta
import config

# Configuração de Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Fuso horário de Brasília (UTC-3)
TZ_BRASILIA = timezone(timedelta(hours=-3))

def get_saudacao():
    agora = datetime.now(TZ_BRASILIA)
    hora = agora.hour
    if 5 <= hora < 12:
        return "Bom dia"
    elif 12 <= hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"

# Expressão regular para detecção de links
LINK_REGEX = re.compile(
    r"(https?://[^\s]+|"
    r"www\.[^\s]+|"
    r"discord(?:\.gg|app\.com/invite|\.com/invite)/[^\s]+|"
    r"(?:youtube\.com|youtu\.be)/[^\s]+)",
    re.IGNORECASE
)

# Estrutura para controle de tickets ativos em memória
# channel_id: { "client_id": int, "tipo": str, "auto_replied": bool, "timer_task": Task, "staff_id": int }
active_tickets = {}

class SouthBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Registra views persistentes
        self.add_view(TicketLauncherView())
        self.add_view(TicketControlView())
        print("[SISTEMA] Views persistentes registradas com sucesso.")

bot = SouthBot()


# ==============================================================================
# FUNÇÃO PARA GERAR LOGS EM .TXT
# ==============================================================================

async def gerar_logs_txt(channel: discord.TextChannel) -> io.BytesIO:
    linhas = [
        "==================================================================",
        "             SOUTH ROLEPLAY - LOG DE ATENDIMENTO                  ",
        f" Canal: #{channel.name}",
        f" Tópico: {channel.topic or 'Não informado'}",
        f" Data: {datetime.now(TZ_BRASILIA).strftime('%d/%m/%Y %H:%M:%S')}",
        "==================================================================\n"
    ]
    try:
        async for msg in channel.history(limit=1000, oldest_first=True):
            data_str = msg.created_at.astimezone(TZ_BRASILIA).strftime("%d/%m/%Y %H:%M:%S")
            autor = f"{msg.author.name} (ID: {msg.author.id})"
            conteudo = msg.clean_content or "[Sem texto]"
            if msg.attachments:
                anexos_urls = ", ".join([att.url for att in msg.attachments])
                conteudo += f" [Anexos: {anexos_urls}]"
            linhas.append(f"[{data_str}] {autor}: {conteudo}")
    except Exception as e:
        linhas.append(f"\n[Erro ao exportar parte das mensagens: {e}]")

    buffer = io.BytesIO("\n".join(linhas).encode("utf-8"))
    buffer.seek(0)
    return buffer


# ==============================================================================
# MODAIS PARA ABERTURA DE TICKET
# ==============================================================================

class TicketModal(discord.ui.Modal):
    def __init__(self, tipo: str):
        titulo = "Suporte APK" if tipo == "apk" else "Proposta de Parceria"
        super().__init__(title=f"{titulo} - South Roleplay")
        self.tipo = tipo

        if tipo == "apk":
            self.campo = discord.ui.TextInput(
                label="Qual é o seu problema ou dúvida com o APK?",
                style=discord.TextStyle.paragraph,
                placeholder="Explique detalhadamente o erro, aparelho ou dúvida...",
                required=True,
                max_length=1000
            )
        else:
            self.campo = discord.ui.TextInput(
                label="Qual tipo de parceria você quer fazer?",
                style=discord.TextStyle.paragraph,
                placeholder="Descreva seu canal/projeto, proposta e condições...",
                required=True,
                max_length=1000
            )

        self.add_item(self.campo)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        if not guild:
            await interaction.response.send_message("Comando apenas em servidores.", ephemeral=True)
            return

        # Checa se o usuário já tem ticket aberto
        for ch in guild.text_channels:
            if ch.topic and f"Ticket do usuário ID: {user.id}" in ch.topic:
                await interaction.response.send_message(
                    f"⚠️ Você já possui um atendimento em andamento em {ch.mention}!",
                    ephemeral=True
                )
                return

        # Categoria de tickets
        categoria = guild.get_channel(config.CATEGORIA_TICKETS_ID)

        # Configura as permissões
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True
            )
        }

        cargos_mencionados = []
        for role_id in config.CARGOS_SUPORTE_IDS:
            role = guild.get_role(role_id)
            if role:
                cargos_mencionados.append(role.mention)
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )

        prefixo = "apk" if self.tipo == "apk" else "parceria"
        nome_canal = f"{prefixo}-{user.name}".lower()

        try:
            ticket_channel = await guild.create_text_channel(
                name=nome_canal,
                category=categoria,
                overwrites=overwrites,
                topic=f"Ticket do usuário ID: {user.id} | Tipo: {self.tipo.upper()}",
                reason=f"Ticket de {self.tipo.upper()} aberto por {user} ({user.id})"
            )

            # Registra ticket ativo
            active_tickets[ticket_channel.id] = {
                "client_id": user.id,
                "tipo": self.tipo,
                "auto_replied": False,
                "staff_id": None
            }

            await interaction.response.send_message(
                f"✅ Seu ticket foi criado com sucesso! Acesse: {ticket_channel.mention}",
                ephemeral=True
            )

            # Embed inicial no canal criado
            tipo_formatado = "Suporte no APK 📱" if self.tipo == "apk" else "Parceria 🤝"
            embed = discord.Embed(
                title=f"🎟️ Atendimento - {tipo_formatado}",
                description=(
                    f"Olá {user.mention}, bem-vindo ao suporte oficial do **South Roleplay**!\n\n"
                    f"📌 **Detalhes da Solicitação:**\n"
                    f"```{self.campo.value}```\n"
                    "Nossa equipe foi notificada e irá te atender em breve.\n"
                    "Use os botões abaixo para gerenciar este ticket."
                ),
                color=discord.Color.from_rgb(0, 150, 255)
            )
            embed.set_footer(text="South Roleplay • Atendimento")
            embed.timestamp = datetime.now(timezone.utc)

            mencoes = f"{user.mention} " + " ".join(cargos_mencionados) if cargos_mencionados else user.mention
            await ticket_channel.send(content=mencoes, embed=embed, view=TicketControlView())

            # Inicia verificação de 10 segundos para resposta automática
            asyncio.create_task(agendar_resposta_automatica(ticket_channel.id, user.id))

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ O bot não tem permissão para criar canais na categoria informada.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Erro ao criar ticket: {e}",
                ephemeral=True
            )


# ==============================================================================
# PAINEL PRINCIPAL DE TICKETS (LANÇADOR)
# ==============================================================================

class TicketLauncherView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Suporte APK",
        style=discord.ButtonStyle.primary,
        emoji="📱",
        custom_id="south_btn_abrir_apk"
    )
    async def btn_apk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal(tipo="apk"))

    @discord.ui.button(
        label="Parceria",
        style=discord.ButtonStyle.secondary,
        emoji="🤝",
        custom_id="south_btn_abrir_parceria"
    )
    async def btn_parceria(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal(tipo="parceria"))


# ==============================================================================
# CONTROLES INTERNOS DO TICKET (FINALIZAR / CHAMAR SUPORTE)
# ==============================================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Finalizar Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="south_btn_finalizar_ticket"
    )
    async def btn_finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_roles = [r.id for r in interaction.user.roles]
        eh_suporte = any(role_id in user_roles for role_id in config.CARGOS_SUPORTE_IDS)
        eh_admin = interaction.user.guild_permissions.administrator

        if not (eh_suporte or eh_admin):
            await interaction.response.send_message(
                "❌ Apenas membros da equipe de suporte podem finalizar o ticket.",
                ephemeral=True
            )
            return

        canal = interaction.channel
        t_data = active_tickets.get(canal.id, {})
        client_id = t_data.get("client_id")

        if not client_id and canal.topic:
            match = re.search(r"ID:\s*(\d+)", canal.topic)
            if match:
                client_id = int(match.group(1))

        cliente = canal.guild.get_member(client_id) if client_id else None

        if t_data:
            t_data["staff_id"] = interaction.user.id

        await interaction.response.send_message(
            f"🔒 Atendimento finalizado por {interaction.user.mention}. Aguardando a avaliação do cliente...",
            ephemeral=False
        )

        # Envia a view de avaliação no canal para o cliente
        view_avaliacao = AvaliacaoView(
            client_id=client_id,
            staff_member=interaction.user,
            channel=canal
        )

        mencao_cliente = cliente.mention if cliente else "Cliente"
        msg_avaliacao = await canal.send(
            content=f"⭐ {mencao_cliente}, seu atendimento foi finalizado! Por favor, selecione uma nota de 1 a 10 abaixo para avaliar nosso suporte:",
            view=view_avaliacao
        )
        view_avaliacao.message = msg_avaliacao

        # Inicia a contagem de 10 minutos (600s) caso o cliente não responda no canal
        asyncio.create_task(timeout_avaliacao_10_minutos(canal, cliente, interaction.user, view_avaliacao))

    @discord.ui.button(
        label="Chamar Suporte",
        style=discord.ButtonStyle.secondary,
        emoji="🔔",
        custom_id="south_btn_chamar_suporte"
    )
    async def btn_chamar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Envia aviso marcando os cargos de suporte
        cargos_mencoes = [f"<@&{r_id}>" for r_id in config.CARGOS_SUPORTE_IDS]
        msg = " ".join(cargos_mencoes) if cargos_mencoes else "@here"
        await interaction.response.send_message(
            f"🔔 {interaction.user.mention} solicitou a presença do suporte aqui! {msg}",
            ephemeral=False
        )


# ==============================================================================
# RESPOSTA AUTOMÁTICA EM 10 SEGUNDOS (SAUDAÇÃO INTELIGENTE)
# ==============================================================================

async def agendar_resposta_automatica(channel_id: int, client_id: int):
    # Aguarda 10 segundos
    await asyncio.sleep(10)

    t_data = active_tickets.get(channel_id)
    if not t_data or t_data.get("auto_replied", False):
        return

    canal = bot.get_channel(channel_id)
    if not canal:
        return

    # Verifica se algum membro do suporte já falou
    suporte_falou = False
    try:
        async for msg in canal.history(limit=15):
            if msg.author.bot:
                continue
            author_roles = [r.id for r in msg.author.roles] if hasattr(msg.author, "roles") else []
            if any(r in author_roles for r in config.CARGOS_SUPORTE_IDS):
                suporte_falou = True
                break
    except Exception:
        pass

    if not suporte_falou and not t_data.get("auto_replied", False):
        t_data["auto_replied"] = True
        saudacao = get_saudacao()
        user_mention = f"<@{client_id}>"

        msg_auto = (
            f"👋 {saudacao}, {user_mention}!\n\n"
            "Normalmente nós atendemos o mais rápido possível, mas no momento nossa equipe pode "
            "estar atendendo outro cliente ou resolvendo outro problema.\n"
            "Assim que possível entraremos em contato com você aqui neste canal!"
        )
        try:
            await canal.send(msg_auto)
        except Exception as e:
            print(f"[AVISO] Falha ao enviar resposta automática: {e}")


# ==============================================================================
# SISTEMA DE AVALIAÇÃO (NOTA 1 A 10 + COMENTÁRIO OPCIONAL)
# ==============================================================================

class ModalComentario(discord.ui.Modal):
    def __init__(self, nota: int, client_id: int, staff_member: discord.Member, channel: discord.TextChannel):
        super().__init__(title=f"Avaliação: Nota {nota}/10 ⭐")
        self.nota = nota
        self.client_id = client_id
        self.staff_member = staff_member
        self.channel = channel

        self.comentario = discord.ui.TextInput(
            label="Comentário sobre sua experiência (Opcional):",
            style=discord.TextStyle.paragraph,
            placeholder="Digite aqui seu feedback, sugestão ou elogio (opcional)...",
            required=False,
            max_length=500
        )
        self.add_item(self.comentario)

    async def on_submit(self, interaction: discord.Interaction):
        comentario_texto = self.comentario.value.strip() or "Nenhum comentário adicionado."
        await interaction.response.send_message("✅ Obrigado pela sua avaliação!", ephemeral=True)
        await processar_finalizacao(
            channel=self.channel,
            client=interaction.user,
            staff=self.staff_member,
            nota=self.nota,
            comentario=comentario_texto
        )


class AvaliacaoSelect(discord.ui.Select):
    def __init__(self, client_id: int, staff_member: discord.Member, channel: discord.TextChannel):
        options = [
            discord.SelectOption(label=f"Nota {i}", value=str(i), emoji="⭐", description=f"Avaliação {i} de 10")
            for i in range(1, 11)
        ]
        super().__init__(
            placeholder="Selecione sua nota de 1 a 10...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_nota_atendimento"
        )
        self.client_id = client_id
        self.staff_member = staff_member
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.client_id:
            await interaction.response.send_message(
                "❌ Apenas o cliente que abriu este atendimento pode enviar a nota de avaliação.",
                ephemeral=True
            )
            return

        nota_escolhida = int(self.values[0])
        # Abre o modal para comentário opcional
        modal = ModalComentario(
            nota=nota_escolhida,
            client_id=self.client_id,
            staff_member=self.staff_member,
            channel=self.channel
        )
        await interaction.response.send_modal(modal)


class AvaliacaoView(discord.ui.View):
    def __init__(self, client_id: int, staff_member: discord.Member, channel: discord.TextChannel):
        super().__init__(timeout=600)  # 10 minutos
        self.client_id = client_id
        self.staff_member = staff_member
        self.channel = channel
        self.finalizado = False
        self.message = None
        self.add_item(AvaliacaoSelect(client_id, staff_member, channel))


# Timeout de 10 minutos caso o cliente não responda
async def timeout_avaliacao_10_minutos(channel: discord.TextChannel, client: discord.Member, staff: discord.Member, view: AvaliacaoView):
    await asyncio.sleep(600)  # 10 minutos
    if view.finalizado or channel.id not in active_tickets:
        return

    # Passaram 10 minutos sem resposta:
    print(f"[TIMEOUT] Cliente não respondeu a avaliação em 10 minutos no canal #{channel.name}.")
    await processar_finalizacao(
        channel=channel,
        client=client,
        staff=staff,
        nota=None,
        comentario=None,
        enviar_dm_para_avaliar=True
    )


# ==============================================================================
# PROCESSAMENTO DE FINALIZAÇÃO (LOGS, CANAL DE NOTAS, DM E EXCLUSÃO)
# ==============================================================================

async def processar_finalizacao(channel: discord.TextChannel, client: discord.Member, staff: discord.Member, nota: int = None, comentario: str = None, enviar_dm_para_avaliar: bool = False):
    if channel.id in active_tickets:
        active_tickets.pop(channel.id, None)

    # 1. Gera o arquivo de logs em .txt
    try:
        buffer_logs = await gerar_logs_txt(channel)
        file_logs_guild = discord.File(fp=buffer_logs, filename=f"logs-{channel.name}.txt")
    except Exception as e:
        print(f"[ERRO] Falha ao gerar buffer de logs: {e}")
        file_logs_guild = None

    # 2. Envia logs para o canal de logs configurado
    canal_logs = bot.get_channel(config.CANAL_LOGS_ID)
    if canal_logs and file_logs_guild:
        try:
            embed_log = discord.Embed(
                title="📋 Logs de Atendimento Finalizado",
                description=(
                    f"**Canal:** #{channel.name}\n"
                    f"**Cliente:** {client.mention if client else 'Desconhecido'} ({client.id if client else 'N/A'})\n"
                    f"**Atendente:** {staff.mention if staff else 'Sistema'}\n"
                    f"**Data:** {datetime.now(TZ_BRASILIA).strftime('%d/%m/%Y %H:%M:%S')}"
                ),
                color=discord.Color.dark_blue()
            )
            await canal_logs.send(embed=embed_log, file=file_logs_guild)
        except Exception as e:
            print(f"[ERRO] Falha ao enviar logs para o canal de logs: {e}")

    # 3. Se houver nota, envia no canal de avaliações
    if nota is not None:
        canal_notas = bot.get_channel(config.CANAL_AVALIACOES_ID)
        if canal_notas:
            try:
                estrelas = "⭐" * nota
                embed_nota = discord.Embed(
                    title="🌟 Nova Avaliação de Atendimento",
                    description=(
                        f"**Cliente:** {client.mention if client else 'N/A'}\n"
                        f"**Atendente:** {staff.mention if staff else 'N/A'}\n"
                        f"**Nota:** `{nota}/10` {estrelas}\n"
                        f"**Comentário:**\n```{comentario or 'Sem comentário'}```"
                    ),
                    color=discord.Color.gold()
                )
                embed_nota.set_footer(text="South Roleplay • Sistema de Avaliações")
                embed_nota.timestamp = datetime.now(timezone.utc)
                await canal_notas.send(embed=embed_nota)
            except Exception as e:
                print(f"[ERRO] Falha ao postar nota no canal de notas: {e}")

    # 4. Envia logs no privado (DM) do cliente
    if client:
        try:
            buffer_dm = await gerar_logs_txt(channel)
            file_dm = discord.File(fp=buffer_dm, filename=f"logs-{channel.name}.txt")

            embed_dm = discord.Embed(
                title="📄 Atendimento Concluído - South Roleplay",
                description=(
                    f"Olá {client.name}, seu ticket no **South Roleplay** foi encerrado.\n"
                    "Em anexo você encontra a transcrição completa da sua conversa com o suporte em formato `.txt`."
                ),
                color=discord.Color.blue()
            )

            if enviar_dm_para_avaliar:
                embed_dm.description += (
                    "\n\n⚠️ Como você não respondeu a avaliação no canal a tempo, você pode "
                    "avaliar o atendimento diretamente por aqui se desejar!"
                )
                view_dm = AvaliacaoDMView(client_id=client.id, staff_member=staff)
                await client.send(embed=embed_dm, file=file_dm, view=view_dm)
            else:
                await client.send(embed=embed_dm, file=file_dm)

        except discord.Forbidden:
            print(f"[AVISO] Não foi possível enviar DM para o cliente {client} (DM fechada).")
        except Exception as e:
            print(f"[AVISO] Erro ao enviar mensagem privada para o cliente: {e}")

    # 5. Avisa no canal e exclui em 5 segundos
    try:
        await channel.send("✅ Atendimento concluído! Este canal será excluído em **5 segundos**...")
        await asyncio.sleep(5)
        await channel.delete(reason="Ticket finalizado com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao deletar canal do ticket: {e}")


# View para avaliação tardia recebida na DM
class AvaliacaoDMView(discord.ui.View):
    def __init__(self, client_id: int, staff_member: discord.Member):
        super().__init__(timeout=86400)  # 24h
        self.client_id = client_id
        self.staff_member = staff_member
        options = [
            discord.SelectOption(label=f"Nota {i}", value=str(i), emoji="⭐")
            for i in range(1, 11)
        ]
        select = discord.ui.Select(
            placeholder="Clique aqui para deixar sua nota de 1 a 10...",
            options=options,
            custom_id="select_nota_dm"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        nota = int(interaction.data["values"][0])
        canal_notas = bot.get_channel(config.CANAL_AVALIACOES_ID)
        if canal_notas:
            try:
                estrelas = "⭐" * nota
                embed_nota = discord.Embed(
                    title="🌟 Nova Avaliação de Atendimento (Enviada via DM)",
                    description=(
                        f"**Cliente:** {interaction.user.mention}\n"
                        f"**Atendente:** {self.staff_member.mention if self.staff_member else 'N/A'}\n"
                        f"**Nota:** `{nota}/10` {estrelas}\n"
                        f"**Comentário:**\n```Enviado via mensagem privada sem comentário adicional```"
                    ),
                    color=discord.Color.gold()
                )
                embed_nota.set_footer(text="South Roleplay • Sistema de Avaliações")
                await canal_notas.send(embed=embed_nota)
            except Exception as e:
                print(f"[ERRO] Falha ao enviar nota da DM: {e}")

        await interaction.response.send_message("✅ Obrigado pela sua avaliação! Foi registrada com sucesso.", ephemeral=True)
        self.stop()


# ==============================================================================
# EVENTO ON_READY (INICIALIZAÇÃO E PAINEL)
# ==============================================================================

@bot.event
async def on_ready():
    print(f"==================================================")
    print(f"  Bot Conectado como: {bot.user} (ID: {bot.user.id})")
    print(f"  Servidores Conectados: {len(bot.guilds)}")
    print(f"==================================================")

    canal = bot.get_channel(config.CANAL_TICKET_ID)
    if canal is None:
        try:
            canal = await bot.fetch_channel(config.CANAL_TICKET_ID)
        except Exception:
            canal = None

    if not canal:
        print(f"[AVISO] Não foi possível encontrar o canal de ticket com ID: {config.CANAL_TICKET_ID}")
        return

    # Procura se a mensagem do painel já existe no canal
    ja_existe = False
    try:
        async for msg in canal.history(limit=50):
            if msg.author.id == bot.user.id and msg.embeds:
                for embed in msg.embeds:
                    if embed.title and "Suporte South Roleplay" in embed.title:
                        ja_existe = True
                        break
            if ja_existe:
                break
    except Exception as e:
        print(f"[AVISO] Erro ao verificar histórico do canal de ticket: {e}")

    if ja_existe:
        print(f"[OK] Painel de Tickets já se encontra ativo no canal #{canal.name}.")
    else:
        embed_painel = discord.Embed(
            title="🎫 Suporte South Roleplay",
            description=(
                "Precisa de ajuda ou deseja propor uma parceria com o **South Roleplay**?\n\n"
                "📌 **Escolha uma das opções abaixo para abrir seu atendimento:**\n\n"
                "📱 **Suporte APK:** Para problemas de conexão, bugs, dúvidas e auxílio no APK.\n"
                "🤝 **Parceria:** Para propostas de canais, criadores de conteúdo e projetos.\n\n"
                "⚠️ *Abra apenas um ticket por assunto e aguarde pacientemente ser atendido.*"
            ),
            color=discord.Color.from_rgb(255, 140, 0)
        )
        if canal.guild.icon:
            embed_painel.set_thumbnail(url=canal.guild.icon.url)
        embed_painel.set_footer(text="South Roleplay • Atendimento ao Jogador")

        try:
            await canal.send(embed=embed_painel, view=TicketLauncherView())
            print(f"[SUCESSO] Painel de tickets enviado com sucesso no canal #{canal.name} ({canal.id})!")
        except Exception as e:
            print(f"[ERRO] Falha ao enviar o painel no canal: {e}")


# ==============================================================================
# MODERAÇÃO ANTI-LINK E MONITORAMENTO DE RESPOSTA NO TICKET
# ==============================================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    # 1. Moderação Anti-Link
    user_roles_ids = [role.id for role in message.author.roles]
    tem_permissao = any(role_id in user_roles_ids for role_id in config.CARGOS_SUPORTE_IDS)

    if not tem_permissao:
        if LINK_REGEX.search(message.content):
            try:
                await message.delete()
                aviso = await message.channel.send(
                    f"🚫 {message.author.mention}, você **não tem permissão** para divulgar links (Discord, YouTube ou links externos) neste servidor! Apenas a equipe autorizada pode enviar links."
                )
                await asyncio.sleep(6)
                await aviso.delete()
            except discord.Forbidden:
                print(f"[PERMISSÃO] Sem permissão para apagar mensagens no canal #{message.channel.name}")
            except Exception as e:
                print(f"[AVISO] Erro na moderação de link: {e}")
            return

    # 2. Se for uma mensagem de suporte dentro de um ticket ativo, marca que o suporte atendeu
    if message.channel.id in active_tickets and tem_permissao:
        active_tickets[message.channel.id]["auto_replied"] = True

    await bot.process_commands(message)


# ==============================================================================
# INICIALIZAÇÃO DO BOT
# ==============================================================================

if __name__ == "__main__":
    if not config.TOKEN or config.TOKEN == "SEU_TOKEN_AQUI":
        print("[ERRO] Defina o TOKEN do bot no arquivo config.py antes de iniciar!")
    else:
        print("[INICIANDO] Conectando o bot ao Discord...")
        try:
            bot.run(config.TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "="*70)
            print("❌ ERRO: Privileged Intents desativados no Discord Developer Portal!")
            print("1. Acesse: https://discord.com/developers/applications")
            print("2. Clique no seu Bot -> Menu lateral 'Bot'")
            print("3. Ative as opções sob 'Privileged Gateway Intents':")
            print("   - [X] MESSAGE CONTENT INTENT")
            print("   - [X] SERVER MEMBERS INTENT")
            print("4. Clique em 'Save Changes' e inicie o bot novamente.")
            print("="*70 + "\n")
        except Exception as e:
            print(f"[ERRO AO INICIAR]: {e}")
