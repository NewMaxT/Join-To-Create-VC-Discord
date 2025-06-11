[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/NewMaxT/Automated-Voice-Channel-Creator)

# Multi-Feature Open Source Discord BOT

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

## Commands

All commands require administrator permissions:

### Voice Channel Management

#### !setupvoice [name_template] [position] [creator_name] [user_limit]
Creates a new voice channel creator with custom parameters
- `name_template`: Template for new channel names (default: "Channel of {user}")
- `position`: Where to place new channels ('before' or 'after', default: 'after')
- `creator_name`: Name of the creator channel (default: "➕ Join to Create")
- `user_limit`: User limit (0-99, 0 = unlimited)

Examples:
```
!setupvoice                                    # Basic setup
!setupvoice "Gaming with {user}"               # Custom name
!setupvoice "Channel of {user}" before         # Create before creator
!setupvoice "Channel of {user}" after "🎮 Create" 5 # After creator with limit
```

#### !removevoice <channel>
Removes a voice channel creator
- `channel`: Mention or ID of the creator channel to remove

Example:
```
!removevoice #join-to-create
```

#### !listvoice
Lists all voice channel creators on the server with their parameters

### Configuration Commands

#### !config language <lang>
Set the bot's language for the server
- `lang`: Language code ('en' for English, 'fr' for French)

#### !config autorole <role> [expiry_minutes] [check_rejoin]
Configure automatic role assignment for new members
- `role`: The role to assign
- `expiry_minutes`: Optional number of minutes after which the role is removed
- `check_rejoin`: If true, role won't be given to rejoining members

#### !config remove_autorole
Disable automatic role assignment

#### !config sticky <channel> <message>
Set a sticky message in a channel
- `channel`: The channel to set the sticky message in
- `message`: The content of the sticky message

#### !config remove_sticky <channel>
Remove sticky message from a channel

### !help
Display detailed bot help

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
