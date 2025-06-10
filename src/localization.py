from typing import Dict, Any

LOCALES = {
    'en': {
        'help': {
            'title': '📢 Help',
            'description': 'This bot automatically creates temporary voice channels and provides server management features.',
            'setup_title': '!setupvoice [name_template] [position] [creator_name] [user_limit]',
            'setup_desc': (
                'Creates a new voice channel creator.\n'
                '```\n'
                'Arguments:\n'
                '- name_template: Template for names (default: "Channel of {user}")\n'
                '- position: "before" or "after" (default: "after")\n'
                '- creator_name: Name of the creator channel\n'
                '- user_limit: User limit (0-99, 0 = unlimited)\n'
                '\n'
                'Examples:\n'
                '!setupvoice\n'
                '!setupvoice "Gaming with {user}"\n'
                '!setupvoice "Channel of {user}" before\n'
                '!setupvoice "Channel of {user}" after "🎮 Create" 5\n'
                '```'
            ),
            'remove_title': '!removevoice <channel>',
            'remove_desc': (
                'Removes a voice channel creator.\n'
                '```\n'
                'Argument:\n'
                '- channel: Mention or ID of the channel to remove\n'
                '\n'
                'Example:\n'
                '!removevoice #join-to-create\n'
                '```'
            ),
            'list_title': '!listvoice',
            'list_desc': (
                'Lists all voice channel creators on the server.\n'
                '```\n'
                'Shows for each channel:\n'
                '- Channel name and link\n'
                '- Name template used\n'
                '- Position of new channels\n'
                '```'
            ),
            'config_title': 'Configuration Commands',
            'config_desc': (
                'Server configuration commands.\n'
                '```\n'
                '!config language <lang>\n'
                '- Set bot language (en/fr)\n'
                '\n'
                '!config autorole <role> [expiry_minutes] [check_rejoin]\n'
                '- Set auto-role for new members\n'
                '- expiry_minutes: Remove role after X minutes\n'
                '- check_rejoin: Don\'t give role to rejoining members\n'
                '\n'
                '!config remove_autorole\n'
                '- Disable auto-role feature\n'
                '\n'
                '!config sticky <channel> <message>\n'
                '- Set sticky message in channel\n'
                '\n'
                '!config remove_sticky <channel>\n'
                '- Remove sticky message from channel\n'
                '```'
            ),
            'help_title': '!help',
            'help_desc': 'Shows this help message.',
            'notes_title': '📝 Important Notes',
            'notes_desc': (
                '• Channels are created in the same category as the creator\n'
                '• The {user} variable is replaced with the member\'s name\n'
                '• Empty channels are automatically deleted\n'
                '• Only administrators can use the commands\n'
                '• Configurations are automatically saved\n'
                '• User limits apply to new channels\n'
                '• Auto-role can expire after specified minutes\n'
                '• Sticky messages stay at bottom of channels'
            ),
            'footer': 'Made by Maxence G. • v1.2'
        },
        'commands': {
            'setup_success': (
                'Voice channel creator has been configured!\n'
                '- Creator channel name: `{creator_name}`\n'
                '- Join {channel} to create a new channel\n'
                '- New channels will be created {location}\n'
                '- Name template: `{template}`\n'
                '- User limit: {limit}'
            ),
            'location_before': 'before the creator channel',
            'location_after': 'after the creator channel',
            'limit_unlimited': 'unlimited',
            'remove_success': 'The voice channel creator has been removed!',
            'remove_error': 'This channel is not a voice channel creator!',
            'list_none': 'No voice channel creators configured on this server!',
            'list_none_active': 'No active voice channel creators found!',
            'list_creators': 'Voice Channel Creators',
            'list_creator_info': (
                'Channel: {channel}\n'
                'Template: `{template}`\n'
                'Position: {position}\n'
            ),
            'default_position': 'Default'
        },
        'config': {
            'autorole': {
                'set_success': 'Auto-role has been set to {role}!',
                'remove_success': 'Auto-role has been disabled!',
                'expiry_set': 'Role will be removed after {minutes} minutes!',
                'expiry_disabled': 'Role expiry has been disabled!',
                'rejoin_enabled': 'Role will not be given to rejoining members!',
                'rejoin_disabled': 'Role will be given to all new members!'
            },
            'sticky': {
                'set_success': 'Sticky message has been set in {channel}!',
                'remove_success': 'Sticky message has been disabled in {channel}!',
                'content_updated': 'Sticky message content has been updated!'
            },
            'language': {
                'set_success': 'Language has been set to English!',
                'invalid': 'Invalid language! Available languages: {langs}'
            }
        }
    },
    'fr': {
        'help': {
            'title': '📢 Aide',
            'description': 'Ce bot permet de créer automatiquement des salons vocaux temporaires et fournit des fonctionnalités de gestion du serveur.',
            'setup_title': '!setupvoice [modele_nom] [position] [nom_createur] [limite_users]',
            'setup_desc': (
                'Crée un nouveau salon créateur de vocaux.\n'
                '```\n'
                'Arguments :\n'
                '- modele_nom : Modèle pour les noms (défaut : "Salon de {user}")\n'
                '- position : "before" ou "after" (défaut : "after")\n'
                '- nom_createur : Nom du salon créateur\n'
                '- limite_users : Limite d\'utilisateurs (0-99, 0 = illimité)\n'
                '\n'
                'Exemples :\n'
                '!setupvoice\n'
                '!setupvoice "Gaming avec {user}"\n'
                '!setupvoice "Salon de {user}" before\n'
                '!setupvoice "Salon de {user}" after "🎮 Créer" 5\n'
                '```'
            ),
            'remove_title': '!removevoice <salon>',
            'remove_desc': (
                'Supprime un salon créateur.\n'
                '```\n'
                'Argument :\n'
                '- salon : Mention ou ID du salon à supprimer\n'
                '\n'
                'Exemple :\n'
                '!removevoice #rejoindre-pour-creer\n'
                '```'
            ),
            'list_title': '!listvoice',
            'list_desc': (
                'Liste tous les salons créateurs du serveur.\n'
                '```\n'
                'Affiche pour chaque salon :\n'
                '- Nom et lien du salon\n'
                '- Modèle de nom utilisé\n'
                '- Position des nouveaux salons\n'
                '```'
            ),
            'config_title': 'Commandes de Configuration',
            'config_desc': (
                'Commandes de configuration du serveur.\n'
                '```\n'
                '!config language <lang>\n'
                '- Définir la langue du bot (en/fr)\n'
                '\n'
                '!config autorole <role> [expiry_minutes] [check_rejoin]\n'
                '- Définir un rôle automatique pour les nouveaux membres\n'
                '- expiry_minutes: Retirer le rôle après X minutes\n'
                '- check_rejoin: Ne pas donner le rôle aux membres qui rejoignent à nouveau\n'
                '\n'
                '!config remove_autorole\n'
                '- Désactiver la fonction de rôle automatique\n'
                '\n'
                '!config sticky <channel> <message>\n'
                '- Définir un message épinglé dans un salon\n'
                '\n'
                '!config remove_sticky <channel>\n'
                '- Retirer le message épinglé d\'un salon\n'
                '```'
            ),
            'help_title': '!help',
            'help_desc': 'Affiche ce message d\'aide.',
            'notes_title': '📝 Notes importantes',
            'notes_desc': (
                '• Les salons sont créés dans la même catégorie que le créateur\n'
                '• La variable {user} est remplacée par le nom du membre\n'
                '• Les salons vides sont automatiquement supprimés\n'
                '• Seuls les administrateurs peuvent utiliser les commandes\n'
                '• Les configurations sont sauvegardées automatiquement\n'
                '• La limite d\'utilisateurs s\'applique aux nouveaux salons\n'
                '• Le rôle auto peut expirer après un nombre de minutes\n'
                '• Les messages épinglés restent en bas des salons'
            ),
            'footer': 'Made by Maxence G. • v1.2'
        },
        'commands': {
            'setup_success': (
                'Le créateur de salon vocal a été configuré !\n'
                '- Nom du salon créateur : `{creator_name}`\n'
                '- Rejoignez {channel} pour créer un nouveau salon\n'
                '- Les nouveaux salons seront créés {location}\n'
                '- Modèle de nom : `{template}`\n'
                '- Limite d\'utilisateurs : {limit}'
            ),
            'location_before': 'avant le salon créateur',
            'location_after': 'après le salon créateur',
            'limit_unlimited': 'illimité',
            'remove_success': 'Le créateur de salon vocal a été supprimé !',
            'remove_error': 'Ce salon n\'est pas un créateur de salon vocal !',
            'list_none': 'Aucun créateur de salon vocal configuré sur ce serveur !',
            'list_none_active': 'Aucun créateur de salon vocal actif trouvé !',
            'list_creators': 'Créateurs de Salons Vocaux',
            'list_creator_info': (
                'Salon : {channel}\n'
                'Modèle : `{template}`\n'
                'Position : {position}\n'
            ),
            'default_position': 'Par défaut'
        },
        'config': {
            'autorole': {
                'set_success': 'Le rôle automatique a été défini sur {role} !',
                'remove_success': 'Le rôle automatique a été désactivé !',
                'expiry_set': 'Le rôle sera retiré après {minutes} minutes !',
                'expiry_disabled': 'L\'expiration du rôle a été désactivée !',
                'rejoin_enabled': 'Le rôle ne sera pas donné aux membres qui rejoignent à nouveau !',
                'rejoin_disabled': 'Le rôle sera donné à tous les nouveaux membres !'
            },
            'sticky': {
                'set_success': 'Le message épinglé a été défini dans {channel} !',
                'remove_success': 'Le message épinglé a été désactivé dans {channel} !',
                'content_updated': 'Le contenu du message épinglé a été mis à jour !'
            },
            'language': {
                'set_success': 'La langue a été définie sur Français !',
                'invalid': 'Langue invalide ! Langues disponibles : {langs}'
            }
        }
    }
}

class Localization:
    def __init__(self):
        self.guild_languages: Dict[int, str] = {}
        self.default_language = 'en'
    
    def get_text(self, guild_id: int, key_path: str, **kwargs: Any) -> str:
        """
        Get localized text for the given key path and guild
        Example: loc.get_text(guild_id, 'help.title')
        """
        lang = self.guild_languages.get(guild_id, self.default_language)
        
        # Navigate through the nested dictionary
        text = LOCALES[lang]
        for key in key_path.split('.'):
            text = text[key]
            
        # Format the text with provided kwargs
        return text.format(**kwargs) if kwargs else text
    
    def set_language(self, guild_id: int, language: str) -> bool:
        """Set the language for a guild. Returns True if successful."""
        if language in LOCALES:
            self.guild_languages[guild_id] = language
            return True
        return False
    
    def get_available_languages(self) -> list:
        """Get list of available languages"""
        return list(LOCALES.keys()) 