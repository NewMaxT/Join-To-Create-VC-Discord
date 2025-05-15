import os
import json
import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv
from typing import Dict, Optional, Set

# Charger les variables d'environnement
load_dotenv()

# Configuration du bot avec les intents
intents = nextcord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

class VoiceCreatorConfig:
    def __init__(self, channel_id: int, template_name: str, position: Optional[int]):
        self.channel_id = channel_id
        self.template_name = template_name
        self.position = position
    
    def to_dict(self) -> dict:
        """Convertit la configuration en dictionnaire pour la sauvegarde JSON"""
        return {
            'channel_id': self.channel_id,
            'template_name': self.template_name,
            'position': self.position
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VoiceCreatorConfig':
        """Crée une configuration à partir d'un dictionnaire JSON"""
        return cls(
            channel_id=data['channel_id'],
            template_name=data['template_name'],
            position=data['position']
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

@bot.command()
@commands.has_permissions(administrator=True)
async def setupvoice(
    ctx, 
    template_name: str = "Salon de {user}",
    position: str = "below",
    creator_name: str = "➕ Rejoindre pour Créer"
):
    """
    Crée un salon vocal créateur avec des paramètres personnalisés
    
    Paramètres:
    - template_name: Le modèle pour les noms des nouveaux salons. Utilisez {user} pour le nom de l'utilisateur
    - position: Où placer les nouveaux salons ('above' = au-dessus ou 'below' = en-dessous)
    - creator_name: Le nom du salon créateur (par défaut: "➕ Rejoindre pour Créer")
    """
    guild = ctx.guild
    current_category = ctx.channel.category

    # Valider le nom du modèle
    if not template_name or len(template_name) > 100:
        await ctx.send("Le nom du modèle doit contenir entre 1 et 100 caractères !")
        return

    # Valider le nom du créateur
    if not creator_name or len(creator_name) > 100:
        await ctx.send("Le nom du salon créateur doit contenir entre 1 et 100 caractères !")
        return

    # Créer le salon vocal créateur
    create_channel = await guild.create_voice_channel(
        name=creator_name,
        category=current_category
    )

    # Initialiser la configuration du serveur si elle n'existe pas
    if guild.id not in guild_configs:
        guild_configs[guild.id] = {}

    # Stocker la configuration
    position_value = None
    if position == "above":
        position_value = create_channel.position - 1
    elif position == "below":
        position_value = create_channel.position + 1
    
    guild_configs[guild.id][create_channel.id] = VoiceCreatorConfig(
        channel_id=create_channel.id,
        template_name=template_name,
        position=position_value
    )

    # Sauvegarder les configurations
    save_configs()

    location_msg = (
        "au-dessus du salon créateur" if position == "above"
        else "en-dessous du salon créateur"
    )
    
    await ctx.send(
        f"Le créateur de salon vocal a été configuré !\n"
        f"- Nom du salon créateur : `{creator_name}`\n"
        f"- Rejoignez {create_channel.mention} pour créer un nouveau salon\n"
        f"- Les nouveaux salons seront créés {location_msg}\n"
        f"- Modèle de nom : `{template_name}`"
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def removevoice(ctx, channel: nextcord.VoiceChannel):
    """Supprime un créateur de salon vocal"""
    if channel.id in guild_configs.get(ctx.guild.id, {}):
        await channel.delete()
        del guild_configs[ctx.guild.id][channel.id]
        if not guild_configs[ctx.guild.id]:
            del guild_configs[ctx.guild.id]
        # Sauvegarder les configurations
        save_configs()
        await ctx.send(f"Le créateur de salon vocal a été supprimé !")
    else:
        await ctx.send("Ce salon n'est pas un créateur de salon vocal !")

@bot.command()
@commands.has_permissions(administrator=True)
async def listvoice(ctx):
    """Liste tous les créateurs de salons vocaux du serveur"""
    if ctx.guild.id not in guild_configs or not guild_configs[ctx.guild.id]:
        await ctx.send("Aucun créateur de salon vocal configuré sur ce serveur !")
        return

    creators = []
    for creator_id, config in guild_configs[ctx.guild.id].items():
        channel = ctx.guild.get_channel(creator_id)
        if channel:
            creators.append(
                f"Salon : {channel.mention}\n"
                f"Modèle : `{config.template_name}`\n"
                f"Position : {'position personnalisée' if config.position else 'ordre de la catégorie'}\n"
            )

    if creators:
        embed = nextcord.Embed(title="Créateurs de Salons Vocaux", color=0x00ff00)
        for i, creator in enumerate(creators, 1):
            embed.add_field(name=f"Créateur {i}", value=creator, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Aucun créateur de salon vocal actif trouvé !")

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
                category=after.channel.category
            )

            # Définir la position si spécifiée
            if config.position is not None:
                try:
                    await new_channel.edit(position=config.position)
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

# Lancer le bot
bot.run(os.getenv('DISCORD_TOKEN'))
