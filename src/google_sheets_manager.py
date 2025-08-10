import os
import asyncio
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import json
import time

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
        # Limiteur de débit: max 1 requête/seconde (HARD limit)
        self.min_interval_seconds = float(os.getenv('GOOGLE_API_MIN_INTERVAL', '1.0'))
        self._last_request_ts: float = 0.0
        # Caches basiques pour réduire les appels
        self._status_sheet_checked: dict[str, bool] = {}
        self._sheet_title_to_id: dict[tuple[str, str], int] = {}

    def _throttle(self):
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()
        
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
            self._throttle()
            return self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        except Exception as e:
            print(f"Erreur lors de la récupération du spreadsheet: {e}")
            return None

    def _get_sheet_id_by_title(self, spreadsheet_id: str, title: str) -> Optional[int]:
        cache_key = (spreadsheet_id, title)
        if cache_key in self._sheet_title_to_id:
            return self._sheet_title_to_id[cache_key]
        data = self._get_spreadsheet(spreadsheet_id)
        if not data:
            return None
        for s in data.get('sheets', []):
            props = s.get('properties', {})
            if props.get('title') == title:
                sid = props.get('sheetId')
                if sid is not None:
                    self._sheet_title_to_id[cache_key] = sid
                return sid
        return None

    def ensure_status_sheet(self, spreadsheet_id: str, title: str = "Statut - Roles", headers: Optional[List[str]] = None) -> bool:
        """
        S'assure qu'une feuille (onglet) de statut existe. Si absente, la crée et écrit un header.
        """
        if self._status_sheet_checked.get(spreadsheet_id):
            return True
        if headers is None:
            headers = [
                "Horodatage", "ID Serveur", "Nom Serveur", "Pseudo (Feuille)",
                "ID Utilisateur", "Nom Utilisateur", "Note", "Résultat", "Détails"
            ]
        spreadsheet = self._get_spreadsheet(spreadsheet_id)
        if not spreadsheet:
            return False

        sheets = spreadsheet.get('sheets', [])
        for s in sheets:
            props = s.get('properties', {})
            if props.get('title') == title:
                # La page existe déjà: ne pas renvoyer addTable, juste marquer comme vérifiée
                self._status_sheet_checked[spreadsheet_id] = True
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
            self._throttle()
            try:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': requests}
                ).execute()
            except Exception as e:
                # Si l'ajout de table échoue (ex: bande alternée déjà présente), appliquer un fallback idempotent
                msg = str(e)
                if 'addTable' in msg or 'alternating background colors' in msg or 'Invalid requests[0].addTable' in msg:
                    fallback_requests = [
                        {
                            'updateSheetProperties': {
                                'properties': {
                                    'sheetId': sheet_id,
                                    'gridProperties': {
                                        'frozenRowCount': 1
                                    }
                                },
                                'fields': 'gridProperties.frozenRowCount'
                            }
                        },
                        {
                            'autoResizeDimensions': {
                                'dimensions': {
                                    'sheetId': sheet_id,
                                    'dimension': 'COLUMNS',
                                    'startIndex': 0,
                                    'endIndex': 9
                                }
                            }
                        }
                    ]
                    self._throttle()
                    try:
                        self.service.spreadsheets().batchUpdate(
                            spreadsheetId=spreadsheet_id,
                            body={'requests': fallback_requests}
                        ).execute()
                    except Exception:
                        pass
                else:
                    raise

            # Écrire le header
            self._throttle()
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!A1:I1",
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            # Mise en forme tableau (uniquement à la création)
            try:
                self.setup_status_table(spreadsheet_id, title, first_time=True, header_count=len(headers))
            except Exception:
                pass
            self._status_sheet_checked[spreadsheet_id] = True
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
            self._throttle()
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

    def setup_status_table(self, spreadsheet_id: str, title: str = "Statut - Roles", first_time: bool = False, header_count: int = 9) -> bool:
        """Crée un Tableau (addTable) uniquement à la création et applique quelques réglages utiles.
        first_time=True: la page vient d'être créée; on peut appeler addTable en toute sécurité.
        header_count: nombre de colonnes dans l'en-tête (par défaut 9 -> A..I)."""
        if not self.service:
            if not self.authenticate():
                return False
        try:
            sheet_id = self._get_sheet_id_by_title(spreadsheet_id, title)
            if sheet_id is None:
                return False

            requests = []
            if first_time:
                requests.append({
                    'addTable': {
                        'table': {
                            'name': 'Statut_Roles_Table',
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'startColumnIndex': 0,
                                'endRowIndex': 1000000,
                                'endColumnIndex': header_count
                            }
                        }
                    }
                })
            # Geler l'en-tête
            requests.append({
                'updateSheetProperties': {
                    'properties': {
                        'sheetId': sheet_id,
                        'gridProperties': {
                            'frozenRowCount': 1
                        }
                    },
                    'fields': 'gridProperties.frozenRowCount'
                }
            })
            # Auto resize fiable: set dimension size then auto-resize
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': header_count
                    },
                    'properties': {
                        'pixelSize': 150
                    },
                    'fields': 'pixelSize'
                }
            })
            requests.append({
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': header_count
                    }
                }
            })

            self._throttle()
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()

            return True
        except Exception as e:
            print(f"Erreur lors de la mise en forme du tableau: {e}")
            return False

    def get_status_row_count(self, spreadsheet_id: str, title: str = "Statut - Roles") -> Optional[int]:
        """Retourne le nombre de lignes remplies dans l'onglet statut (colonne A)."""
        if not self.service:
            if not self.authenticate():
                return None
        try:
            self._throttle()
            resp = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!A:A"
            ).execute()
            values = resp.get('values', [])
            return len(values) if values else 0
        except Exception as e:
            print(f"Erreur lors du comptage des lignes statut: {e}")
            return None

    def get_data_row_count(self, spreadsheet_id: str) -> Optional[int]:
        """Retourne le nombre de lignes remplies dans la 1re feuille (colonne A)."""
        if not self.service:
            if not self.authenticate():
                return None
        try:
            self._throttle()
            resp = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="A:A"
            ).execute()
            values = resp.get('values', [])
            return len(values) if values else 0
        except Exception as e:
            print(f"Erreur lors du comptage des lignes de données: {e}")
            return None

    def read_single_row(self, spreadsheet_id: str, row_index: int, cols: str = "A:C") -> Optional[List[str]]:
        """Lit une seule ligne (row_index) sur la 1re feuille, colonnes spécifiées (ex: A:C)."""
        if not self.service:
            if not self.authenticate():
                return None
        try:
            # Sans nom d'onglet -> 1re feuille
            rng = f"{cols.split(':')[0]}{row_index}:{cols.split(':')[1]}{row_index}"
            self._throttle()
            resp = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=rng
            ).execute()
            values = resp.get('values', [])
            return values[0] if values else []
        except Exception as e:
            print(f"Erreur lors de la lecture de la ligne {row_index}: {e}")
            return None

    def read_rows_range(self, spreadsheet_id: str, start_row: int, end_row: int, cols: str = "A:C") -> Optional[List[List[str]]]:
        """Lit un bloc de lignes [start_row, end_row] sur la 1re feuille (colonnes cols)."""
        if not self.service:
            if not self.authenticate():
                return None
        try:
            rng = f"{cols.split(':')[0]}{start_row}:{cols.split(':')[1]}{end_row}"
            self._throttle()
            resp = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=rng
            ).execute()
            return resp.get('values', [])
        except Exception as e:
            print(f"Erreur lors de la lecture des lignes {start_row}-{end_row}: {e}")
            return None
    
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
