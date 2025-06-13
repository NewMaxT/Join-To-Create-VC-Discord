import json
import os
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

class ServerConfig:
    def __init__(self):
        self.autorole_config: Dict[int, Dict] = {}  # guild_id -> config
        self.sticky_messages: Dict[int, Dict] = {}  # guild_id -> channel_id -> config
        self.joined_members: Dict[int, Set[int]] = {}  # guild_id -> set of member_ids
        self.member_join_dates: Dict[int, Dict[int, datetime]] = {}  # guild_id -> member_id -> join_date
        
    def save_config(self):
        """Save configuration to file"""
        data = {
            'autorole': {
                str(guild_id): config
                for guild_id, config in self.autorole_config.items()
            },
            'sticky_messages': {
                str(guild_id): {
                    str(channel_id): config
                    for channel_id, config in channels.items()
                }
                for guild_id, channels in self.sticky_messages.items()
            },
            'joined_members': {
                str(guild_id): list(members)
                for guild_id, members in self.joined_members.items()
            },
            'member_join_dates': {
                str(guild_id): {
                    str(member_id): join_date.isoformat()
                    for member_id, join_date in members.items()
                }
                for guild_id, members in self.member_join_dates.items()
            }
        }
        
        with open('server_config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def load_config(self):
        """Load configuration from file"""
        if not os.path.exists('server_config.json'):
            return
        
        try:
            with open('server_config.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load autorole config
            self.autorole_config = {
                int(guild_id): config
                for guild_id, config in data.get('autorole', {}).items()
            }
            
            # Load sticky messages
            self.sticky_messages = {
                int(guild_id): {
                    int(channel_id): config
                    for channel_id, config in channels.items()
                }
                for guild_id, channels in data.get('sticky_messages', {}).items()
            }
            
            # Load joined members
            self.joined_members = {
                int(guild_id): set(map(int, members))
                for guild_id, members in data.get('joined_members', {}).items()
            }
            
            # Load member join dates
            self.member_join_dates = {
                int(guild_id): {
                    int(member_id): datetime.fromisoformat(join_date)
                    for member_id, join_date in members.items()
                }
                for guild_id, members in data.get('member_join_dates', {}).items()
            }
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    def set_autorole(self, guild_id: int, role_id: int, expiry_minutes: Optional[int] = None, check_rejoin: bool = False):
        """Configure autorole for a guild"""
        self.autorole_config[guild_id] = {
            'role_id': role_id,
            'expiry_minutes': expiry_minutes,
            'check_rejoin': check_rejoin
        }
        self.save_config()
    
    def remove_autorole(self, guild_id: int):
        """Remove autorole configuration for a guild"""
        if guild_id in self.autorole_config:
            del self.autorole_config[guild_id]
            self.save_config()
    
    def get_autorole(self, guild_id: int) -> Optional[Dict]:
        """Get autorole configuration for a guild"""
        return self.autorole_config.get(guild_id)
    
    def set_sticky_message(self, guild_id: int, channel_id: int, content: str, last_message_id: Optional[int] = None):
        """Set sticky message for a channel"""
        if guild_id not in self.sticky_messages:
            self.sticky_messages[guild_id] = {}
        
        self.sticky_messages[guild_id][channel_id] = {
            'content': content,
            'last_message_id': last_message_id
        }
        self.save_config()
    
    def remove_sticky_message(self, guild_id: int, channel_id: int):
        """Remove sticky message from a channel"""
        if guild_id in self.sticky_messages and channel_id in self.sticky_messages[guild_id]:
            del self.sticky_messages[guild_id][channel_id]
            if not self.sticky_messages[guild_id]:
                del self.sticky_messages[guild_id]
            self.save_config()
    
    def get_sticky_message(self, guild_id: int, channel_id: int) -> Optional[Dict]:
        """Get sticky message configuration for a channel"""
        return self.sticky_messages.get(guild_id, {}).get(channel_id)
    
    def update_sticky_message_id(self, guild_id: int, channel_id: int, message_id: int):
        """Update the last message ID for a sticky message"""
        if guild_id in self.sticky_messages and channel_id in self.sticky_messages[guild_id]:
            self.sticky_messages[guild_id][channel_id]['last_message_id'] = message_id
            self.save_config()
    
    def add_joined_member(self, guild_id: int, member_id: int):
        """Record that a member has joined the guild before"""
        if guild_id not in self.joined_members:
            self.joined_members[guild_id] = set()
        self.joined_members[guild_id].add(member_id)
        
        if guild_id not in self.member_join_dates:
            self.member_join_dates[guild_id] = {}
        self.member_join_dates[guild_id][member_id] = datetime.now()
        
        self.save_config()
    
    def has_member_joined_before(self, guild_id: int, member_id: int) -> bool:
        """Check if a member has joined the guild before"""
        return member_id in self.joined_members.get(guild_id, set())
    
    def get_expired_roles(self) -> Dict[int, Set[int]]:
        """Get members whose roles should expire"""
        expired_roles = {}
        now = datetime.now()
        
        for guild_id, config in self.autorole_config.items():
            if not config.get('expiry_minutes'):
                continue
                
            expiry_date = now - timedelta(minutes=config['expiry_minutes'])
            expired_members = {
                member_id
                for member_id, join_date in self.member_join_dates.get(guild_id, {}).items()
                if join_date <= expiry_date
            }
            
            if expired_members:
                expired_roles[guild_id] = expired_members
        
        return expired_roles

    def get_time_left_before_role_expiry(self, guild_id: int, member_id: int) -> Optional[int]:
        """Get the number of minutes left before a member's role expires
        
        Args:
            guild_id: The ID of the guild
            member_id: The ID of the member
            
        Returns:
            Optional[int]: The number of minutes left before expiry, or None if no expiry set
                          Returns 0 if the role has already expired
        """
        config = self.get_autorole(guild_id)
        if not config or not config.get('expiry_minutes'):
            return None
            
        join_date = self.member_join_dates.get(guild_id, {}).get(member_id)
        if not join_date:
            return None
            
        expiry_time = join_date + timedelta(minutes=config['expiry_minutes'])
        time_left = expiry_time - datetime.now()
        minutes_left = int(time_left.total_seconds() / 60)
        
        return max(0, minutes_left)  # Don't return negative minutes

    def get_role_expiry_time(self, guild_id: int, member_id: int) -> Optional[float]:
        """Get the expiry time for a member's role
        
        Args:
            guild_id: The ID of the guild
            member_id: The ID of the member
            
        Returns:
            Optional[float]: The expiry time as a Unix timestamp, or None if no expiry
        """
        config = self.get_autorole(guild_id)
        if not config or not config.get('expiry_minutes'):
            return None
            
        join_date = self.member_join_dates.get(guild_id, {}).get(member_id)
        if not join_date:
            return None
            
        expiry_time = join_date + timedelta(minutes=config['expiry_minutes'])
        return expiry_time.timestamp() 