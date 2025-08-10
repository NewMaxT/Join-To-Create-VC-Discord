[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/NewMaxT/Automated-Voice-Channel-Creator)

# Multi-Feature Discord BOT

## Features

- Multiple voice channel creators
- Customizable channel names
- Relative positioning of new channels (before/after the creator)
- Automatic cleanup of empty channels
- Automatic configuration saving (in case of crash or reboot)
- Easy-to-use management commands
- Auto-role system for new members (optional)
- Sticky messages in text channels (optional)
- Multi-language support (English/French)

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory with your Discord bot token:
```
DISCORD_TOKEN=your_bot_token_here
```

3. Run the bot:
```bash
python src/main.py
```

## Commands (Slash)

All commands require administrator permissions.

### Voice Channel Management

#### /setupvoice
Creates a new voice channel creator with custom parameters
- `template_name`: Template for new channel names (default: "Channel of {user}")
- `position`: Where to place new channels ('before' or 'after', default: 'after')
- `creator_name`: Name of the creator channel (default: "➕ Join to Create")
- `user_limit`: User limit (0-99, 0 = unlimited)

#### /removevoice
Removes a voice channel creator
- `channel`: The creator voice channel to remove

#### /listvoice
Lists all voice channel creators on the server with their parameters

### Configuration

#### /config language
Set the bot's language for the server
- `language`: Language code ('en', 'fr')

#### /config autorole
Configure automatic role assignment for new members
- `role`: The role to assign
- `expiry_minutes`: Optional number of minutes after which the role is removed
- `check_rejoin`: If true, role won't be given to rejoining members

#### /config remove_autorole
Disable automatic role assignment

#### /config sticky
Set a sticky message in a channel
- `channel`: The channel to set the sticky message in
- `content`: The content of the sticky message

#### /config remove_sticky
Remove sticky message from a channel

### /help
Display detailed bot help

### Quiz Automation (Google Sheets)

Automate granting an access role to users who pass a quiz tracked in Google Sheets.

Requirements:
- A Google Service Account with access to your spreadsheet (Editor for status logging)
- Environment variables set in `.env`:
  - `DISCORD_TOKEN=xxxxx`
  - Option A: `GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}`
  - Option B: `GOOGLE_SERVICE_ACCOUNT_FILE=C:\\path\\to\\service_account.json`

Commands:
- `/quiz setup` – configure the integration
  - `spreadsheet_id`: The Google Sheet ID
  - `waiting_role`: Discord role users must already have to be eligible (required)
  - `access_role`: Discord role to grant when passed (required)
  - `min_score`: Minimum score to pass (default 17)
  - `log_channel`: Optional channel to log actions
- `/quiz status` – view current configuration and runtime status
- `/quiz test` – test connectivity and show sample results

What it does:
- Polls Google Sheets every 15s for new quiz results (Column B: score, Column C: Discord username)
- If user exists on the server, has the waiting role, and score >= min_score → grants access role
- Writes a status row on the same spreadsheet in the `Quiz_Status` tab with timestamp, guild, user, score, result, details

How to get the Service Account JSON:
- Go to Google Cloud Console → APIs & Services → Enable “Google Sheets API”
- Create Credentials → Service account → finish
- Open the service account → Keys → Add key → Create new key → JSON → Download
- Copy the service account email (ends with `@<project-id>.iam.gserviceaccount.com`)
- Share your Google Sheet with that email as Editor (needed for the `Quiz_Status` tab)

Configure the bot with the JSON (choose one):
- Option A (.env inline JSON):
  ```
  DISCORD_TOKEN=xxxxx
  GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@...iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}
  ```
- Option B (file path in .env):
  ```
  DISCORD_TOKEN=xxxxx
  GOOGLE_SERVICE_ACCOUNT_FILE=C:\\path\\to\\service_account.json
  ```

## Required Permissions

The bot requires the following permissions:
- Manage Channels
- Move Members
- View Channels
- Connect
- Send Messages
- Manage Roles (for autorole feature)

## Discord Developer Portal Setup

### Required Scopes
When creating your bot invite link, you need to select these scopes:
- `bot` - Required to add the bot to servers
- `applications.commands` - Required for slash commands support (WIP)

### Required Bot Permissions
In the Discord Developer Portal, enable these permissions for your bot:
- **General Permissions**
  - View Channels
  - Send Messages
  - Manage Messages (for sticky messages)
  - Read Message History (for sticky messages)
  - Add Reactions (for reaction roles, WIP)
  
- **Voice Channel Permissions**
  - Connect
  - Move Members
  - Manage Channels
  
- **Role Permissions**
  - Manage Roles (for autorole feature)

### Privileged Gateway Intents
Enable these intents in the Discord Developer Portal:
- SERVER MEMBERS INTENT - Required for autorole feature
- MESSAGE CONTENT INTENT - Required for command handling

## Notes

- Only server administrators can manage voice channel creators
- Channel name templates support the {user} variable which is replaced with the user's display name
- Created channels are automatically deleted when empty
- New channels are always created in the same category as their creator
- New channels can be positioned before or after their creator
- Configurations are automatically saved and persist after bot restart
- You can have multiple creator channels in the same server
- Auto-role feature can be configured to:
  - Skip members who have joined before
  - Remove roles after a specified number of minutes
  - Only apply to first-time joins
- Sticky messages will always stay at the bottom of their channel
- For Heroku deployments, use the button above and read their [T.O.S](https://www.heroku.com/policy/heroku-elements-terms/)
