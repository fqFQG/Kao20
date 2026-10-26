import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
import random
import json
import os
import sys
import asyncio
import aiohttp
from pathlib import Path

# ══════════════════════════════════════════════════
#                   CONFIGURACIÓN
# ══════════════════════════════════════════════════

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERROR FATAL: No se encontró DISCORD_TOKEN en las variables de entorno.")
    sys.exit(1)

API_SECRET = os.environ.get("API_SECRET", "abc12345spitermanr")

NICK_ALLOWED_IDS = {
    263778453675966464,
    1060919120343859211,
    1401228905762918602,
    872307224549150751,
    1116589477478006794,
}

PALABRAS = [
    "Hi", "P no sabe balancear", "2 Pings a Moyo para PD",
    "Llevo 24 horas sin jugar Ghoul: Kao", "Que tan giveado esta Noc?",
    "Qué recuerdos cuando Leon no era giveado", "Que bueno que Jade se fue, me tenia de esclavo",
    "Semigamer al final hizo algo? Aparte de hablar basura", "Take, calvo.",
    "Que hace el gobierno?", "Sigma boy", "El SP Reset no es real",
    "La reputacion de la CCG es una mierda.",
]

PD_ROLE_ID     = 1445639262446817380
MEMBER_ROLE_ID = 1478506758388584569
REP_ROLES      = {1445637786081165412, 1445637691042566254, 1445637435638681691}
MSG_ROLE_ID    = 1445637435638681691
REP_CHANNEL_ID = 1451799073769263206
STAFF_ROLE_ID  = 1445638316547510303
OWNER_ROLE_ID  = 1445637435638681691

INVITE_LINK = "https://discord.gg/EVWsSVsTdG"
DATA_FILE = "bot_data.json"

DURACIONES_BAN = {
    "1 hora":   3600, "6 horas":  21600, "12 horas": 43200,
    "1 día":    86400, "3 días":   259200, "1 semana": 604800,
}

DURACION_CHOICES = [
    app_commands.Choice(name=nombre, value=segundos)
    for nombre, segundos in DURACIONES_BAN.items()
]

BOT_DATA = {
    "pd_count": 0, 
    "ccg_rep": 100.0, 
    "pago_pendiente": False, 
    "nicknames": {},           
    "active_nicknames": {},    
    "embeds": {},              
    "state_cache": {} 
}

SALARIOS: dict[str, int] = {
    "Initiate":                               160_000,
    "Grade 3 Rookie":                         190_000,
    "Grade 2 Rookie":                         220_000,
    "Grade 1 Rookie":                         260_000,
    "Junior Rank 3 Investigator":             300_000,
    "Junior Rank 2 Investigator":             340_000,
    "Junior Rank 1 Investigator":             380_000,
    "Senior Rank 3 Investigator":             430_000,
    "Senior Rank 2 Investigator":             480_000,
    "Senior Rank 1 Investigator":             540_000,
    "First Class Investigator":               620_000,
    "Senior First Class Investigator":        700_000,
    "Senior Investigator":                    820_000,
    "Associate Special Class Investigator": 1_050_000,
    "Special Class Investigator":             1_400_000,
}

# ══════════════════════════════════════════════════
#              PERSISTENCIA DE DATOS
# ══════════════════════════════════════════════════

def inicializar_data() -> None:
    global BOT_DATA
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k, v in loaded.items():
                        BOT_DATA[k] = v
            print("💾 Datos cargados con éxito desde el archivo local en memoria caché.")
        except Exception as e:
            print(f"⚠️ Error al analizar JSON en el arranque: {e}")

async def guardar_data() -> None:
    def _guardar():
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(BOT_DATA, f, indent=2)
        except Exception as e:
            print(f"❌ Error al escribir en disco: {e}")
    await asyncio.to_thread(_guardar)

# ══════════════════════════════════════════════════
#               AUXILIARES DISCORD / EMBED
# ══════════════════════════════════════════════════

async def actualizar_embed_discord(channel_id: int, message_id: int, nickname: str, title: str, foto_url: str):
    try:
        await bot.wait_until_ready()
        
        canal = bot.get_channel(int(channel_id))
        if not canal:
            canal = await bot.fetch_channel(int(channel_id))
        if not canal: return
        
        msg = await canal.fetch_message(int(message_id))
        if not msg: return
        
        embed = discord.Embed(
            title=nickname,
            description=f"**Rango:** {title}",
            color=discord.Color.from_str("#3498db")
        )
        if foto_url:
            embed.set_image(url=foto_url)
            
        await msg.edit(embed=embed)
        print(f"✅ [Discord Embed] Mensaje {message_id} actualizado. Nick: {nickname} | Rango: {title}")
    except Exception as e:
        print(f"❌ [Sync Error] Fallo al editar el mensaje de Discord {message_id}: {e}")

# ══════════════════════════════════════════════════
#                    API WEB
# ══════════════════════════════════════════════════

async def endpoint_consultar(request: web.Request) -> web.Response:
    if request.rel_url.query.get("key") != API_SECRET:
        return web.json_response({"error": "Unauthorized"}, status=401)
    return web.json_response({
        "pending": BOT_DATA.get("pago_pendiente", False), 
        "ccg_rep": BOT_DATA.get("ccg_rep", 100.0)
    })

async def endpoint_confirmar(request: web.Request) -> web.Response:
    if request.rel_url.query.get("key") != API_SECRET:
        return web.json_response({"error": "Unauthorized"}, status=401)
    BOT_DATA["pago_pendiente"] = False
    await guardar_data()
    return web.json_response({"ok": True})

async def endpoint_nick_confirm(request: web.Request) -> web.Response:
    if request.rel_url.query.get("key") != API_SECRET:
        return web.json_response({"error": "Unauthorized"}, status=401)
    try:
        body = await request.json()
        roblox_id = str(body["roblox_user_id"])
        nickname  = str(body["nickname"])
    except Exception as e:
        return web.json_response({"error": f"Bad request: {e}"}, status=400)

    BOT_DATA.setdefault("nicknames", {})[roblox_id] = nickname
    BOT_DATA.setdefault("active_nicknames", {})[roblox_id] = nickname
    await guardar_data()
    return web.json_response({"ok": True, "roblox_user_id": roblox_id, "nickname": nickname})

async def endpoint_nick_pending(request: web.Request) -> web.Response:
    if request.rel_url.query.get("key") != API_SECRET:
        return web.json_response({"error": "Unauthorized"}, status=401)
    roblox_id = (request.rel_url.query.get("roblox_id") or request.rel_url.query.get("userId") or "").strip()
    if not roblox_id:
        return web.json_response({"error": "Missing roblox_id"}, status=400)

    nicks = BOT_DATA.get("nicknames", {})
    if roblox_id in nicks:
        nick = nicks.pop(roblox_id)
        await guardar_data()
        return web.json_response({"pending": True, "nickname": nick})
            
    return web.json_response({"pending": False})

async def endpoint_player_sync(request: web.Request) -> web.Response:
    try: body = await request.json()
    except Exception: return web.json_response({"error": "Bad request"}, status=400)
        
    if body.get("key") != API_SECRET:
        return web.json_response({"error": "Unauthorized"}, status=401)

    roblox_id     = str(body.get("roblox_id"))
    current_nick  = str(body.get("nickname", "")).strip()
    current_title = str(body.get("title", "Desconocido")).strip()

    cambio_detectado = False

    nicks = BOT_DATA.setdefault("nicknames", {})
    pending_nick = nicks.pop(roblox_id, None)

    if pending_nick:
        BOT_DATA.setdefault("active_nicknames", {})[roblox_id] = pending_nick
        nick_a_mostrar = pending_nick
        cambio_detectado = True
    else:
        nick_a_mostrar = BOT_DATA.setdefault("active_nicknames", {}).get(roblox_id, current_nick)
        if current_nick and not roblox_id in BOT_DATA["active_nicknames"]:
            BOT_DATA["active_nicknames"][roblox_id] = current_nick
            cambio_detectado = True

    embeds = BOT_DATA.setdefault("embeds", {})
    msg_info = embeds.get(roblox_id)

    state_cache = BOT_DATA.setdefault("state_cache", {})
    last_state = state_cache.get(roblox_id, {})
    
    cambio_estado = (last_state.get("title") != current_title) or (last_state.get("nickname") != nick_a_mostrar)

    if cambio_estado:
        state_cache[roblox_id] = {"title": current_title, "nickname": nick_a_mostrar}
        cambio_detectado = True
        
        if msg_info:
            asyncio.create_task(actualizar_embed_discord(
                msg_info["channel_id"],
                msg_info["message_id"],
                nick_a_mostrar,
                current_title,
                msg_info.get("foto")
            ))

    if cambio_detectado:
        await guardar_data()

    return web.json_response({
        "ok": True,
        "active_nickname": nick_a_mostrar
    })

async def iniciar_servidor_web():
    app = web.Application()
    app.router.add_get ("/api/salario",         endpoint_consultar)
    app.router.add_post("/api/salario/confirm",  endpoint_confirmar)
    app.router.add_post("/api/nick/confirm",     endpoint_nick_confirm)
    app.router.add_get ("/api/nick/pending",     endpoint_nick_pending)
    app.router.add_post("/api/player/sync",      endpoint_player_sync)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐  Servidor API corriendo en puerto {port}")

async def get_roblox_avatar_url(roblox_user_id: int) -> str | None:
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={roblox_user_id}&size=150x150&format=Png&isCircular=false"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    data_list = j.get("data", [])
                    if data_list: return data_list[0].get("imageUrl")
    except Exception: pass
    return None

# ══════════════════════════════════════════════════
#                 SETUP DEL BOT
# ══════════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
GUILD_ID = 1445620262572785820

@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")

@bot.command(name="sync")
async def sync_command(ctx: commands.Context):
    if ctx.author.id not in NICK_ALLOWED_IDS: return
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)
    await ctx.send(f"✅ Comandos sincronizados correctamente ({len(synced)}).")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        await message.reply(random.choice(PALABRAS), mention_author=True)
    await bot.process_commands(message)

# ══════════════════════════════════════════════════
#                 COMANDOS SLASHS
# ══════════════════════════════════════════════════

@bot.tree.command(name="pd", description="Anuncia un Evento PD")
async def pd_command(interaction: discord.Interaction, hora: str, join: str):
    if PD_ROLE_ID not in {r.id for r in interaction.user.roles}:
        await interaction.response.send_message("❌ No tienes el rol necesario.", ephemeral=True)
        return
    member_ping = f"<@&{MEMBER_ROLE_ID}>"
    mensaje = f"**Evento PD**\n ▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃\n \n \nInicio : {hora}\nJoin : {join}\n \n \n ▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃\n \n \n||{member_ping}||"
    await interaction.response.send_message(mensaje, allowed_mentions=discord.AllowedMentions(roles=True))

    BOT_DATA["pd_count"] = BOT_DATA.get("pd_count", 0) + 1
    if BOT_DATA["pd_count"] >= 15:
        BOT_DATA["pd_count"] = 0
        BOT_DATA["pago_pendiente"] = True
        await guardar_data()
        await notificar_pago_en_discord(interaction.channel, BOT_DATA.get("ccg_rep", 100.0))
    else:
        await guardar_data()

async def notificar_pago_en_discord(channel: discord.TextChannel, ccg_rep: float):
    factor = ccg_rep / 100.0
    lineas = [
        "**Distribución de Salarios — CCG**",
        f"*Reputación CCG: **{ccg_rep}%** — Factor: ×{factor:.2f}*",
        "```",
        f"{'Rango':<46}  {'Salario base':>14}  {'A cobrar':>14}",
        "─" * 80
    ]
    for rango, base in SALARIOS.items():
        lineas.append(f"{rango:<46}  ¥{base:>13,}  ¥{int(base * factor):>13,}")
    lineas.append("```")
    await channel.send("\n".join(lineas))

@bot.tree.command(name="reputacion", description="Actualiza la reputación de un Distrito")
async def reputacion_command(interaction: discord.Interaction, distrito: str, policia: str, ccg: str, escuadron_0: str, fuerzas_especiales: str, desconocido: str):
    if not {r.id for r in interaction.user.roles}.intersection(REP_ROLES):
        await interaction.response.send_message("No tienes permisos.", ephemeral=True)
        return
    limpiar = lambda v: v.replace("%", "").strip()
    mensaje = f"# Distrito {distrito} #\n**Policía**: {limpiar(policia)}%\n**CCG**: {limpiar(ccg)}%\n**Escuadron 0**: {limpiar(escuadron_0)}%\n**Fuerzas Especiales**: {limpiar(fuerzas_especiales)}%\n**???**: {limpiar(desconocido)}%\n<@&{MEMBER_ROLE_ID}>"
    canal = bot.get_channel(REP_CHANNEL_ID)
    if canal: await canal.send(mensaje, allowed_mentions=discord.AllowedMentions(roles=True))
    try:
        BOT_DATA["ccg_rep"] = float(limpiar(ccg))
        await guardar_data()
    except Exception: pass
    await interaction.response.send_message("Reputación publicada.", ephemeral=True)

@bot.tree.command(name="nick", description="Asigna un nickname a un jugador de Roblox")
async def nick_command(interaction: discord.Interaction, userid: str, nickname: str, foto: str = None):
    if interaction.user.id not in NICK_ALLOWED_IDS:
        await interaction.response.send_message("No tienes permisos para usar este comando.", ephemeral=True)
        return
    try: roblox_id = int(userid.strip())
    except ValueError:
        await interaction.response.send_message("❌ ID de Roblox inválido.", ephemeral=True)
        return
    await interaction.response.defer()
    avatar_url = foto
    if not avatar_url or not avatar_url.startswith("http"):
        avatar_url = await get_roblox_avatar_url(roblox_id) or "https://www.roblox.com/headshot-thumbnail/image?userId=1&width=150&height=150&format=png"

    embed = discord.Embed(title=nickname, color=discord.Color.from_str("#3498db"))
    embed.set_image(url=avatar_url)
    msg = await interaction.followup.send(embed=embed)

    BOT_DATA.setdefault("nicknames", {})[str(roblox_id)] = nickname
    BOT_DATA.setdefault("active_nicknames", {})[str(roblox_id)] = nickname
    BOT_DATA.setdefault("embeds", {})[str(roblox_id)] = {"channel_id": msg.channel.id, "message_id": msg.id, "foto": avatar_url}
    
    if str(roblox_id) in BOT_DATA.setdefault("state_cache", {}):
        del BOT_DATA["state_cache"][str(roblox_id)]
        
    await guardar_data()

@bot.tree.command(name="msg", description="Envía un mensaje anónimo, opcionalmente respondiendo y con imagen")
async def msg_command(interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str, message_id: str = None, adjunto: discord.Attachment = None):
    if MSG_ROLE_ID not in {r.id for r in interaction.user.roles}: 
        await interaction.response.send_message("❌ No tienes permiso para esto.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    archivo_discord = None
    if adjunto:
        archivo_discord = await adjunto.to_file()

    if message_id:
        try:
            msg_obj = await canal.fetch_message(int(message_id.strip()))
            await msg_obj.reply(mensaje, file=archivo_discord, mention_author=True)
            await interaction.followup.send("✅ Respuesta anónima enviada con éxito.")
            return
        except discord.NotFound:
            await interaction.followup.send("❌ No se encontró ningún mensaje con ese ID en ese canal.")
            return
        except ValueError:
            await interaction.followup.send("❌ El ID del mensaje debe ser un número válido.")
            return

    await canal.send(mensaje, file=archivo_discord, allowed_mentions=discord.AllowedMentions.all())
    await interaction.followup.send("✅ Mensaje anónimo enviado con éxito.")

@bot.tree.context_menu(name="Responder (Troll)")
async def troll_reply(interaction: discord.Interaction, message: discord.Message):
    if not {STAFF_ROLE_ID, OWNER_ROLE_ID}.intersection({r.id for r in interaction.user.roles}):
        await interaction.response.send_message("No puedes usar esto.", ephemeral=True)
        return
        
    frases_troll = [
        "Claro que sí, campeón.",
        "Dato curioso: a nadie le importa.",
        "Take, calvo. Digo... ¿qué decías?",
        "Mejor ponte a farmear rep para la CCG."
    ]
    
    await message.reply(random.choice(frases_troll), mention_author=True)
    await interaction.response.send_message("Troleada enviada.", ephemeral=True)

@bot.tree.command(name="strike", description="Emite un strike a un usuario")
async def strike_command(interaction: discord.Interaction, usuario: discord.Member, razon: str):
    if not {STAFF_ROLE_ID, OWNER_ROLE_ID}.intersection({r.id for r in interaction.user.roles}): return
    try: await usuario.send(f"**Has recibido un Strike —**\n▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃\n\n{razon}\n\n▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃")
    except Exception: pass
    await interaction.response.send_message("Strike registrado.", ephemeral=True)

@bot.tree.command(name="ban", description="Banea a un usuario")
@app_commands.choices(duracion=DURACION_CHOICES)
async def ban_command(interaction: discord.Interaction, usuario: discord.Member, razon: str, duracion: app_commands.Choice[int] = None, permanente: bool = False):
    roles = {r.id for r in interaction.user.roles}
    if STAFF_ROLE_ID not in roles and OWNER_ROLE_ID not in roles: return
    if permanente and OWNER_ROLE_ID not in roles: return
    segundos = duracion.value if duracion else 604800
    try: await usuario.send(f"Baneado temporalmente. Motivo: {razon}")
    except Exception: pass
    await usuario.ban(reason=razon)
    if not permanente:
        async def desban(uid, g, s):
            await asyncio.sleep(s)
            try: await g.unban(discord.Object(id=uid))
            except Exception: pass
        asyncio.create_task(desban(usuario.id, interaction.guild, segundos))
    await interaction.response.send_message("Sanción aplicada con éxito.", ephemeral=True)

@bot.tree.command(name="desban", description="Desbanea a un usuario por ID")
async def desban_command(interaction: discord.Interaction, user_id: str):
    if OWNER_ROLE_ID not in {r.id for r in interaction.user.roles}: return
    try:
        uid = int(user_id.strip())
        await interaction.guild.unban(discord.Object(id=uid))
        await interaction.response.send_message("Usuario desbaneado.", ephemeral=True)
    except Exception: pass

@bot.tree.command(name="textp", description="Envía un MD anónimo")
async def textp_command(interaction: discord.Interaction, usuario: discord.Member, mensaje: str):
    if OWNER_ROLE_ID not in {r.id for r in interaction.user.roles}: return
    try: await usuario.send(mensaje)
    except Exception: pass
    await interaction.response.send_message("Mensaje enviado de forma anónima.", ephemeral=True)

@bot.tree.command(name="pesca", description="🎲 Dado d20")
async def pesca_command(interaction: discord.Interaction):
    res = random.randint(1, 20)
    msg = "**Especial**" if res==20 else "Uno grande." if res>=15 else "Uno mediano." if res>=10 else "Uno pequeño." if res>=5 else "Nada." if res==1 else "Malo pescando."
    await interaction.response.send_message(f"🎲 **{interaction.user.display_name}** sacó {res}/20\n{msg}")

@bot.tree.command(name="quinx", description="Ruleta Quinx")
async def quinx_command(interaction: discord.Interaction, jugador: str):
    await interaction.response.send_message(f"Procesando a **{jugador}**...")
    await asyncio.sleep(2)
    t = random.random() * 100
    res = "**FALLO — INSANITY**" if t<45 else "**FALLIDO (Muerte)**" if t<75 else "**EXITO**"
    await interaction.edit_original_response(content=f"Procedimiento Quinx — **{jugador}**\n▃▃▃▃▃▃▃▃\n{res}\n▃▃▃▃▃▃▃▃")

async def main():
    inicializar_data()
    await iniciar_servidor_web()
    async with bot: await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())