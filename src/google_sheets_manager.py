import os
import asyncio
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import json

class GoogleSheetsManager:
    def __init__(self, credentials_file: str = None):
        """
        Initialise le gestionnaire Google Sheets
        
        Args:
            credentials_file: Chemin vers le fichier JSON du compte de service (optionnel si variable d'env utilisée)
        """
        self.credentials_file = credentials_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        # Pour l'écriture (status sheet), on étendra dynamiquement la portée
        
    def authenticate(self) -> bool:
        """
        Authentifie l'application avec Google Sheets API
        
        Returns:
            bool: True si l'authentification réussit, False sinon
        """
        try:
            # Option 1: JSON du compte de service via variable d'environnement
            sa_json_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if sa_json_env:
                try:
                    info = json.loads(sa_json_env)
                except json.JSONDecodeError:
                    # Supporte le JSON compacté échappé (par ex. via .env)
                    info = json.loads(sa_json_env.encode('utf-8').decode('unicode_escape'))
                # Étend les scopes si nécessaire (écriture)
                scopes = self._get_effective_scopes()
                creds = ServiceAccountCredentials.from_service_account_info(info, scopes=scopes)
            else:
                # Option 2: fichier JSON sur disque (chemin via paramètre ou variable d'env)
                if not self.credentials_file or not os.path.exists(self.credentials_file):
                    print("Aucun compte de service fourni. Définissez GOOGLE_SERVICE_ACCOUNT_JSON ou GOOGLE_SERVICE_ACCOUNT_FILE.")
                    return False
                scopes = self._get_effective_scopes()
                creds = ServiceAccountCredentials.from_service_account_file(self.credentials_file, scopes=scopes)

            self.service = build('sheets', 'v4', credentials=creds)
            return True
        except Exception as e:
            print(f"Erreur lors de l'authentification Google Sheets: {e}")
            return False

    def _get_effective_scopes(self) -> list:
        """Retourne les scopes nécessaires, lecture + écriture pour la feuille de statut."""
        # Scope lecture de base + écriture pour pouvoir créer/mettre à jour la page statut
        return [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
    
    def read_sheet_data(self, spreadsheet_id: str, range_name: str = "A:C") -> Optional[List[List]]:
        """
        Lit les données d'une feuille Google Sheets
        
        Args:
            spreadsheet_id: ID de la feuille Google Sheets
            range_name: Plage de cellules à lire (par défaut A:C)
            
        Returns:
            List[List]: Données de la feuille ou None en cas d'erreur
        """
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            return values
            
        except HttpError as error:
            print(f"Erreur lors de la lecture de la feuille: {error}")
            return None
        except Exception as e:
            print(f"Erreur inattendue: {e}")
            return None

    def _get_spreadsheet(self, spreadsheet_id: str) -> Optional[Dict]:
        if not self.service:
            if not self.authenticate():
                return None
        try:
            return self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        except Exception as e:
            print(f"Erreur lors de la récupération du spreadsheet: {e}")
            return None

    def ensure_status_sheet(self, spreadsheet_id: str, title: str = "Quiz_Status", headers: Optional[List[str]] = None) -> bool:
        """
        S'assure qu'une feuille (onglet) de statut existe. Si absente, la crée et écrit un header.
        """
        if headers is None:
            headers = [
                "Timestamp", "Guild ID", "Guild Name", "Pseudo (Sheet)",
                "User ID", "User Name", "Note", "Result", "Details"
            ]
        spreadsheet = self._get_spreadsheet(spreadsheet_id)
        if not spreadsheet:
            return False

        sheets = spreadsheet.get('sheets', [])
        for s in sheets:
            props = s.get('properties', {})
            if props.get('title') == title:
                return True

        # Créer la feuille si non présente
        try:
            requests = [{
                'addSheet': {
                    'properties': {
                        'title': title
                    }
                }
            }]
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()

            # Écrire le header
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!A1:I1",
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            return True
        except Exception as e:
            print(f"Erreur lors de la création de la feuille de statut: {e}")
            return False

    def append_status_row(self, spreadsheet_id: str, title: str, row_values: List) -> bool:
        """Ajoute une ligne de statut dans l'onglet spécifié."""
        if not self.service:
            if not self.authenticate():
                return False
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!A:Z",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_values]}
            ).execute()
            return True
        except Exception as e:
            print(f"Erreur lors de l'append de la ligne de statut: {e}")
            return False
    
    def get_quiz_results(self, spreadsheet_id: str) -> List[Dict[str, any]]:
        """
        Récupère les résultats du quiz depuis Google Sheets
        
        Args:
            spreadsheet_id: ID de la feuille Google Sheets
            
        Returns:
            List[Dict]: Liste des résultats avec pseudo et note
        """
        data = self.read_sheet_data(spreadsheet_id)
        if not data:
            return []
        
        results = []
        # Ignore la première ligne (en-têtes) si elle existe
        start_row = 1 if data and len(data) > 0 else 0
        
        for i, row in enumerate(data[start_row:], start=start_row + 1):
            if len(row) >= 3:  # Au moins 3 colonnes (A, B, C)
                try:
                    raw_score = row[1] if len(row) > 1 else ''
                    note = 0.0
                    if raw_score:
                        # Supporte "18", "18.5", "18 / 20", "18/20"
                        # Prend le premier nombre rencontré
                        import re
                        match = re.search(r"(\d+(?:[\.,]\d+)?)", str(raw_score))
                        if match:
                            note_str = match.group(1).replace(',', '.')
                            note = float(note_str)
                    pseudo = row[2].strip() if len(row) > 2 and row[2] else ""  # Colonne C (pseudo)
                    
                    if pseudo:  # Ignore les lignes vides
                        results.append({
                            'row': i,
                            'pseudo': pseudo,
                            'note': note
                        })
                except (ValueError, IndexError) as e:
                    print(f"Erreur lors du parsing de la ligne {i}: {e}")
                    continue
        
        return results
    
    def mark_row_as_processed(self, spreadsheet_id: str, row_number: int, column: str = "D") -> bool:
        """
        Marque une ligne comme traitée (optionnel, pour éviter de retraiter les mêmes données)
        
        Args:
            spreadsheet_id: ID de la feuille Google Sheets
            row_number: Numéro de la ligne à marquer
            column: Colonne où marquer le traitement (par défaut D)
            
        Returns:
            bool: True si succès, False sinon
        """
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            range_name = f"{column}{row_number}"
            values = [["TRAITÉ"]]
            
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
            
        except HttpError as error:
            print(f"Erreur lors du marquage de la ligne: {error}")
            return False
        except Exception as e:
            print(f"Erreur inattendue: {e}")
            return False
