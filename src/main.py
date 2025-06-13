import os
import json
import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands, tasks
from dotenv import load_dotenv
from typing import Dict, Optional, Set
from localization import Localization
from config import ServerConfig
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

activity = Activity(type=ActivityType.playing, name="Fully Open-Source")
bot = commands.Bot(intents=intents, activity=activity)

# Initialize localization and server config
loc = Localization()
server_config = ServerConfig()

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
    """Bot startup event"""
    print(f'Bot ready! Connected as {bot.user.name}')

    # Load configurations at startup
    load_configs()
    server_config.load_config()
    
    # Print autorole information for each guild
    for guild in bot.guilds:
        config = server_config.get_autorole(guild.id)
        if config:
            role = guild.get_role(config['role_id'])
            if role:
                print(f"\nAutorole information for {guild.name}:")
                print(f"Role: {role.name}")
                
                # Get members with the role
                members_with_role = [member for member in guild.members if role in member.roles]
                
                if members_with_role:
                    print(f"Members with {role.name}:")
                    for member in members_with_role:
                        # Get expiry time if set
                        expiry_time = server_config.get_role_expiry_time(guild.id, member.id)
                        if expiry_time:
                            current_time = datetime.now().timestamp()
                            remaining_time = expiry_time - current_time
                            if remaining_time > 0:
                                minutes = int(remaining_time / 60)
                                print(f"  - {member.display_name}: {minutes} minutes remaining")
                            else:
                                print(f"  - {member.display_name}: Role expired")
                        else:
                            print(f"  - {member.display_name}: No expiry")
                else:
                    print("No members currently have this role")
    
    # Start background tasks
    check_role_expiry.start()
    check_sticky_messages.start()
    
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
    """Check and remove expired roles"""
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
                    print(f"Removed role {role.name} from {member.display_name}")
                except nextcord.HTTPException:
                    print(f"Error removing role {role.name} from {member.display_name}")
                    pass

@tasks.loop(seconds=5)
async def check_sticky_messages():
    """Check and maintain sticky messages every 5 seconds"""
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
                            print(f"Deleted old sticky message in channel {channel_id}")
                        except nextcord.HTTPException:
                            pass

                    # Post new sticky message
                    new_message = await channel.send(sticky_config['content'])
                    sticky_config['last_message_id'] = new_message.id
                    server_config.update_sticky_message_id(guild_id, channel_id, new_message.id)
                    print(f"Posted new sticky message in channel {channel_id}")

            except Exception as e:
                print(f"Error maintaining sticky message in channel {channel_id}: {e}")

@bot.event
async def on_member_join(member):
    """Handle new member joins"""
    print(f"New member joined: {member.display_name}")
    guild_id = member.guild.id
    config = server_config.get_autorole(guild_id)
    
    if config:
        # Check if we should skip rejoining members
        if config['check_rejoin'] and server_config.has_member_joined_before(guild_id, member.id):
            print(f"Skipping rejoining member {member.display_name} because they have already joined before")
            return
            
        role = member.guild.get_role(config['role_id'])
        if role:
            try:
                await member.add_roles(role)
                server_config.add_joined_member(guild_id, member.id)
                print(f"Added role {role.name} to {member.display_name}")
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
                    
                    print(f"Missing Permissions: {', '.join(missing_perms)}")
                    print(f"Error details: {str(e)}")
                else:
                    print(f"Error adding role {role.name} to {member.display_name}, non-permission error: {str(e)}")
        else:
            print(f"Bad role configuration found for guild {guild_id}")
    else:
        print(f"No autorole configuration found for guild {guild_id}")

@bot.slash_command(name="config", description="Configuration commands group")
@commands.has_permissions(administrator=True)
async def config(interaction: Interaction):
    """Configuration commands group"""
    pass

@config.subcommand(name="language", description="Set the bot's language for this server")
@commands.has_permissions(administrator=True)
async def set_language(
    interaction: Interaction,
    language: str = SlashOption(description="The language code to set (e.g. 'en', 'fr')")
):
    """Set the bot's language for this server"""
    if loc.set_language(interaction.guild_id, language):
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.language.set_success'))
    else:
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.language.invalid', 
                                  langs=', '.join(loc.get_available_languages())))

@config.subcommand(name="autorole", description="Configure auto-role for new members")
@commands.has_permissions(administrator=True)
async def set_autorole(
    interaction: Interaction,
    role: nextcord.Role = SlashOption(description="The role to automatically assign"),
    expiry_minutes: Optional[int] = SlashOption(description="Optional: Minutes until role expires", required=False),
    check_rejoin: bool = SlashOption(description="Whether to check if members are rejoining", required=False, default=False)
):
    """Configure auto-role for new members"""
    # Validate expiry_minutes if provided
    if expiry_minutes is not None and expiry_minutes <= 0:
        await interaction.response.send_message("Expiry time must be greater than 0 minutes!")
        return
        
    server_config.set_autorole(interaction.guild_id, role.id, expiry_minutes, check_rejoin)
    
    # Send confirmation message
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.autorole.set_success', role=role.mention))
    
    if expiry_minutes:
        await interaction.followup.send(loc.get_text(interaction.guild_id, 'config.autorole.expiry_set', minutes=expiry_minutes))
    
    if check_rejoin:
        await interaction.followup.send(loc.get_text(interaction.guild_id, 'config.autorole.rejoin_enabled'))

@config.subcommand(name="remove_autorole", description="Remove auto-role configuration")
@commands.has_permissions(administrator=True)
async def remove_autorole(interaction: Interaction):
    """Remove auto-role configuration"""
    server_config.remove_autorole(interaction.guild_id)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.autorole.remove_success'))

@config.subcommand(name="sticky", description="Set a sticky message in a channel")
@commands.has_permissions(administrator=True)
async def set_sticky(
    interaction: Interaction,
    channel: nextcord.TextChannel = SlashOption(description="The channel to set the sticky message in"),
    content: str = SlashOption(description="The content of the sticky message")
):
    """Set a sticky message in a channel"""
    server_config.set_sticky_message(interaction.guild_id, channel.id, content, last_message_id=None)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.sticky.set_success', channel=channel.mention))

@config.subcommand(name="remove_sticky", description="Remove sticky message from a channel")
@commands.has_permissions(administrator=True)
async def remove_sticky(
    interaction: Interaction,
    channel: nextcord.TextChannel = SlashOption(description="The channel to remove the sticky message from")
):
    """Remove sticky message from a channel"""
    server_config.remove_sticky_message(interaction.guild_id, channel.id)
    await interaction.response.send_message(loc.get_text(interaction.guild_id, 'config.sticky.remove_success', channel=channel.mention))

@bot.slash_command(name="setupvoice", description="Creates a voice channel creator with custom parameters")
@commands.has_permissions(administrator=True)
async def setupvoice(
    interaction: Interaction,
    template_name: str = SlashOption(
        description="Template for channel names, use {user} for the user's name",
        default="Channel of {user}"
    ),
    position: str = SlashOption(
        description="Position of new channels relative to creator",
        choices=["before", "after"],
        default="after"
    ),
    creator_name: str = SlashOption(
        description="Name of the creator channel",
        default="➕ Join to Create"
    ),
    user_limit: int = SlashOption(
        description="User limit for created channels (0 = unlimited)",
        min_value=0,
        max_value=99,
        default=0
    )
):
    """Creates a voice channel creator with custom parameters"""
    guild = interaction.guild
    current_category = interaction.channel.category

    # Validate template name
    if not template_name or len(template_name) > 100:
        await interaction.response.send_message("The template name must be between 1 and 100 characters!")
        return

    # Validate creator name
    if not creator_name or len(creator_name) > 100:
        await interaction.response.send_message("The creator channel name must be between 1 and 100 characters!")
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

@bot.slash_command(name="removevoice", description="Removes a voice channel creator")
@commands.has_permissions(administrator=True)
async def removevoice(
    interaction: Interaction,
    channel: nextcord.VoiceChannel = SlashOption(description="The voice channel creator to remove")
):
    """Removes a voice channel creator"""
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

@bot.slash_command(name="listvoice", description="Lists all voice channel creators on the server")
@commands.has_permissions(administrator=True)
async def listvoice(interaction: Interaction):
    """Lists all voice channel creators on the server"""
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

@bot.slash_command(name="help", description="Display bot help")
@commands.has_permissions(administrator=True)
async def cmds_help(interaction: Interaction):
    """Display bot help (Admin only)"""
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

    # Configuration commands
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

    await interaction.response.send_message(embed=embed)

# Update error handlers for slash commands
@bot.event
async def on_application_command_error(interaction: Interaction, error):
    """Global error handler for slash commands"""
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message(loc.get_text(interaction.guild_id, 'errors.missing_permissions'), ephemeral=True)
    else:
        # Log other errors
        print(f"Error in slash command {interaction.application_command.name}: {error}")
        await interaction.response.send_message("An error occurred while executing this command.", ephemeral=True)

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
            print(f"Moved member {member.display_name} to {new_channel.name}")
    
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

# Lancer le bot
bot.run(os.getenv('DISCORD_TOKEN'))
