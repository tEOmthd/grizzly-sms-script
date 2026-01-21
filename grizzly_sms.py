import requests
import json
import time
from datetime import datetime
from typing import Optional, Dict

class GrizzlySMS:
    """
    Client Python pour l'API Grizzly SMS
    Documentation: https://grizzlysms.com/api
    """
    
    def __init__(self, api_key: str):
        """
        Initialise le client Grizzly SMS
        
        Args:
            api_key: Votre clé API Grizzly SMS
        """
        self.api_key = api_key
        self.base_url = "https://api.grizzlysms.com/stubs/handler_api.php"
        self.history_file = "sms_history.json"
    
    def get_balance(self) -> Optional[float]:
        """
        Récupère le solde du compte
        
        Returns:
            Solde en euros, ou None en cas d'erreur
        """
        try:
            response = requests.get(self.base_url, params={
                'api_key': self.api_key,
                'action': 'getBalance'
            }, timeout=10)
            
            if 'ACCESS_BALANCE' in response.text:
                balance = float(response.text.split(':')[1])
                print(f"💰 Solde actuel: {balance}€")
                return balance
            else:
                print(f"❌ Erreur lors de la récupération du solde: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None
    
    def get_quick_number(self, country: str = 'fr', service: str = 'other') -> Optional[Dict]:
        """
        Obtient un numéro de téléphone temporaire
        
        Args:
            country: Code pays (fr, us, uk, ru, etc.)
            service: Service cible (other, google, whatsapp, uber, etc.)
        
        Returns:
            Dictionnaire avec les infos du numéro, ou None en cas d'erreur
        """
        print(f"🔄 Demande d'un numéro {country.upper()} pour {service}...")
        
        try:
            response = requests.get(self.base_url, params={
                'api_key': self.api_key,
                'action': 'getNumber',
                'service': service,
                'country': country
            }, timeout=10)
            
            if 'ACCESS_NUMBER' in response.text:
                parts = response.text.split(':')
                data = {
                    'activation_id': parts[1],
                    'phone': parts[2],
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'country': country,
                    'service': service,
                    'status': 'active'
                }
                
                # Sauvegarder dans l'historique
                self._save_to_log(data)
                
                print(f"✅ Numéro: +{data['phone']}")
                print(f"📋 ID d'activation: {data['activation_id']}")
                print(f"⏱️  Valide pendant ~15-20 minutes")
                
                return data
            
            elif 'NO_NUMBERS' in response.text:
                print(f"❌ Pas de numéro disponible pour {country}/{service}")
                return None
            elif 'NO_BALANCE' in response.text:
                print(f"❌ Solde insuffisant. Rechargez votre compte.")
                return None
            elif 'BAD_KEY' in response.text:
                print(f"❌ Clé API invalide")
                return None
            else:
                print(f"❌ Erreur: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return None
    
    def get_sms(self, activation_id: str, max_wait: int = 300) -> Optional[str]:
        """
        Attend et récupère le code SMS
        
        Args:
            activation_id: ID d'activation du numéro
            max_wait: Temps d'attente maximum en secondes (défaut: 5 min)
        
        Returns:
            Code SMS reçu, ou None si timeout/erreur
        """
        print(f"⏳ Attente du SMS (max {max_wait}s)...")
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < max_wait:
            attempts += 1
            
            try:
                response = requests.get(self.base_url, params={
                    'api_key': self.api_key,
                    'action': 'getStatus',
                    'id': activation_id
                }, timeout=10)
                
                if 'STATUS_OK' in response.text:
                    code = response.text.split(':')[1]
                    print(f"📩 Code SMS reçu: {code}")
                    
                    # Marquer comme terminé
                    self._mark_as_finished(activation_id)
                    
                    return code
                
                elif 'STATUS_WAIT_CODE' in response.text:
                    if attempts % 6 == 0:  # Afficher toutes les 30s
                        elapsed = int(time.time() - start_time)
                        print(f"⏳ Toujours en attente... ({elapsed}s écoulées)")
                    time.sleep(5)
                
                elif 'STATUS_CANCEL' in response.text:
                    print(f"❌ Activation annulée")
                    return None
                
                else:
                    print(f"❌ Statut inconnu: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Erreur lors de la vérification: {e}")
                time.sleep(5)
        
        print(f"⏱️  Timeout - Aucun SMS reçu après {max_wait}s")
        print(f"💡 Le crédit sera probablement remboursé automatiquement")
        return None
    
    def cancel_activation(self, activation_id: str) -> bool:
        """
        Annule une activation et récupère le crédit
        
        Args:
            activation_id: ID d'activation à annuler
        
        Returns:
            True si succès, False sinon
        """
        try:
            response = requests.get(self.base_url, params={
                'api_key': self.api_key,
                'action': 'setStatus',
                'status': 8,  # 8 = Cancel
                'id': activation_id
            }, timeout=10)
            
            if 'ACCESS_CANCEL' in response.text:
                print(f"🔄 Activation annulée - crédit remboursé")
                self._mark_as_cancelled(activation_id)
                return True
            else:
                print(f"❌ Impossible d'annuler: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur lors de l'annulation: {e}")
            return False
    
    def _save_to_log(self, data: Dict) -> None:
        """Sauvegarde l'historique dans un fichier JSON"""
        try:
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                history = []
            
            history.append(data)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            print(f"📝 Sauvegardé dans {self.history_file}")
            
        except Exception as e:
            print(f"⚠️  Impossible de sauvegarder l'historique: {e}")
    
    def _mark_as_finished(self, activation_id: str) -> None:
        """Marque une activation comme terminée dans l'historique"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            for entry in history:
                if entry.get('activation_id') == activation_id:
                    entry['status'] = 'completed'
                    entry['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception:
            pass
    
    def _mark_as_cancelled(self, activation_id: str) -> None:
        """Marque une activation comme annulée dans l'historique"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            for entry in history:
                if entry.get('activation_id') == activation_id:
                    entry['status'] = 'cancelled'
                    entry['cancelled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception:
            pass
    
    def get_history(self) -> list:
        """
        Récupère l'historique des numéros
        
        Returns:
            Liste des entrées d'historique
        """
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []


if __name__ == "__main__":
    # Mode simple : obtenir un numéro rapidement
    from config import API_KEY
    
    sms = GrizzlySMS(API_KEY)
    
    # Vérifier le solde
    sms.get_balance()
    
    # Obtenir un numéro
    numero = sms.get_quick_number(country='fr', service='other')
    
    if numero:
        print(f"\n📱 Utilisez ce numéro: +{numero['phone']}")
        print(f"⏱️  Vous avez ~15-20 minutes pour recevoir le SMS")
        
        # Demander si l'utilisateur veut attendre le SMS