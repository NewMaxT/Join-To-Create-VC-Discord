import asyncio
import nextcord
from nextcord.ext import tasks
from typing import Dict, List, Optional, Set
from google_sheets_manager import GoogleSheetsManager
import json
import os
from datetime import datetime

class QuizAutomation:
    def __init__(self, bot: nextcord.Client):
        """
        Initialise l'automatisation du quiz
        
        Args:
            bot: Instance du bot Discord
        """
        self.bot = bot
        self.sheets_manager = GoogleSheetsManager()
        self.processed_rows: Set[int] = set()
        self.config_file = "quiz_config.json"
        self.config = self.load_config()
        
        # Démarrer la tâche de vérification
        self.check_quiz_results.start()
    
    def load_config(self) -> Dict:
        """Charge la configuration depuis le fichier JSON"""
        default_config = {
            "spreadsheet_id": "",
            "check_interval": 15,  # secondes
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
                        title="🤖 Quiz Automation",
                        description=message,
                        color=0x00ff00,
                        timestamp=datetime.now()
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                print(f"Erreur lors de l'envoi du log: {e}")
        
        # En parallèle, écrire dans la feuille de statut si possible
        try:
            status_title = self.config.get("status_sheet_title", "Quiz_Status")
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
            title = self.config.get("status_sheet_title", "Quiz_Status")
            # S'assurer que la feuille existe
            if not self.sheets_manager.ensure_status_sheet(spreadsheet_id, title):
                return
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_values = [
                timestamp,
                str(guild.id),
                guild.name,
                pseudo_from_sheet,
                str(user_id) if user_id else "",
                (member.name if member else ""),
                str(note),
                result,
                details
            ]
            self.sheets_manager.append_status_row(spreadsheet_id, title, row_values)
        except Exception:
            pass
    
    @tasks.loop(seconds=15)
    async def check_quiz_results(self):
        """Vérifie les résultats du quiz toutes les 15 secondes"""
        if not self.config.get("spreadsheet_id"):
            return
        
        try:
            # Récupérer les résultats du quiz
            results = self.sheets_manager.get_quiz_results(self.config["spreadsheet_id"])
            if not results:
                return
            
            # Traiter chaque serveur
            for guild in self.bot.guilds:
                for result in results:
                    await self.process_quiz_result(result, guild)
                    
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
            "check_interval": self.config.get("check_interval", 15),
            "min_score": self.config.get("min_score", 17),
            "waiting_role_id": self.config.get("waiting_role_id"),
            "access_role_id": self.config.get("access_role_id"),
            "processed_rows": len(self.processed_rows),
            "is_running": self.check_quiz_results.is_running()
        }
