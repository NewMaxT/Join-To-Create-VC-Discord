import os
import json
import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands, tasks
from dotenv import load_dotenv
from typing import Dict, Optional, Set
from localization import Localization
from config import ServerConfig
from quiz_automation import QuizAutomation
import asyncio
from nextcord import Activity, ActivityType
from datetime import datetime

# Charger les variables d'environnement
load_dotenv()

# Configuration du bot avec les intents
intents = nextcord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.members = True  # Required for autorole

activity = Activity(type=ActivityType.playing, name="Entièrement open-source")
bot = commands.Bot(intents=intents, activity=activity)

# Initialize localization and server config
loc = Localization()
server_config = ServerConfig()

# Initialize quiz automation
quiz_automation = None

class VoiceCreatorConfig:
    def __init__(self, channel_id: int, template_name: str, position: str = "after", user_limit: int = 0):
        self.channel_id = channel_id
        self.template_name = template_name
        self.position = position  # "before" ou "after"
        self.user_limit = user_limit
    
    def to_dict(self) -> dict:
        """Convertit la configuration en dictionnaire pour la sauvegarde JSON"""
        return {
            'channel_id': self.channel_id,
            'template_name': self.template_name,
            'position': self.position,
            'user_limit': self.user_limit
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VoiceCreatorConfig':
        """Crée une configuration à partir d'un dictionnaire JSON"""
        return cls(
            channel_id=data['channel_id'],
            template_name=data['template_name'],
            position=data.get('position', 'after'),
            user_limit=data.get('user_limit', 0)
        )

# Dictionnaire pour stocker les configurations des créateurs de salons vocaux par serveur
# Format: guild_id -> Dict[creator_channel_id, VoiceCreatorConfig]
guild_configs: Dict[int, Dict[int, VoiceCreatorConfig]] = {}

# Dictionnaire pour suivre les salons créés par le bot
# Format: guild_id -> Set[channel_id]
created_channels: Dict[int, Set[int]] = {}

CONFIG_FILE = 'voice_creators.json'

def save_configs():
    """Sauvegarde les configurations dans un fichier JSON"""
    data = {
        str(guild_id): {
            str(channel_id): config.to_dict()
            for channel_id, config in configs.items()
        }
        for guild_id, configs in guild_configs.items()
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Configurations saved to {CONFIG_FILE}")

def load_configs():
    """Charge les configurations depuis le fichier JSON"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for guild_id_str, configs in data.items():
            guild_id = int(guild_id_str)
            guild_configs[guild_id] = {
                int(channel_id): VoiceCreatorConfig.from_dict(config_data)
                for channel_id, config_data in configs.items()
            }
        print(f"Configurations loaded from {CONFIG_FILE}")
    except Exception as e:
        print(f"Erreur lors du chargement des configurations : {e}")

@bot.event
async def on_ready():
    """Événement de démarrage du bot"""
    print(f"Bot prêt ! Connecté en tant que {bot.user.name}")

    # Load configurations at startup
    load_configs()
    server_config.load_config()
    # Sync slash commands to each guild for immediate availability
    try:
        for guild in bot.guilds:
            await bot.sync_application_commands(guild_id=guild.id)
        print("Slash commands synced to all guilds")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")
    
    # Afficher les informations d'auto-rôle pour chaque serveur
    for guild in bot.guilds:
        config = server_config.get_autorole(guild.id)
        if config:
            role = guild.get_role(config['role_id'])
            if role:
                print(f"\nInformations d'auto-rôle pour {guild.name} :")
                print(f"Rôle : {role.name}")
                
                # Obtenir les membres avec le rôle
                members_with_role = [member for member in guild.members if role in member.roles]
                
                if members_with_role:
                    print(f"Membres avec {role.name} :")
                    for member in members_with_role:
                        # Obtenir la date d'expiration si définie
                        expiry_time = server_config.get_role_expiry_time(guild.id, member.id)
                        if expiry_time:
                            current_time = datetime.now().timestamp()
                            remaining_time = expiry_time - current_time
                            if remaining_time > 0:
                                minutes = int(remaining_time / 60)
                                print(f"  - {member.display_name} : {minutes} minutes restantes")
                            else:
                                print(f"  - {member.display_name} : Rôle expiré")
                        else:
                            print(f"  - {member.display_name} : Pas d'expiration")
                else:
                    print("Aucun membre ne possède actuellement ce rôle")
    
    # Start background tasks
    check_role_expiry.start()
    check_sticky_messages.start()
    
    # Initialiser l'automatisation du quiz
    global quiz_automation
    quiz_automation = QuizAutomation(bot, server_config)
    # Créer/valider l'onglet de statut une seule fois au démarrage
    try:
        cfg = quiz_automation.config
        if cfg.get("spreadsheet_id"):
            from google_sheets_manager import GoogleSheetsManager
            _gsm = GoogleSheetsManager()
            _gsm.ensure_status_sheet(cfg["spreadsheet_id"], cfg.get("status_sheet_title", "Statut - Roles"))
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la feuille de statut: {e}")
    
    # Vérifier que les salons créateurs existent toujours
    invalid_configs = []
    for guild_id, configs in guild_configs.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            invalid_configs.append((guild_id, None))
            continue
            
        invalid_channels = []
        for channel_id in configs.keys():
            channel = guild.get_channel(channel_id)
            if not channel:
                invalid_channels.append(channel_id)
        
        if invalid_channels:
            for channel_id in invalid_channels:
                del configs[channel_id]
            if not configs:
                invalid_configs.append((guild_id, None))
    
    # Nettoyer les configurations invalides
    for guild_id, _ in invalid_configs:
        if guild_id in guild_configs:
            del guild_configs[guild_id]
    
    # Sauvegarder les configurations nettoyées
    save_configs()

@tasks.loop(seconds=30)
async def check_role_expiry():
    """Vérifie et supprime les rôles expirés"""
    expired_roles = server_config.get_expired_roles()
    
    for guild_id, member_ids in expired_roles.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
            
        config = server_config.get_autorole(guild_id)
        if not config:
            continue
            
        role = guild.get_role(config['role_id'])
        if not role:
            continue
            
        for member_id in member_ids:
            member = guild.get_member(member_id)
            if member and role in member.roles:
                try:
                    await member.remove_roles(role)
                    print(f"Rôle {role.name} retiré de {member.display_name}")
                    # Log de suppression dans le salon si configuré
                    log_channel_id = server_config.get_autorole_log_channel(guild_id)
                    if log_channel_id:
                        ch = guild.get_channel(log_channel_id)
                        if ch:
                            await ch.send(f"🗑️ Rôle {role.mention} retiré de {member.mention} (expiration)")
                except nextcord.HTTPException:
                    print(f"Erreur lors du retrait du rôle {role.name} de {member.display_name}")
                    pass

@tasks.loop(seconds=5)
async def check_sticky_messages():
    """Vérifie et maintient les messages épinglés toutes les 5 secondes"""
    for guild_id, channels in server_config.sticky_messages.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        for channel_id, sticky_config in channels.items():
            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            try:
                # Get the last message in the channel
                last_messages = [msg async for msg in channel.history(limit=1)]
                last_message = last_messages[0] if last_messages else None
                
                # Get the last sticky message if it exists
                last_sticky_id = sticky_config.get('last_message_id')
                last_sticky = None
                if last_sticky_id:
                    try:
                        last_sticky = await channel.fetch_message(last_sticky_id)
                    except (nextcord.NotFound, nextcord.HTTPException):
                        last_sticky = None

                # If the last message isn't our sticky message, we need to repost it
                if not last_message or last_message.id != sticky_config.get('last_message_id'):
                    # Delete the old sticky message if it exists
                    if last_sticky:
                        try:
                            await last_sticky.delete()
                            print(f"Ancien message épinglé supprimé dans le salon {channel_id}")
                        except nextcord.HTTPException:
                            pass

                    # Post new sticky message
                    new_message = await channel.send(sticky_config['content'])
                    sticky_config['last_message_id'] = new_message.id
                    server_config.update_sticky_message_id(guild_id, channel_id, new_message.id)
                    print(f"Nouveau message épinglé publié dans le salon {channel_id}")

            except Exception as e:
                print(f"Error maintaining sticky message in channel {channel_id}: {e}")

@bot.event
async def on_member_join(member):
    """Gère l'arrivée de nouveaux membres"""
    print(f"Nouveau membre : {member.display_name}")
    guild_id = member.guild.id
    config = server_config.get_autorole(guild_id)
    
    if config:
        # If trigger is on_quiz_access, do not assign on join
        if config.get('trigger') == 'on_quiz_access':
            print("Autorole trigger set to on_quiz_access; skipping on join.")
            return
        # Check if we should skip rejoining members
        if config['check_rejoin'] and server_config.has_member_joined_before(guild_id, member.id):
            print(f"Ignoré: {member.display_name} a déjà rejoint auparavant")
            return
            
        role = member.guild.get_role(config['role_id'])
        if role:
            try:
                await member.add_roles(role)
                server_config.add_joined_member(guild_id, member.id)
                print(f"Rôle {role.name} ajouté à {member.display_name}")
                # Log dans le salon d'auto-rôle si défini
                log_channel_id = server_config.get_autorole_log_channel(guild_id)
                if log_channel_id:
                    ch = member.guild.get_channel(log_channel_id)
                    if ch:
                        await ch.send(f"✅ Rôle {role.mention} attribué à {member.mention}")
            except nextcord.HTTPException as e:
                # Check if it's a permission error (code 403)
                if e.code == 50013:  # Missing Permissions error code
                    bot_permissions = member.guild.me.guild_permissions
                    missing_perms = []
                    
                    # Check common required permissions
                    if not bot_permissions.manage_roles:
                        missing_perms.append("Manage Roles")
                    if not bot_permissions.view_audit_log:
                        missing_perms.append("View Audit Log")
                    
                    # Check role hierarchy
                    if member.guild.me.top_role <= role:
                        missing_perms.append(f"Role Hierarchy (Bot's highest role must be above {role.name})")
                    
                    print(f"Permissions manquantes : {', '.join(missing_perms)}")
                    print(f"Détails de l'erreur : {str(e)}")
                else:
                    print(f"Erreur lors de l'ajout du rôle {role.name} à {member.display_name} (hors permissions) : {str(e)}")
                # Log erreur
                log_channel_id = server_config.get_autorole_log_channel(guild_id)
                if log_channel_id:
                    ch = member.guild.get_channel(log_channel_id)
                    if ch:
                        await ch.send(f"❌ Impossible d'attribuer {role.mention} à {member.mention} : {str(e)}")
        else:
            print(f"Mauvaise configuration de rôle pour le serveur {guild_id}")
    else:
        print(f"Aucune configuration d'auto-rôle pour le serveur {guild_id}")

@bot.slash_command(name="config", description="Groupe de commandes de configuration")
@commands.has_permissions(administrator=True)
async def config(interaction: Interaction):
    """Configuration commands group"""
    pass

@bot.slash_command(name="autorole", description="Commandes liées à l'auto-rôle")
@commands.has_permissions(administrator=True)
async def autorole_cmd(interaction: Interaction):
    """Groupe de commandes autorole"""
    pass

@autorole_cmd.subcommand(name="list_expiry", description="Lister les membres et le temps restant avant expiration de l'auto-rôle")
@commands.has_permissions(administrator=True)
async def autorole_list_expiry(interaction: Interaction):
    guild = interaction.guild
    config = server_config.get_autorole(guild.id)
    if not config:
        await interaction.response.send_message("Aucune configuration d'auto-rôle pour ce serveur.", ephemeral=True)
        return
    role = guild.get_role(config['role_id'])
    if not role:
        await interaction.response.send_message("Le rôle configuré n'existe plus.", ephemeral=True)
        return

    members_with_role = [m for m in guild.members if role in m.roles]
    if not members_with_role:
        await interaction.response.send_message("Aucun membre ne possède ce rôle.", ephemeral=True)
        return

    lines = []
    for member in members_with_role:
        minutes_left = server_config.get_time_left_before_role_expiry(guild.id, member.id)
        if minutes_left is None:
            lines.append(f"• {member.display_name}: pas d'expiration")
        else:
            lines.append(f"• {member.display_name}: {minutes_left} min restantes")

    text = "\n".join(lines[:25])
    more = "" if len(lines) <= 25 else f"\n... et {len(lines) - 25} autres"
    await interaction.response.send_message(f"Membres avec {role.mention} :\n{text}{more}", ephemeral=True)

@config.subcommand(name="language", description="Définir la langue du bot pour ce serveur")
@commands.has_permissions(administrator=True)
async def set_language(
    interaction: Interaction,
    language: str = SlashOption(description="Code langue à définir (par ex. 'en', 'fr')")
):
    """Set the bot's language for this server"""
    if loc.set_language(interaction.guild_id, language):
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.language.set_success'))
    else:
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.language.invalid', 
                                  langs=', '.join(loc.get_available_languages())))

@config.subcommand(name="autorole", description="Configurer l'auto-rôle pour les nouveaux membres")
@commands.has_permissions(administrator=True)
async def set_autorole(
    interaction: Interaction,
    role: nextcord.Role = SlashOption(description="Rôle à attribuer automatiquement"),
    expiry_minutes: Optional[int] = SlashOption(description="Optionnel : minutes avant expiration du rôle", required=False),
    check_rejoin: bool = SlashOption(description="Ignorer les membres qui reviennent", required=False, default=False),
    trigger: str = SlashOption(description="Quand attribuer le rôle", choices=["on_join", "on_quiz_access"], default="on_join")
):
    """Configure auto-role for new members"""
    # Validate expiry_minutes if provided
    if expiry_minutes is not None and expiry_minutes <= 0:
        await interaction.response.send_message("Expiry time must be greater than 0 minutes!")
        return
        
    server_config.set_autorole(interaction.guild_id, role.id, expiry_minutes, check_rejoin, trigger)
    
    # Send confirmation message
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.autorole.set_success', role=role.mention) + f" (déclencheur={trigger})")
    
    if expiry_minutes:
        await interaction.followup.send(loc.get_text(interaction.guild_id, 'config.autorole.expiry_set', minutes=expiry_minutes))
    
    if check_rejoin:
        await interaction.followup.send(loc.get_text(interaction.guild_id, 'config.autorole.rejoin_enabled'))

@config.subcommand(name="remove_autorole", description="Supprimer la configuration d'auto-rôle")
@commands.has_permissions(administrator=True)
async def remove_autorole(interaction: Interaction):
    """Remove auto-role configuration"""
    server_config.remove_autorole(interaction.guild_id)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.autorole.remove_success'))

@config.subcommand(name="autorole_logs", description="Définir le salon de logs pour l'auto-rôle")
@commands.has_permissions(administrator=True)
async def set_autorole_logs(
    interaction: Interaction,
    channel: nextcord.TextChannel = SlashOption(description="Salon où publier les logs d'auto-rôle")
):
    server_config.set_autorole_log_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(f"Salon de logs d'auto-rôle défini sur {channel.mention}")

@config.subcommand(name="sticky", description="Définir un message épinglé dans un salon")
@commands.has_permissions(administrator=True)
async def set_sticky(
    interaction: Interaction,
    channel: nextcord.TextChannel = SlashOption(description="Salon où définir le message épinglé"),
    content: str = SlashOption(description="Contenu du message épinglé")
):
    """Set a sticky message in a channel"""
    server_config.set_sticky_message(interaction.guild_id, channel.id, content, last_message_id=None)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.sticky.set_success', channel=channel.mention))

@config.subcommand(name="remove_sticky", description="Supprimer le message épinglé d'un salon")
@commands.has_permissions(administrator=True)
async def remove_sticky(
    interaction: Interaction,
    channel: nextcord.TextChannel = SlashOption(description="Salon où supprimer le message épinglé")
):
    """Remove sticky message from a channel"""
    server_config.remove_sticky_message(interaction.guild_id, channel.id)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.sticky.remove_success', channel=channel.mention))

@bot.slash_command(name="setupvoice", description="Créer un créateur de salon vocal avec des paramètres personnalisés")
@commands.has_permissions(administrator=True)
async def setupvoice(
    interaction: Interaction,
    template_name: str = SlashOption(
        description="Modèle pour les noms de salon, utilisez {user} pour le nom de l'utilisateur",
        default="Channel of {user}"
    ),
    position: str = SlashOption(
        description="Position des nouveaux salons par rapport au créateur",
        choices=["before", "after"],
        default="after"
    ),
    creator_name: str = SlashOption(
        description="Nom du salon créateur",
        default="➕ Join to Create"
    ),
    user_limit: int = SlashOption(
        description="Limite d'utilisateurs pour les salons créés (0 = illimité)",
        min_value=0,
        max_value=99,
        default=0
    )
):
    """Crée un créateur de salon vocal avec des paramètres personnalisés"""
    guild = interaction.guild
    current_category = interaction.channel.category

    # Validate template name
    if not template_name or len(template_name) > 100:
        await interaction.response.send_message("Le nom du modèle doit contenir entre 1 et 100 caractères !")
        return

    # Validate creator name
    if not creator_name or len(creator_name) > 100:
        await interaction.response.send_message("Le nom du salon créateur doit contenir entre 1 et 100 caractères !")
        return

    # Create voice channel creator
    create_channel = await guild.create_voice_channel(
        name=creator_name,
        category=current_category
    )

    # Initialize guild config if it doesn't exist
    if guild.id not in guild_configs:
        guild_configs[guild.id] = {}
    
    guild_configs[guild.id][create_channel.id] = VoiceCreatorConfig(
        channel_id=create_channel.id,
        template_name=template_name,
        position=position,
        user_limit=user_limit
    )

    # Save configurations
    save_configs()

    location = loc.get_text(interaction.guild_id, 'commands.location_before' if position == "before" else 'commands.location_after')
    limit = loc.get_text(interaction.guild_id, 'commands.limit_unlimited') if user_limit == 0 else str(user_limit)
    
    await interaction.response.send_message(loc.get_text(
        interaction.guild_id,
        'commands.setup_success',
        creator_name=creator_name,
        channel=create_channel.mention,
        location=location,
        template=template_name,
        limit=limit
    ))

@bot.slash_command(name="removevoice", description="Supprimer un créateur de salon vocal")
@commands.has_permissions(administrator=True)
async def removevoice(
    interaction: Interaction,
    channel: nextcord.VoiceChannel = SlashOption(description="Le salon vocal créateur à supprimer")
):
    """Supprime un créateur de salon vocal"""
    if channel.id in guild_configs.get(interaction.guild_id, {}):
        await channel.delete()
        del guild_configs[interaction.guild_id][channel.id]
        if not guild_configs[interaction.guild_id]:
            del guild_configs[interaction.guild_id]
        # Save configurations
        save_configs()
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'commands.remove_success'))
    else:
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'commands.remove_error'))

@bot.slash_command(name="listvoice", description="Lister tous les créateurs de salons vocaux du serveur")
@commands.has_permissions(administrator=True)
async def listvoice(interaction: Interaction):
    """Liste tous les créateurs de salons vocaux du serveur"""
    if interaction.guild_id not in guild_configs or not guild_configs[interaction.guild_id]:
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'commands.list_none'))
        return

    creators = []
    for creator_id, config in guild_configs[interaction.guild_id].items():
        channel = interaction.guild.get_channel(creator_id)
        if channel:
            position = config.position if config.position is not None else loc.get_text(interaction.guild_id, 'commands.default_position')
            creators.append(loc.get_text(
                interaction.guild_id,
                'commands.list_creator_info',
                channel=channel.mention,
                template=config.template_name,
                position=position
            ))

    if creators:
        embed = nextcord.Embed(
            title=loc.get_text(interaction.guild_id, 'commands.list_creators'),
            color=0x00ff00
        )
        for i, creator in enumerate(creators, 1):
            embed.add_field(name=f"Creator {i}", value=creator, inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'commands.list_none_active'))

# Quiz Automation Commands
@bot.slash_command(name="quiz", description="Configuration de l'automatisation du quiz")
@commands.has_permissions(administrator=True)
async def quiz(interaction: Interaction):
    """Configuration de l'automatisation du quiz"""
    pass

@quiz.subcommand(name="setup", description="Configure l'automatisation du quiz avec Google Sheets")
@commands.has_permissions(administrator=True)
async def setup_quiz(
    interaction: Interaction,
    spreadsheet_id: str = SlashOption(description="ID de la feuille Google Sheets"),
    waiting_role: nextcord.Role = SlashOption(description="Rôle d'attente (obligatoire)", required=True),
    access_role: nextcord.Role = SlashOption(description="Rôle d'accès (obligatoire)", required=True),
    min_score: int = SlashOption(description="Note minimale requise", min_value=0, max_value=20, default=17),
    check_interval: int = SlashOption(description="Intervalle de vérification (secondes)", min_value=10, max_value=3600, default=60),
    log_channel: Optional[nextcord.TextChannel] = SlashOption(description="Canal de logs (optionnel)", required=False)
):
    """Configure l'automatisation du quiz"""
    try:
        global quiz_automation
        if not quiz_automation:
            await interaction.response.send_message("❌ L'automatisation du quiz n'est pas initialisée", ephemeral=True)
            return
        
        log_channel_id = log_channel.id if log_channel else None
        
        await quiz_automation.setup_quiz_automation(
            spreadsheet_id=spreadsheet_id,
            waiting_role=waiting_role,
            access_role=access_role,
            min_score=min_score,
            log_channel_id=log_channel_id
        )
        # Sauvegarder l'intervalle par défaut choisi par l'admin
        quiz_automation.update_config(check_interval=check_interval, check_interval_default=check_interval)
        # Redémarrer la boucle avec le nouvel intervalle
        try:
            quiz_automation.check_quiz_results.change_interval(seconds=check_interval)
        except Exception:
            pass
        
        embed = nextcord.Embed(
            title="✅ Configuration du Quiz",
            description="L'automatisation du quiz a été configurée avec succès !",
            color=0x00ff00
        )
        embed.add_field(name="📊 Feuille Google Sheets", value=spreadsheet_id, inline=False)
        embed.add_field(name="⏳ Rôle d'attente", value=waiting_role.mention, inline=True)
        embed.add_field(name="🎯 Rôle d'accès", value=access_role.mention, inline=True)
        embed.add_field(name="📈 Note minimale", value=f"{min_score}/20", inline=True)
        embed.add_field(name="⏱️ Intervalle", value=f"{check_interval}s", inline=True)
        if log_channel:
            embed.add_field(name="📝 Canal de logs", value=log_channel.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de la configuration: {str(e)}", ephemeral=True)

@quiz.subcommand(name="status", description="Affiche le statut de l'automatisation du quiz")
@commands.has_permissions(administrator=True)
async def quiz_status(interaction: Interaction):
    """Affiche le statut de l'automatisation du quiz"""
    try:
        global quiz_automation
        if not quiz_automation:
            await interaction.response.send_message("❌ L'automatisation du quiz n'est pas initialisée", ephemeral=True)
            return
        
        status = await quiz_automation.get_status()
        
        embed = nextcord.Embed(
            title="📊 Statut de l'Automatisation du Quiz",
            color=0x00ff00 if status["is_running"] else 0xff0000
        )
        embed.add_field(name="🔄 Statut", value="✅ Actif" if status["is_running"] else "❌ Inactif", inline=True)
        embed.add_field(name="📊 Feuille Google Sheets", value=status["spreadsheet_id"], inline=True)
        embed.add_field(name="⏱️ Intervalle de vérification", value=f"{status['check_interval']} secondes", inline=True)
        embed.add_field(name="📈 Note minimale", value=f"{status['min_score']}/20", inline=True)
        embed.add_field(name="⏳ Rôle d'attente", value=(f"<@&{status['waiting_role_id']}>" if status.get('waiting_role_id') else "Non défini"), inline=True)
        embed.add_field(name="🎯 Rôle d'accès", value=(f"<@&{status['access_role_id']}>" if status.get('access_role_id') else "Non défini"), inline=True)
        embed.add_field(name="📝 Lignes traitées", value=str(status["processed_rows"]), inline=True)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de la récupération du statut: {str(e)}", ephemeral=True)

@quiz.subcommand(name="test", description="Teste la connexion avec Google Sheets")
@commands.has_permissions(administrator=True)
async def test_quiz_connection(interaction: Interaction):
    """Teste la connexion avec Google Sheets"""
    try:
        global quiz_automation
        if not quiz_automation:
            await interaction.response.send_message("❌ L'automatisation du quiz n'est pas initialisée", ephemeral=True)
            return
        
        config = quiz_automation.config
        if not config.get("spreadsheet_id"):
            await interaction.response.send_message("❌ Aucune feuille Google Sheets configurée", ephemeral=True)
            return
        
        # Test de connexion
        results = quiz_automation.sheets_manager.get_quiz_results(config["spreadsheet_id"])
        
        embed = nextcord.Embed(
            title="🔍 Test de Connexion Google Sheets",
            description="Connexion réussie !",
            color=0x00ff00
        )
        embed.add_field(name="📊 Résultats trouvés", value=str(len(results)), inline=True)
        
        if results:
            # Afficher les 5 premiers résultats
            sample_results = results[:5]
            results_text = "\n".join([f"• {r['pseudo']}: {r['note']}/20" for r in sample_results])
            if len(results) > 5:
                results_text += f"\n... et {len(results) - 5} autres"
            
            embed.add_field(name="📝 Exemples de résultats", value=results_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        embed = nextcord.Embed(
            title="❌ Erreur de Connexion",
            description=f"Impossible de se connecter à Google Sheets: {str(e)}",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="help", description="Afficher l'aide du bot")
@commands.has_permissions(administrator=True)
async def cmds_help(interaction: Interaction):
    """Affiche l'aide du bot (Admin uniquement)"""
    embed = nextcord.Embed(
        title=loc.get_text(interaction.guild_id, 'help.title'),
        description=loc.get_text(interaction.guild_id, 'help.description'),
        color=0x00ff00
    )

    # setupvoice command
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.setup_title'),
        value=loc.get_text(interaction.guild_id, 'help.setup_desc'),
        inline=False
    )

    # removevoice command
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.remove_title'),
        value=loc.get_text(interaction.guild_id, 'help.remove_desc'),
        inline=False
    )

    # listvoice command
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.list_title'),
        value=loc.get_text(interaction.guild_id, 'help.list_desc'),
        inline=False
    )

    # Commandes de configuration
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.config_title'),
        value=loc.get_text(interaction.guild_id, 'help.config_desc'),
        inline=False
    )

    # help command
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.help_title'),
        value=loc.get_text(interaction.guild_id, 'help.help_desc'),
        inline=False
    )

    # Important notes
    embed.add_field(
        name=loc.get_text(interaction.guild_id, 'help.notes_title'),
        value=loc.get_text(interaction.guild_id, 'help.notes_desc'),
        inline=False
    )

    # Footer with version
    embed.set_footer(text=loc.get_text(interaction.guild_id, 'help.footer'))

    # Ajouter info Quiz & MassGive
    embed.add_field(
        name="Quiz",
        value=(
            "`/quiz setup` Configure l'automatisation (Google Sheets)\n"
            "`/quiz status` Affiche l'état\n"
            "`/quiz test` Teste la connexion\n"
            "- Statut: écrit dans l'onglet `Statut - Roles` (✅/❌, détails FR)\n"
            "- Intervalle: 60s par défaut, réduit à 5s si >5 lignes à traiter"
        ),
        inline=False
    )
    embed.add_field(
        name="MassGive",
        value=(
            "`/massgive target_role:@Role everyone:true` — attribuer à tout le serveur\n"
            "`/massgive target_role:@Role filter_role:@RoleFiltre` — attribuer à ceux qui ont RoleFiltre\n"
            "`/config autorole_logs channel:#logs` — définir le salon de logs auto-rôle\n"
            "`/config autorole ...` — configure l'auto-rôle (délais d'expiration visibles dans la console et via la commande ci-dessous)\n"
            "`/autorole list_expiry` — liste les membres avec temps restant avant expiration"
        ),
        inline=False
    )

    await interaction.response.send_message(embed=embed)

# Update error handlers for slash commands
@bot.event
async def on_application_command_error(interaction: Interaction, error):
    """Gestionnaire global d'erreurs pour les commandes slash"""
    try:
        if isinstance(error, commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(loc.get_text(interaction.guild_id, 'errors.missing_permissions'), ephemeral=True)
            else:
                await interaction.response.send_message(loc.get_text(interaction.guild_id, 'errors.missing_permissions'), ephemeral=True)
        else:
            # Log other errors
            cmd_name = getattr(interaction.application_command, 'name', 'unknown')
            print(f"Erreur dans la commande slash {cmd_name} : {error}")
            if interaction.response.is_done():
                await interaction.followup.send("Une erreur est survenue lors de l'exécution de cette commande.", ephemeral=True)
            else:
                await interaction.response.send_message("Une erreur est survenue lors de l'exécution de cette commande.", ephemeral=True)
    except nextcord.NotFound:
        # Interaction token likely expired (Unknown interaction). Ignore gracefully.
        pass
    except Exception as e:
        print(f"Error while handling application command error: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Gère la création et la suppression des salons vocaux"""
    guild_id = member.guild.id
    
    if after.channel is not None and guild_id in guild_configs:
        # Vérifier si l'utilisateur a rejoint un salon créateur
        if after.channel.id in guild_configs[guild_id]:
            config = guild_configs[guild_id][after.channel.id]
            
            # Créer le nom du salon à partir du modèle
            channel_name = config.template_name.replace("{user}", member.display_name)
            
            # Créer le nouveau salon dans la même catégorie que le créateur
            new_channel = await member.guild.create_voice_channel(
                name=channel_name,
                category=after.channel.category,
                user_limit=config.user_limit
            )

            # Positionner le salon relativement au créateur
            try:
                if config.position == "before":
                    await new_channel.move(before=after.channel, sync_permissions=True)
                else:  # after
                    await new_channel.move(after=after.channel, sync_permissions=True)
            except nextcord.HTTPException:
                pass  # Ignorer les erreurs de position
            
            # Ajouter le nouveau salon à la liste des salons créés
            if guild_id not in created_channels:
                created_channels[guild_id] = set()
            created_channels[guild_id].add(new_channel.id)
            
            # Déplacer le membre dans le nouveau salon
            await member.move_to(new_channel)
            print(f"Membre {member.display_name} déplacé vers {new_channel.name}")
    
    # Nettoyer les salons vides
    if before.channel is not None and guild_id in created_channels:
        # Vérifier si le salon a été créé par le bot et est vide
        if (
            before.channel.id in created_channels[guild_id] and
            len(before.channel.members) == 0
        ):
            await before.channel.delete()
            created_channels[guild_id].remove(before.channel.id)
            # Supprimer le set si c'était le dernier salon
            if not created_channels[guild_id]:
                del created_channels[guild_id]

@bot.slash_command(name="massgive", description="Attribuer un rôle en masse")
@commands.has_permissions(administrator=True)
async def massgive(
    interaction: Interaction,
    target_role: nextcord.Role = SlashOption(description="Rôle à attribuer"),
    filter_role: Optional[nextcord.Role] = SlashOption(description="Attribuer uniquement aux membres possédant ce rôle (optionnel)", required=False),
    everyone: bool = SlashOption(description="Attribuer à tout le serveur (@everyone)", default=False)
):
    """Attribue un rôle à @everyone ou à tous les membres possédant un rôle donné."""
    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    # Validation des options
    if not everyone and filter_role is None:
        await interaction.followup.send("Veuillez préciser un rôle filtre ou choisir l'option @everyone.")
        return

    # Vérifier la hiérarchie des rôles et permissions du bot
    me = guild.me
    if not me.guild_permissions.manage_roles:
        await interaction.followup.send("Je n'ai pas la permission 'Gérer les rôles'.")
        return
    if me.top_role <= target_role:
        await interaction.followup.send(f"Mon rôle le plus élevé doit être au-dessus de {target_role.mention}.")
        return

    # Déterminer la cible
    def is_target(member: nextcord.Member) -> bool:
        if everyone:
            return True
        if filter_role is not None:
            return filter_role in member.roles
        return False

    candidates = [m for m in guild.members if is_target(m) and target_role not in m.roles]
    total = len(candidates)
    if total == 0:
        scope = "tout le monde" if everyone else f"les membres avec {filter_role.mention}"
        await interaction.followup.send(f"Aucun membre à mettre à jour pour {scope}.")
        return

    success = 0
    failed = 0
    skipped_hierarchy = 0

    # Attribution en série avec pauses pour éviter le rate-limit
    for idx, member in enumerate(candidates, start=1):
        try:
            # Vérifier hiérarchie côté membre (le rôle cible doit être au-dessus des rôles du membre si contraintes)
            await member.add_roles(target_role, reason=f"MassGive par {interaction.user}")
            success += 1
        except nextcord.HTTPException as e:
            failed += 1
        except Exception:
            failed += 1

        if idx % 10 == 0:
            # Mise à jour de progression toutes les 10 opérations
            await asyncio.sleep(0.5)

    embed = nextcord.Embed(
        title="✅ Attribution en masse terminée",
        color=0x00ff00
    )
    scope = "@everyone" if everyone else (f"membres avec {filter_role.mention}" if filter_role else "")
    embed.add_field(name="Cible", value=scope, inline=False)
    embed.add_field(name="Rôle attribué", value=target_role.mention, inline=True)
    embed.add_field(name="Total", value=str(total), inline=True)
    embed.add_field(name="Succès", value=str(success), inline=True)
    embed.add_field(name="Échecs", value=str(failed), inline=True)

    await interaction.followup.send(embed=embed)

# Lancer le bot
bot.run(os.getenv('DISCORD_TOKEN'))
