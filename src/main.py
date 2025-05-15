import os
import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv
from typing import Dict, Optional

# Charger les variables d'environnement
load_dotenv()

# Configuration du bot avec les intents
intents = nextcord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

class VoiceCreatorConfig:
    def __init__(self, channel_id: int, template_name: str, category_id: Optional[int], position: Optional[int]):
        self.channel_id = channel_id
        self.template_name = template_name
        self.category_id = category_id
        self.position = position

# Dictionnaire pour stocker les configurations des créateurs de salons vocaux par serveur
# Format: guild_id -> Dict[creator_channel_id, VoiceCreatorConfig]
guild_configs: Dict[int, Dict[int, VoiceCreatorConfig]] = {}

@bot.event
async def on_ready():
    print(f'Bot prêt ! Connecté en tant que {bot.user.name}')

@bot.command()
@commands.has_permissions(administrator=True)
async def setupvoice(
    ctx, 
    template_name: str = "Salon de {user}",
    category: Optional[nextcord.CategoryChannel] = None,
    position: str = "below"
):
    """
    Crée un salon vocal créateur avec des paramètres personnalisés
    
    Paramètres:
    - template_name: Le modèle pour les noms des nouveaux salons. Utilisez {user} pour le nom de l'utilisateur
    - category: Catégorie optionnelle pour placer les nouveaux salons
    - position: Où placer les nouveaux salons ('above' = au-dessus, 'below' = en-dessous, ou 'category' = dans la catégorie)
    """
    guild = ctx.guild
    current_category = ctx.channel.category if position != "category" else category

    # Valider le nom du modèle
    if not template_name or len(template_name) > 100:
        await ctx.send("Le nom du modèle doit contenir entre 1 et 100 caractères !")
        return

    # Créer le salon vocal créateur
    create_channel = await guild.create_voice_channel(
        name="➕ Rejoindre pour Créer",
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

    category_id = category.id if category and position == "category" else None
    
    guild_configs[guild.id][create_channel.id] = VoiceCreatorConfig(
        channel_id=create_channel.id,
        template_name=template_name,
        category_id=category_id,
        position=position_value
    )

    location_msg = (
        f"dans la catégorie '{category.name}'" if category and position == "category"
        else "au-dessus du salon créateur" if position == "above"
        else "en-dessous du salon créateur"
    )
    
    await ctx.send(
        f"Le créateur de salon vocal a été configuré !\n"
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
            category_name = (
                ctx.guild.get_channel(config.category_id).name
                if config.category_id
                else "même que le créateur"
            )
            creators.append(
                f"Salon : {channel.mention}\n"
                f"Modèle : `{config.template_name}`\n"
                f"Catégorie : {category_name}\n"
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
            
            # Déterminer la catégorie et la position pour le nouveau salon
            category = None
            if config.category_id:
                category = member.guild.get_channel(config.category_id)
            else:
                category = after.channel.category

            # Créer le nom du salon à partir du modèle
            channel_name = config.template_name.replace("{user}", member.display_name)
            
            # Créer le nouveau salon
            new_channel = await member.guild.create_voice_channel(
                name=channel_name,
                category=category
            )

            # Définir la position si spécifiée
            if config.position is not None:
                try:
                    await new_channel.edit(position=config.position)
                except nextcord.HTTPException:
                    pass  # Ignorer les erreurs de position
            
            # Déplacer le membre dans le nouveau salon
            await member.move_to(new_channel)
    
    # Nettoyer les salons vides
    if before.channel is not None:
        # Vérifier si le salon n'est pas un créateur et est vide
        is_creator = any(
            before.channel.id == config.channel_id
            for configs in guild_configs.values()
            for config in configs.values()
        )
        
        if (
            not is_creator and
            len(before.channel.members) == 0 and
            before.channel.category == after.channel.category
        ):
            await before.channel.delete()

# Lancer le bot
bot.run(os.getenv('DISCORD_TOKEN'))
