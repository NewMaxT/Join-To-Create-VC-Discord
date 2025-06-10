import os
import json
import nextcord
from nextcord.ext import commands, tasks
from dotenv import load_dotenv
from typing import Dict, Optional, Set
from localization import Localization
from config import ServerConfig
import asyncio

# Charger les variables d'environnement
load_dotenv()

# Configuration du bot avec les intents
intents = nextcord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.members = True  # Required for autorole

bot = commands.Bot(command_prefix='!', intents=intents)

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
    except Exception as e:
        print(f"Erreur lors du chargement des configurations : {e}")

@bot.event
async def on_ready():
    print(f'Bot prêt ! Connecté en tant que {bot.user.name}')
    # Charger les configurations au démarrage
    load_configs()
    server_config.load_config()
    # Start background tasks
    check_role_expiry.start()
    
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

@tasks.loop(hours=1)
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
                except nextcord.HTTPException:
                    pass

@bot.event
async def on_member_join(member):
    """Handle new member joins"""
    guild_id = member.guild.id
    config = server_config.get_autorole(guild_id)
    
    if config:
        # Check if we should skip rejoining members
        if config['check_rejoin'] and server_config.has_member_joined_before(guild_id, member.id):
            return
            
        role = member.guild.get_role(config['role_id'])
        if role:
            try:
                await member.add_roles(role)
                server_config.add_joined_member(guild_id, member.id)
            except nextcord.HTTPException:
                pass

@bot.event
async def on_message(message):
    """Handle messages and sticky messages"""
    if message.author.bot:
        return
        
    # Process sticky messages
    guild_id = message.guild.id if message.guild else None
    channel_id = message.channel.id if message.channel else None
    
    if guild_id and channel_id:
        sticky_config = server_config.get_sticky_message(guild_id, channel_id)
        if sticky_config:
            # Delete all previous sticky messages from the bot
            try:
                # Fetch last 50 messages to find and delete old sticky messages
                async for old_message in message.channel.history(limit=50):
                    if (old_message.author == bot.user and 
                        old_message.content == sticky_config['content']):
                        try:
                            await old_message.delete()
                        except nextcord.HTTPException:
                            pass
            except nextcord.HTTPException:
                pass
            
            # Wait a short time to let other messages appear
            await asyncio.sleep(0.5)
            
            # Send new sticky message
            new_message = await message.channel.send(sticky_config['content'])
            server_config.update_sticky_message_id(guild_id, channel_id, new_message.id)
    
    await bot.process_commands(message)

@bot.group(name='config')
@commands.has_permissions(administrator=True)
async def config_group(ctx):
    """Configuration commands group"""
    if ctx.invoked_subcommand is None:
        await ctx.send(loc.get_text(ctx.guild.id, 'help.title'))

@config_group.command(name='language')
async def set_language(ctx, language: str):
    """Set the bot's language for this server"""
    if loc.set_language(ctx.guild.id, language):
        await ctx.send(loc.get_text(ctx.guild.id, 'config.language.set_success'))
    else:
        await ctx.send(loc.get_text(ctx.guild.id, 'config.language.invalid', 
                                  langs=', '.join(loc.get_available_languages())))

@config_group.command(name='autorole')
async def set_autorole(ctx, role: nextcord.Role, expiry_minutes: Optional[int] = None, check_rejoin: bool = False):
    """Configure auto-role for new members"""
    # Validate expiry_minutes if provided
    if expiry_minutes is not None and expiry_minutes <= 0:
        await ctx.send("Expiry time must be greater than 0 minutes!")
        return
        
    server_config.set_autorole(ctx.guild.id, role.id, expiry_minutes, check_rejoin)
    
    # Send confirmation message
    await ctx.send(loc.get_text(ctx.guild.id, 'config.autorole.set_success', role=role.mention))
    
    if expiry_minutes:
        await ctx.send(loc.get_text(ctx.guild.id, 'config.autorole.expiry_set', minutes=expiry_minutes))
    
    if check_rejoin:
        await ctx.send(loc.get_text(ctx.guild.id, 'config.autorole.rejoin_enabled'))

@config_group.command(name='remove_autorole')
async def remove_autorole(ctx):
    """Remove auto-role configuration"""
    server_config.remove_autorole(ctx.guild.id)
    await ctx.send(loc.get_text(ctx.guild.id, 'config.autorole.remove_success'))

@config_group.command(name='sticky')
async def set_sticky(ctx, channel: nextcord.TextChannel, *, content: str):
    """Set a sticky message in a channel"""
    server_config.set_sticky_message(ctx.guild.id, channel.id, content)
    await ctx.send(loc.get_text(ctx.guild.id, 'config.sticky.set_success', channel=channel.mention))

@config_group.command(name='remove_sticky')
async def remove_sticky(ctx, channel: nextcord.TextChannel):
    """Remove sticky message from a channel"""
    server_config.remove_sticky_message(ctx.guild.id, channel.id)
    await ctx.send(loc.get_text(ctx.guild.id, 'config.sticky.remove_success', channel=channel.mention))

@bot.command()
@commands.has_permissions(administrator=True)
async def setupvoice(
    ctx, 
    template_name: str = "Channel of {user}",
    position: str = "after",
    creator_name: str = "➕ Join to Create",
    user_limit: int = 0
):
    """Creates a voice channel creator with custom parameters"""
    guild = ctx.guild
    current_category = ctx.channel.category

    # Validate template name
    if not template_name or len(template_name) > 100:
        await ctx.send("The template name must be between 1 and 100 characters!")
        return

    # Validate creator name
    if not creator_name or len(creator_name) > 100:
        await ctx.send("The creator channel name must be between 1 and 100 characters!")
        return

    # Validate position
    if position not in ["before", "after"]:
        await ctx.send("Position must be 'before' or 'after'!")
        return

    # Validate user limit
    if user_limit < 0 or user_limit > 99:
        await ctx.send("User limit must be between 0 and 99 (0 = unlimited)!")
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

    location = loc.get_text(ctx.guild.id, 'commands.location_before' if position == "before" else 'commands.location_after')
    limit = loc.get_text(ctx.guild.id, 'commands.limit_unlimited') if user_limit == 0 else str(user_limit)
    
    await ctx.send(loc.get_text(
        ctx.guild.id,
        'commands.setup_success',
        creator_name=creator_name,
        channel=create_channel.mention,
        location=location,
        template=template_name,
        limit=limit
    ))

@bot.command()
@commands.has_permissions(administrator=True)
async def removevoice(ctx, channel: nextcord.VoiceChannel):
    """Removes a voice channel creator"""
    if channel.id in guild_configs.get(ctx.guild.id, {}):
        await channel.delete()
        del guild_configs[ctx.guild.id][channel.id]
        if not guild_configs[ctx.guild.id]:
            del guild_configs[ctx.guild.id]
        # Save configurations
        save_configs()
        await ctx.send(loc.get_text(ctx.guild.id, 'commands.remove_success'))
    else:
        await ctx.send(loc.get_text(ctx.guild.id, 'commands.remove_error'))

@bot.command()
@commands.has_permissions(administrator=True)
async def listvoice(ctx):
    """Lists all voice channel creators on the server"""
    if ctx.guild.id not in guild_configs or not guild_configs[ctx.guild.id]:
        await ctx.send(loc.get_text(ctx.guild.id, 'commands.list_none'))
        return

    creators = []
    for creator_id, config in guild_configs[ctx.guild.id].items():
        channel = ctx.guild.get_channel(creator_id)
        if channel:
            position = config.position if config.position is not None else loc.get_text(ctx.guild.id, 'commands.default_position')
            creators.append(loc.get_text(
                ctx.guild.id,
                'commands.list_creator_info',
                channel=channel.mention,
                template=config.template_name,
                position=position
            ))

    if creators:
        embed = nextcord.Embed(
            title=loc.get_text(ctx.guild.id, 'commands.list_creators'),
            color=0x00ff00
        )
        for i, creator in enumerate(creators, 1):
            embed.add_field(name=f"Creator {i}", value=creator, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(loc.get_text(ctx.guild.id, 'commands.list_none_active'))

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

@bot.remove_command('help')  # Remove default help command

@bot.command()
@commands.has_permissions(administrator=True)
async def help(ctx):
    """Display bot help (Admin only)"""
    embed = nextcord.Embed(
        title=loc.get_text(ctx.guild.id, 'help.title'),
        description=loc.get_text(ctx.guild.id, 'help.description'),
        color=0x00ff00
    )

    # setupvoice command
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.setup_title'),
        value=loc.get_text(ctx.guild.id, 'help.setup_desc'),
        inline=False
    )

    # removevoice command
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.remove_title'),
        value=loc.get_text(ctx.guild.id, 'help.remove_desc'),
        inline=False
    )

    # listvoice command
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.list_title'),
        value=loc.get_text(ctx.guild.id, 'help.list_desc'),
        inline=False
    )

    # Configuration commands
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.config_title'),
        value=loc.get_text(ctx.guild.id, 'help.config_desc'),
        inline=False
    )

    # help command
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.help_title'),
        value=loc.get_text(ctx.guild.id, 'help.help_desc'),
        inline=False
    )

    # Important notes
    embed.add_field(
        name=loc.get_text(ctx.guild.id, 'help.notes_title'),
        value=loc.get_text(ctx.guild.id, 'help.notes_desc'),
        inline=False
    )

    # Footer with version
    embed.set_footer(text=loc.get_text(ctx.guild.id, 'help.footer'))

    await ctx.send(embed=embed)

# Add error handler for missing permissions
@help.error
@setupvoice.error
@removevoice.error
@listvoice.error
@config_group.error
async def command_error(ctx, error):
    """Handle permission errors for commands"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(loc.get_text(ctx.guild.id, 'errors.missing_permissions'))
    else:
        # Log other errors
        print(f"Error in {ctx.command}: {error}")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for uncaught command errors"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(loc.get_text(ctx.guild.id, 'errors.missing_permissions'))
    else:
        # Log other errors
        print(f"Uncaught error in {ctx.command}: {error}")

# Lancer le bot
bot.run(os.getenv('DISCORD_TOKEN'))
