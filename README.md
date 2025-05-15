# Bot Discord de Salons Vocaux Automatiques

Ce bot Discord crée automatiquement de nouveaux salons vocaux lorsque les utilisateurs rejoignent des salons "créateurs" désignés. Lorsque les utilisateurs quittent les salons créés, ils sont automatiquement supprimés.

## Fonctionnalités

- Création de plusieurs créateurs de salons vocaux dans différentes catégories
- Modèles de noms de salons personnalisables avec variables
- Options flexibles de placement des salons (au-dessus/en-dessous du créateur ou dans une catégorie spécifique)
- Nettoyage automatique des salons vides
- Support pour plusieurs serveurs
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

### !setupvoice [modele_nom] [categorie] [position]
Crée un nouveau créateur de salon vocal avec des paramètres personnalisés
- `modele_nom` : Modèle pour les noms des nouveaux salons (par défaut : "Salon de {user}")
- `categorie` : Catégorie optionnelle pour placer les nouveaux salons
- `position` : Où placer les nouveaux salons ('above' = au-dessus, 'below' = en-dessous, ou 'category' = dans la catégorie, par défaut : 'below')

Exemples :
```
!setupvoice                                    # Configuration basique avec valeurs par défaut
!setupvoice "Gaming avec {user}"               # Modèle de nom personnalisé
!setupvoice "Salon de {user}" #Gaming above    # Catégorie et position personnalisées
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
- Vous pouvez avoir plusieurs salons créateurs avec des paramètres différents dans le même serveur