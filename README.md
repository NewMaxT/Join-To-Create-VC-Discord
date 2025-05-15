# Bot Discord de Salons Vocaux Automatiques

Ce bot Discord crée automatiquement de nouveaux salons vocaux lorsque les utilisateurs rejoignent des salons "créateurs" désignés. Lorsque les utilisateurs quittent les salons créés, ils sont automatiquement supprimés.

## Fonctionnalités

- Création de plusieurs créateurs de salons vocaux
- Modèles de noms de salons personnalisables avec variables
- Positionnement relatif des nouveaux salons (avant/après le créateur)
- Nettoyage automatique des salons vides
- Support pour plusieurs serveurs
- Sauvegarde automatique des configurations
- Commandes de gestion faciles à utiliser

## Installation

1. Installez les dépendances requises :
```bash
pip install -r requirements.txt
```

2. Créez un fichier `.env` dans le répertoire racine avec votre token de bot Discord :
```
DISCORD_TOKEN=votre_token_de_bot_ici
```

3. Lancez le bot :
```bash
python src/main.py
```

## Commandes

Toutes les commandes nécessitent les permissions d'administrateur :

### !setupvoice [modele_nom] [position] [nom_createur] [limite_users]
Crée un nouveau créateur de salon vocal avec des paramètres personnalisés
- `modele_nom` : Modèle pour les noms des nouveaux salons (par défaut : "Salon de {user}")
- `position` : Où placer les nouveaux salons ('before' = avant ou 'after' = après, par défaut : 'after')
- `nom_createur` : Le nom du salon créateur (par défaut : "➕ Rejoindre pour Créer")
- `limite_users` : Limite d'utilisateurs (0-99, 0 = illimité)

Exemples :
```
!setupvoice                                    # Configuration basique
!setupvoice "Gaming avec {user}"               # Nom personnalisé
!setupvoice "Salon de {user}" before          # Création avant le créateur
!setupvoice "Salon de {user}" after "🎮 Créer" 5 # Après le créateur avec limite
```

### !removevoice <salon>
Supprime un créateur de salon vocal
- `salon` : Mention ou ID du salon créateur à supprimer

Exemple :
```
!removevoice #rejoindre-pour-creer
```

### !listvoice
Liste tous les créateurs de salons vocaux du serveur avec leurs paramètres

### !help
Affiche l'aide détaillée du bot

## Permissions Requises

Le bot nécessite les permissions suivantes :
- Gérer les salons
- Déplacer des membres
- Voir les salons
- Se connecter
- Envoyer des messages

## Notes

- Seuls les administrateurs du serveur peuvent gérer les créateurs de salons vocaux
- Les modèles de noms de salons prennent en charge la variable {user} qui est remplacée par le nom d'affichage de l'utilisateur
- Les salons créés sont automatiquement supprimés lorsqu'ils sont vides
- Les nouveaux salons sont toujours créés dans la même catégorie que leur salon créateur
- Les nouveaux salons peuvent être positionnés avant ou après leur créateur
- Les configurations sont sauvegardées automatiquement et persistent après le redémarrage du bot
- Vous pouvez avoir plusieurs salons créateurs dans le même serveur