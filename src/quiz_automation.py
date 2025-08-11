import asyncio
import nextcord
from nextcord.ext import tasks
from typing import Dict, List, Optional, Set
from google_sheets_manager import GoogleSheetsManager
from config import ServerConfig
import json
import os
from datetime import datetime

class QuizAutomation:
    def __init__(self, bot: nextcord.Client, server_config: ServerConfig):
        """
        Initialise l'automatisation du quiz
        
        Args:
            bot: Instance du bot Discord
        """
        self.bot = bot
        self.server_config = server_config
        self.sheets_manager = GoogleSheetsManager()
        self.processed_rows: Set[int] = set()
        self.config_file = "quiz_config.json"
        self.config = self.load_config()
        
        # États pour limiter les requêtes
        self.last_seen_data_rows: Optional[int] = None
        self.last_processed_row: Optional[int] = None

        # Démarrer la tâche de vérification
        self.check_quiz_results.start()
    
    def load_config(self) -> Dict:
        """Charge la configuration depuis le fichier JSON"""
        default_config = {
            "spreadsheet_id": "",
            "check_interval": 60,  # secondes (modifiable via commande)
            "min_score": 17,
            "max_score": 20,
            # On stocke les IDs des rôles (obligatoires)
            "waiting_role_id": None,
            "access_role_id": None,
            "log_channel_id": None
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Fusionner avec la config par défaut
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"Erreur lors du chargement de la configuration: {e}")
        
        return default_config
    
    def save_config(self):
        """Sauvegarde la configuration dans le fichier JSON"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")
    
    def update_config(self, **kwargs):
        """Met à jour la configuration"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
        self.save_config()
    
    async def find_member_by_username(self, guild: nextcord.Guild, username: str) -> Optional[nextcord.Member]:
        """
        Trouve un membre par son nom d'utilisateur
        
        Args:
            guild: Serveur Discord
            username: Nom d'utilisateur à rechercher
            
        Returns:
            nextcord.Member ou None si non trouvé
        """
        # Recherche exacte
        member = guild.get_member_named(username)
        if member:
            return member
        
        # Recherche par display_name
        for member in guild.members:
            if member.display_name.lower() == username.lower():
                return member
        
        # Recherche partielle dans le nom d'utilisateur
        for member in guild.members:
            if username.lower() in member.name.lower():
                return member
        
        return None
    
    async def has_role(self, member: nextcord.Member, role_id: int) -> bool:
        """
        Vérifie si un membre a un rôle spécifique
        
        Args:
            member: Membre Discord
            role_name: Nom du rôle à vérifier
            
        Returns:
            bool: True si le membre a le rôle
        """
        return any(role.id == role_id for role in member.roles)
    
    async def add_role(self, member: nextcord.Member, role_id: int) -> bool:
        """
        Ajoute un rôle à un membre
        
        Args:
            member: Membre Discord
            role_name: Nom du rôle à ajouter
            
        Returns:
            bool: True si le rôle a été ajouté avec succès
        """
        try:
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role)
                return True
            else:
                print(f"Rôle ID '{role_id}' non trouvé sur le serveur")
                return False
        except Exception as e:
            print(f"Erreur lors de l'ajout du rôle {role_id} à {member.name}: {e}")
            return False
    
    async def remove_role(self, member: nextcord.Member, role_id: int) -> bool:
        """
        Retire un rôle d'un membre
        
        Args:
            member: Membre Discord
            role_name: Nom du rôle à retirer
            
        Returns:
            bool: True si le rôle a été retiré avec succès
        """
        try:
            role = member.guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role)
                return True
            return False
        except Exception as e:
            print(f"Erreur lors du retrait du rôle {role_id} de {member.name}: {e}")
            return False
    
    async def log_action(self, message: str):
        """Enregistre une action dans le canal de logs"""
        if self.config.get("log_channel_id"):
            try:
                channel = self.bot.get_channel(self.config["log_channel_id"])
                if channel:
                    embed = nextcord.Embed(
                        title="🤖 Quizz Le Repère",
                        description=message,
                        color=0x00ff00,
                        timestamp=datetime.now()
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                print(f"Erreur lors de l'envoi du log: {e}")
        
        # En parallèle, écrire dans la feuille de statut si possible
        try:
            status_title = self.config.get("status_sheet_title", "Statut - Roles")
            spreadsheet_id = self.config.get("spreadsheet_id")
            if spreadsheet_id and self.sheets_manager.ensure_status_sheet(spreadsheet_id, status_title):
                # message est déjà formatté, mais on préfère un append structuré ailleurs
                pass
        except Exception:
            pass
    
    async def process_quiz_result(self, result: Dict, guild: nextcord.Guild) -> bool:
        """
        Traite un résultat de quiz
        
        Args:
            result: Résultat du quiz (pseudo, note, row)
            guild: Serveur Discord
            
        Returns:
            bool: True si le traitement a réussi
        """
        pseudo = result['pseudo']
        note = result['note']
        row = result['row']
        
        # Vérifier si la ligne a déjà été traitée
        if row in self.processed_rows:
            return True
        
        # Trouver le membre
        member = await self.find_member_by_username(guild, pseudo)
        if not member:
            await self.log_action(f"❌ Membre non trouvé: {pseudo}")
            # Tracer dans la feuille de statut
            self._append_status(guild, pseudo, None, None, result['note'], "ERROR", "Member not found")
            return False
        
        # Vérifier les conditions
        if not self.config.get("waiting_role_id") or not self.config.get("access_role_id"):
            await self.log_action("❌ Configuration incomplète: roles non définis")
            self._append_status(guild, pseudo, member, member.id if member else None, note, "ERROR", "Roles not configured")
            return False

        has_waiting_role = await self.has_role(member, self.config["waiting_role_id"])
        score_ok = note >= self.config["min_score"]
        
        if not has_waiting_role:
            await self.log_action(f"❌ {member.name} n'a pas le rôle requis (ID: {self.config['waiting_role_id']})")
            self._append_status(guild, pseudo, member, member.id, note, "ERROR", "Missing waiting role")
            return False
        
        if not score_ok:
            await self.log_action(f"❌ {member.name} a une note insuffisante: {note}/{self.config['max_score']}")
            self._append_status(guild, pseudo, member, member.id, note, "ERROR", "Score too low")
            return False
        
        # Toutes les conditions sont remplies, donner le rôle d'accès
        success = await self.add_role(member, self.config["access_role_id"])
        if success:
            await self.log_action(f"✅ {member.name} a reçu le rôle d'accès (ID: {self.config['access_role_id']}) (Note: {note}/{self.config['max_score']})")
            self._append_status(guild, pseudo, member, member.id, note, "SUCCESS", "Role granted")
            self.processed_rows.add(row)
            # Si des auto-rôles sont configurés avec déclencheur on_quiz_access, les attribuer maintenant
            try:
                cfgs = self.server_config.get_autoroles(guild.id) if hasattr(self.server_config, 'get_autoroles') else ([])
                if not cfgs:
                    # fallback ancien schéma
                    single = self.server_config.get_autorole(guild.id)
                    cfgs = [single] if single else []
                for cfg in cfgs:
                    if not cfg or cfg.get('trigger') != 'on_quiz_access':
                        continue
                    role_id = cfg.get('role_id')
                    autorole = guild.get_role(role_id) if role_id else None
                    if not autorole or autorole in member.roles:
                        continue
                    try:
                        await member.add_roles(autorole, reason="Autorole (on_quiz_access)")
                        if hasattr(self.server_config, 'add_role_assignment'):
                            self.server_config.add_role_assignment(guild.id, autorole.id, member.id)
                        log_channel_id = self.server_config.get_autorole_log_channel(guild.id)
                        if log_channel_id:
                            ch = guild.get_channel(log_channel_id)
                            if ch:
                                await ch.send(f"✅ Rôle {autorole.mention} attribué à {member.mention} (on_quiz_access)")
                    except Exception as e:
                        log_channel_id = self.server_config.get_autorole_log_channel(guild.id)
                        if log_channel_id:
                            ch = guild.get_channel(log_channel_id)
                            if ch:
                                await ch.send(f"❌ Impossible d'attribuer {autorole.mention} à {member.mention} (on_quiz_access): {e}")
            except Exception:
                pass
            return True
        else:
            await self.log_action(f"❌ Erreur lors de l'attribution du rôle à {member.name}")
            self._append_status(guild, pseudo, member, member.id, note, "ERROR", "Failed to add role")
            return False

    def _append_status(self, guild: nextcord.Guild, pseudo_from_sheet: str, member: Optional[nextcord.Member], user_id: Optional[int], note: float, result: str, details: str):
        try:
            spreadsheet_id = self.config.get("spreadsheet_id")
            if not spreadsheet_id:
                return
            title = self.config.get("status_sheet_title", "Statut - Roles")
            # S'assurer que la feuille existe
            if not self.sheets_manager.ensure_status_sheet(spreadsheet_id, title):
                return
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Résultat avec emoji
            result_upper = (result or "").upper()
            if result_upper == "SUCCESS":
                result_cell = "✅"
            elif result_upper == "ERROR":
                result_cell = "❌"
            else:
                result_cell = str(result)
            # Traduction des détails
            translations = {
                "Missing waiting role": "Rôle d'attente manquant",
                "Score too low": "Score insuffisant",
                "Role granted": "Rôle attribué",
                "Roles not configured": "Rôles non configurés",
                "Member not found": "Membre introuvable",
                "Failed to add role": "Échec lors de l'attribution du rôle",
                "Empty or invalid row": "Ligne vide ou invalide",
            }
            details_cell = translations.get(details, details)
            row_values = [
                timestamp,
                str(guild.id),
                guild.name,
                pseudo_from_sheet,
                str(user_id) if user_id else "",
                (member.name if member else ""),
                str(note),
                result_cell,
                details_cell
            ]
            self.sheets_manager.append_status_row(spreadsheet_id, title, row_values)
        except Exception:
            pass
    
    @tasks.loop(seconds=60)
    async def check_quiz_results(self):
        """Vérifie les résultats du quiz toutes les 15 secondes"""
        if not self.config.get("spreadsheet_id"):
            return
        
        try:
            spreadsheet_id = self.config["spreadsheet_id"]
            status_title = self.config.get("status_sheet_title", "Statut - Roles")
            # ensure_status_sheet est désormais appelé une fois au démarrage (dans on_ready)

            # Éviter de rechecker si aucune nouvelle entrée
            if self.last_seen_data_rows is None:
                self.last_seen_data_rows = self.sheets_manager.get_data_row_count(spreadsheet_id) or 1
            if self.last_processed_row is None:
                # Basé sur le statut existant
                status_rows = self.sheets_manager.get_status_row_count(spreadsheet_id, status_title) or 0
                self.last_processed_row = max(1, status_rows)

            current_data_rows = self.sheets_manager.get_data_row_count(spreadsheet_id) or self.last_seen_data_rows
            if current_data_rows <= (self.last_processed_row or 1):
                self.last_seen_data_rows = current_data_rows
                return
            self.last_seen_data_rows = current_data_rows

            next_row_to_read = (self.last_processed_row or 1) + 1

            # Si plus de 5 nouvelles lignes à traiter, accélérer à 5s
            data_rows = current_data_rows
            new_rows = max(0, data_rows - (self.last_processed_row or 1))
            if new_rows > 5 and self.config.get("check_interval", 60) != 5:
                try:
                    self.check_quiz_results.change_interval(seconds=5)
                    self.config["check_interval"] = 5
                except Exception:
                    pass
            elif new_rows <= 5 and self.config.get("check_interval", 60) != 60:
                try:
                    self.check_quiz_results.change_interval(seconds=self.config.get("check_interval_default", 60))
                    self.config["check_interval"] = self.config.get("check_interval_default", 60)
                except Exception:
                    pass

            # Lire en batch un petit bloc de lignes (jusqu'à 5) pour réduire les requêtes
            end_row_to_read = min(next_row_to_read + 4, data_rows)
            rows = self.sheets_manager.read_rows_range(spreadsheet_id, next_row_to_read, end_row_to_read, cols="A:C") or []
            import re
            processed_any = False
            for offset, row in enumerate(rows):
                current_row_idx = next_row_to_read + offset
                try:
                    raw_score = row[1] if len(row) > 1 else ''
                    match = re.search(r"(\d+(?:[\.,]\d+)?)", str(raw_score))
                    note = float(match.group(1).replace(',', '.')) if match else 0.0
                    pseudo = row[2].strip() if len(row) > 2 and row[2] else ""
                except Exception:
                    note = 0.0
                    pseudo = ""

                if not pseudo:
                    for guild in self.bot.guilds:
                        self._append_status(guild, pseudo, None, None, note, "ERROR", "Empty or invalid row")
                    continue

                result = {"row": current_row_idx, "pseudo": pseudo, "note": note}
                for guild in self.bot.guilds:
                    await self.process_quiz_result(result, guild)
                processed_any = True
                self.last_processed_row = max(self.last_processed_row or 1, current_row_idx)

            if not processed_any:
                return
                    
        except Exception as e:
            print(f"Erreur lors de la vérification des résultats du quiz: {e}")
            await self.log_action(f"❌ Erreur: {str(e)}")
    
    @check_quiz_results.before_loop
    async def before_check_quiz_results(self):
        """Attendre que le bot soit prêt avant de démarrer la vérification"""
        await self.bot.wait_until_ready()
    
    async def setup_quiz_automation(
        self,
        spreadsheet_id: str,
        waiting_role: nextcord.Role,
        access_role: nextcord.Role,
        min_score: int = 17,
        log_channel_id: Optional[int] = None
    ):
        """
        Configure l'automatisation du quiz
        
        Args:
            spreadsheet_id: ID de la feuille Google Sheets
            waiting_role: Nom du rôle d'attente
            completed_role: Nom du rôle complété
            access_role: Nom du rôle d'accès
            min_score: Note minimale requise
            log_channel_id: ID du canal de logs (optionnel)
        """
        self.update_config(
            spreadsheet_id=spreadsheet_id,
            waiting_role_id=waiting_role.id,
            access_role_id=access_role.id,
            min_score=min_score,
            log_channel_id=log_channel_id
        )
        
        await self.log_action("🔧 Configuration de l'automatisation du quiz mise à jour")
    
    async def get_status(self) -> Dict:
        """Retourne le statut de l'automatisation"""
        return {
            "spreadsheet_id": self.config.get("spreadsheet_id", "Non configuré"),
            "check_interval": self.config.get("check_interval", 60),
            "min_score": self.config.get("min_score", 17),
            "waiting_role_id": self.config.get("waiting_role_id"),
            "access_role_id": self.config.get("access_role_id"),
            "processed_rows": len(self.processed_rows),
            "is_running": self.check_quiz_results.is_running()
        }
