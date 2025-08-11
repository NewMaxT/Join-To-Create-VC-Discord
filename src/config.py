import json
import os
from typing import Dict, Optional, Set, List
from datetime import datetime, timedelta

class ServerConfig:
    def __init__(self):
        # Multiple autoroles per guild: guild_id -> List[config]
        self.autorole_config: Dict[int, List[Dict]] = {}
        self.sticky_messages: Dict[int, Dict] = {}  # guild_id -> channel_id -> config
        self.joined_members: Dict[int, Set[int]] = {}  # guild_id -> set of member_ids
        # Per-role assignment date: guild_id -> role_id -> member_id -> datetime
        self.role_assignment_dates: Dict[int, Dict[int, Dict[int, datetime]]] = {}
        self.autorole_log_channels: Dict[int, int] = {}  # guild_id -> log channel id
        # Backward-compat (old schema used this). Keep an empty structure to avoid attribute errors
        self.member_join_dates: Dict[int, Dict[int, datetime]] = {}
        
    def save_config(self):
        """Save configuration to file"""
        data = {
            'autorole': {
                str(guild_id): configs
                for guild_id, configs in self.autorole_config.items()
            },
            'autorole_logs': {
                str(guild_id): channel_id
                for guild_id, channel_id in self.autorole_log_channels.items()
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
            'role_assignment_dates': {
                str(guild_id): {
                    str(role_id): {
                        str(member_id): assign_date.isoformat()
                        for member_id, assign_date in members.items()
                    }
                    for role_id, members in roles.items()
                }
                for guild_id, roles in self.role_assignment_dates.items()
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
            
            # Load autorole config (list); backward-compat for dict
            loaded_autorole = data.get('autorole', {})
            converted: Dict[int, List[Dict]] = {}
            for guild_id_str, cfg in loaded_autorole.items():
                gid = int(guild_id_str)
                if isinstance(cfg, dict):
                    converted[gid] = [cfg]
                elif isinstance(cfg, list):
                    converted[gid] = cfg
                else:
                    converted[gid] = []
            self.autorole_config = converted

            # Load autorole logs channels
            self.autorole_log_channels = {
                int(guild_id): int(channel_id)
                for guild_id, channel_id in data.get('autorole_logs', {}).items()
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
            
            # Load role assignment dates
            self.role_assignment_dates = {
                int(guild_id): {
                    int(role_id): {
                        int(member_id): datetime.fromisoformat(assign_date)
                        for member_id, assign_date in members.items()
                    }
                    for role_id, members in roles.items()
                }
                for guild_id, roles in data.get('role_assignment_dates', {}).items()
            }
            # Backward-compat: keep member_join_dates if present
            mjd = data.get('member_join_dates') or {}
            self.member_join_dates = {
                int(guild_id): {
                    int(member_id): datetime.fromisoformat(join_date)
                    for member_id, join_date in members.items()
                }
                for guild_id, members in mjd.items()
            }
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    def add_autorole(self, guild_id: int, role_id: int, expiry_minutes: Optional[int] = None, check_rejoin: bool = False, trigger: str = 'on_join'):
        """Add or replace an autorole config for a guild"""
        if guild_id not in self.autorole_config:
            self.autorole_config[guild_id] = []
        # Replace existing by role_id
        self.autorole_config[guild_id] = [c for c in self.autorole_config[guild_id] if c.get('role_id') != role_id]
        self.autorole_config[guild_id].append({
            'role_id': role_id,
            'expiry_minutes': expiry_minutes,
            'check_rejoin': check_rejoin,
            'trigger': trigger
        })
        self.save_config()
    
    def remove_autorole(self, guild_id: int, role_id: Optional[int] = None):
        """Remove autorole configurations. If role_id is provided, remove only that one."""
        if guild_id not in self.autorole_config:
            return
        if role_id is None:
            del self.autorole_config[guild_id]
        else:
            self.autorole_config[guild_id] = [c for c in self.autorole_config[guild_id] if c.get('role_id') != role_id]
            if not self.autorole_config[guild_id]:
                del self.autorole_config[guild_id]
        self.save_config()

    def set_autorole_log_channel(self, guild_id: int, channel_id: int):
        """Set the log channel for autorole events"""
        self.autorole_log_channels[guild_id] = channel_id
        self.save_config()

    def get_autorole_log_channel(self, guild_id: int) -> Optional[int]:
        return self.autorole_log_channels.get(guild_id)
    
    def get_autorole(self, guild_id: int) -> Optional[Dict]:
        """Get first autorole configuration for a guild (compat)."""
        cfgs = self.autorole_config.get(guild_id, [])
        return cfgs[0] if cfgs else None

    def get_autoroles(self, guild_id: int) -> List[Dict]:
        """Get all autorole configurations for a guild."""
        return list(self.autorole_config.get(guild_id, []))
    
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
    
    def add_role_assignment(self, guild_id: int, role_id: int, member_id: int):
        """Record the assignment date for a specific role to a member."""
        if guild_id not in self.role_assignment_dates:
            self.role_assignment_dates[guild_id] = {}
        if role_id not in self.role_assignment_dates[guild_id]:
            self.role_assignment_dates[guild_id][role_id] = {}
        self.role_assignment_dates[guild_id][role_id][member_id] = datetime.now()
        self.save_config()

    def remove_role_assignment(self, guild_id: int, role_id: int, member_id: int):
        """Remove a recorded assignment date after role removal."""
        try:
            role_map = self.role_assignment_dates.get(guild_id, {})
            members_map = role_map.get(role_id, {})
            if member_id in members_map:
                del members_map[member_id]
                # cleanup empty maps
                if not members_map:
                    del role_map[role_id]
                if not role_map:
                    del self.role_assignment_dates[guild_id]
                self.save_config()
        except Exception:
            pass
    
    def has_member_joined_before(self, guild_id: int, member_id: int) -> bool:
        """Check if a member has joined the guild before"""
        return member_id in self.joined_members.get(guild_id, set())
    
    def get_expired_roles(self) -> Dict[int, Dict[int, Set[int]]]:
        """Get members whose autoroles should expire per role.
        Returns a dict: {guild_id: {role_id: set(member_ids)}}"""
        result: Dict[int, Dict[int, Set[int]]] = {}
        now = datetime.now()
        for guild_id, cfgs in self.autorole_config.items():
            for cfg in cfgs:
                role_id = cfg.get('role_id')
                expiry = cfg.get('expiry_minutes')
                if not expiry:
                    continue
                cutoff = now - timedelta(minutes=expiry)
                assigned = self.role_assignment_dates.get(guild_id, {}).get(role_id, {})
                expired_members = {mid for mid, at in assigned.items() if at <= cutoff}
                if expired_members:
                    result.setdefault(guild_id, {})[role_id] = expired_members
        return result

    def get_time_left_before_role_expiry(self, guild_id: int, member_id: int) -> Optional[int]:
        """Compatibility: returns time left for the FIRST autorole config, if any."""
        first = self.get_autorole(guild_id)
        if not first or not first.get('expiry_minutes'):
            return None
        role_id = first['role_id']
        assign_date = self.role_assignment_dates.get(guild_id, {}).get(role_id, {}).get(member_id)
        if not assign_date:
            # Fallback to legacy join date if available
            assign_date = self.member_join_dates.get(guild_id, {}).get(member_id)
            if not assign_date:
                return None
        expiry_time = assign_date + timedelta(minutes=first['expiry_minutes'])
        return max(0, int((expiry_time - datetime.now()).total_seconds() / 60))

    def get_time_left_before_role_expiry_for_role(self, guild_id: int, member_id: int, role_id: int) -> Optional[int]:
        """Get minutes left for a specific role assignment."""
        cfgs = [c for c in self.autorole_config.get(guild_id, []) if c.get('role_id') == role_id]
        if not cfgs:
            return None
        expiry = cfgs[0].get('expiry_minutes')
        if not expiry:
            return None
        assign_date = self.role_assignment_dates.get(guild_id, {}).get(role_id, {}).get(member_id)
        if not assign_date:
            return None
        expiry_time = assign_date + timedelta(minutes=expiry)
        return max(0, int((expiry_time - datetime.now()).total_seconds() / 60))

    def get_role_expiry_time(self, guild_id: int, member_id: int) -> Optional[float]:
        """Return expiry time (unix ts) for the FIRST autorole config, for backward usage in prints."""
        first = self.get_autorole(guild_id)
        if not first or not first.get('expiry_minutes'):
            return None
        role_id = first['role_id']
        assign_date = self.role_assignment_dates.get(guild_id, {}).get(role_id, {}).get(member_id)
        if not assign_date:
            assign_date = self.member_join_dates.get(guild_id, {}).get(member_id)
            if not assign_date:
                return None
        expiry_time = assign_date + timedelta(minutes=first['expiry_minutes'])
        return expiry_time.timestamp()