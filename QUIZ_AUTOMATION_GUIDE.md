# Guide d'Automatisation Quiz Discord ↔ Google Sheets

## Vue d'ensemble

Ce système automatise l'attribution de rôles Discord basée sur les résultats d'un quiz stockés dans Google Sheets. Le bot vérifie toutes les 15 secondes les nouvelles entrées et attribue automatiquement le rôle d'accès aux utilisateurs qui remplissent les critères.

## Fonctionnement

1. **Utilisateur avec rôle "Attente - Quiz"** → Accès au quiz externe
2. **Quiz Google Forms** → Résultats dans Google Sheets (Colonne C: pseudo, Colonne B: note)
3. **Bot Discord** → Vérifie Google Sheets toutes les 15 secondes
4. **Conditions remplies** → Attribution automatique du rôle "accès"

### Conditions requises :
- ✅ Pseudo Discord présent sur le serveur
- ✅ Utilisateur a le rôle "Attente - Quiz"
- ✅ Note ≥ 17/20

## Configuration

### 1. Configuration Google Sheets API (sans navigateur)

Nous utilisons un compte de service. Deux options sont possibles :

- Variable d'environnement `GOOGLE_SERVICE_ACCOUNT_JSON` contenant le JSON du compte de service
- Fichier sur disque défini par `GOOGLE_SERVICE_ACCOUNT_FILE`

#### Étapes
1. Allez sur `console.cloud.google.com`
2. Créez/ouvrez un projet et activez l'API Google Sheets
3. Créez un "Service Account" et générez une clé JSON (Credentials → Service Account → Keys → Add key → JSON)
4. Copiez l'email du compte de service (se termine par `@<project-id>.iam.gserviceaccount.com`)
5. Partagez votre Google Sheet avec cet email en "Éditeur" (nécessaire pour écrire dans `Quiz_Status`)
6. Configurez l'une des options ci-dessous :

Option A - .env (recommandé pour déploiement sans fichier):
```
GOOGLE_SERVICE_ACCOUNT_JSON={...votre JSON du compte de service...}
```

Option B - Fichier:
```
GOOGLE_SERVICE_ACCOUNT_FILE=D:\\chemin\\vers\\service_account.json
```

#### Étape 3 : Préparer votre Google Sheets
1. Créez une nouvelle feuille Google Sheets
2. Structure recommandée :
   ```
   | A (Timestamp) | B (Note) | C (Pseudo Discord) | D (Statut) |
   |---------------|----------|-------------------|------------|
   | 2024-01-01... | 18       | Username#1234     |            |
   | 2024-01-01... | 15       | AnotherUser#5678  |            |
   ```
3. Copiez l'ID de la feuille depuis l'URL :
   ```
   https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
   ```

### 2. Configuration Discord

#### Étape 1 : Créer les rôles
Créez les rôles suivants sur votre serveur Discord :
- `Attente - Quiz` : Rôle initial pour accéder au quiz
- `accès` : Rôle final après réussite du quiz
- `Complété - Quiz` : Rôle optionnel pour marquer la complétion

#### Étape 2 : Permissions du bot
Assurez-vous que le bot a les permissions suivantes :
- ✅ Gérer les rôles
- ✅ Voir les membres
- ✅ Envoyer des messages
- ✅ Utiliser les commandes slash

### 3. Configuration du Bot

#### Étape 1 : Installer les dépendances
```bash
pip install -r requirements.txt
```

#### Étape 2 : Première exécution
1. Créez un fichier `.env` à la racine (exemple Windows):
   ```
   DISCORD_TOKEN=xxxxx
   # Option A: JSON inline
   GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
   # Option B: fichier
   # GOOGLE_SERVICE_ACCOUNT_FILE=D:\\chemin\\vers\\service_account.json
   ```
2. Partagez votre Google Sheet avec l'email du compte de service (Éditeur)
3. Lancez le bot : `python src/main.py`
4. Aucune ouverture de navigateur n'est nécessaire

#### Étape 3 : Configuration via Discord
Utilisez la commande slash `/quiz setup` (les rôles sont OBLIGATOIRES et choisis via sélecteur de rôle) :
- **spreadsheet_id** : ID de votre feuille Google Sheets
- **waiting_role** : rôle Discord d'attente (obligatoire)
- **access_role** : rôle Discord d'accès (obligatoire)
- **min_score** : 17 par défaut
- **log_channel** : Canal de logs (optionnel)

## Commandes Disponibles

### `/quiz setup`
Configure l'automatisation du quiz
```
/quiz setup spreadsheet_id:1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms waiting_role:@Attente access_role:@Acces min_score:17 log_channel:#logs
```

### `/quiz status`
Affiche le statut actuel de l'automatisation
```
/quiz status
```

### `/quiz test`
Teste la connexion avec Google Sheets
```
/quiz test
```

## Structure des Fichiers

```
LE-REPERE/
├── src/
│   ├── main.py                 # Bot principal
│   ├── quiz_automation.py      # Logique d'automatisation
│   ├── google_sheets_manager.py # Gestion Google Sheets
│   ├── config.py              # Configuration serveur
│   └── localization.py        # Localisation
├── quiz_config.json          # Configuration quiz (générée automatiquement)
└── requirements.txt          # Dépendances Python
```

## Dépannage

### Erreur "Fichier credentials.json non trouvé"
- Vérifiez que le fichier `credentials.json` est présent à la racine
- Vérifiez que le fichier n'est pas corrompu

### Erreur "Permission denied"
- Vérifiez les permissions du bot Discord
- Vérifiez que le bot peut gérer les rôles

### Erreur "Membre non trouvé"
- Vérifiez que le pseudo dans Google Sheets correspond exactement
- Le bot recherche par nom d'utilisateur, display_name, et recherche partielle

### Erreur "Rôle non trouvé"
- Vérifiez que les rôles existent sur le serveur
- Vérifiez l'orthographe des noms de rôles

### L'automatisation ne fonctionne pas
1. Utilisez `/quiz status` pour vérifier le statut
2. Utilisez `/quiz test` pour tester la connexion
3. Vérifiez les logs dans le canal configuré
4. Vérifiez que le bot a les bonnes permissions

## Personnalisation

### Modifier l'intervalle de vérification
Dans `src/quiz_automation.py`, ligne 200 :
```python
@tasks.loop(seconds=15)  # Changez 15 par votre intervalle
```

### Ajouter des conditions supplémentaires
Dans `src/quiz_automation.py`, méthode `process_quiz_result()` :
```python
# Ajoutez vos conditions ici
if votre_condition:
    # Votre logique
    pass
```

### Modifier les messages de log
Dans `src/quiz_automation.py`, méthode `log_action()` :
```python
embed = nextcord.Embed(
    title="🤖 Quiz Automation",  # Modifiez le titre
    description=message,
    color=0x00ff00,  # Modifiez la couleur
    timestamp=datetime.now()
)
```

## Sécurité

- Ne partagez jamais le fichier `credentials.json`
- Ne partagez jamais le fichier `token.pickle`
- Ajoutez ces fichiers à votre `.gitignore`
- Utilisez des rôles avec des permissions minimales

## Support

Pour toute question ou problème :
1. Vérifiez ce guide de dépannage
2. Consultez les logs du bot
3. Testez avec `/quiz test`
4. Vérifiez les permissions et la configuration
