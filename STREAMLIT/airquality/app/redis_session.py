#!/usr/bin/env python3
"""
Redis Session Manager pour Streamlit
Gestion optimisée des sessions JWT avec Redis
"""

import redis
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RedisSessionManager:
    """Gestionnaire de sessions Redis optimisé pour support multi-utilisateurs"""
    
    def __init__(self):
        """Initialise connexion Redis"""
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        # Ne récupérer password que s'il est vraiment défini et non vide
        redis_pass = os.getenv('REDIS_PASSWORD')
        self.redis_password = redis_pass if redis_pass and redis_pass.strip() else None
        
        # Durée de vie des sessions (30 minutes par défaut)
        self.session_ttl = int(os.getenv('SESSION_TTL_MINUTES', 30)) * 60
        
        try:
            # Ne pas envoyer de password si vide/None
            redis_config = {
                'host': self.redis_host,
                'port': self.redis_port,
                'db': self.redis_db,
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5
            }
            
            # Ajouter password seulement s'il est défini
            if self.redis_password:
                redis_config['password'] = self.redis_password
            
            self.redis_client = redis.Redis(**redis_config)
            
            # Test de connexion
            try:
                self.redis_client.ping()
                logger.info(f"✅ Connexion Redis établie: {self.redis_host}:{self.redis_port}")
            except redis.exceptions.AuthenticationError:
                # Si erreur d'auth, réessayer sans mot de passe
                if self.redis_password:
                    logger.warning("⚠️ Erreur Auth Redis. Tentative de connexion SANS mot de passe...")
                    redis_config.pop('password', None)
                    self.redis_client = redis.Redis(**redis_config)
                    self.redis_client.ping()
                    logger.info(f"✅ Connexion Redis établie (sans mot de passe)")
                else:
                    raise
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Erreur connexion Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Redis: {e}")
            raise
    
    def _get_session_key(self, token: str) -> str:
        """Génère clé Redis pour un token"""
        return f"session:{token}"
    
    def _get_user_sessions_key(self, user_id: int) -> str:
        """Génère clé Redis pour les sessions d'un user"""
        return f"user_sessions:{user_id}"
    
    def create_session(self, token: str, user_data: Dict, expires_at: datetime) -> bool:
        """
        Crée une nouvelle session dans Redis
        
        Args:
            token: JWT token
            user_data: Données utilisateur (id, email, role, etc.)
            expires_at: Date d'expiration
            
        Returns:
            bool: True si succès
        """
        try:
            session_key = self._get_session_key(token)
            user_sessions_key = self._get_user_sessions_key(user_data['user_id'])
            
            # Préparation des données session
            session_data = {
                'user_id': user_data['user_id'],
                'email': user_data['email'],
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'role': user_data['role'],
                'expires_at': expires_at.isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_activity': datetime.now(timezone.utc).isoformat()
            }
            
            # Pipeline pour atomicité
            pipe = self.redis_client.pipeline()
            
            # 1. Stocker la session
            pipe.setex(
                session_key,
                self.session_ttl,
                json.dumps(session_data)
            )
            
            # 2. Ajouter le token à la liste des sessions de l'utilisateur
            pipe.sadd(user_sessions_key, token)
            pipe.expire(user_sessions_key, self.session_ttl * 2)  # TTL plus long pour la liste
            
            # Exécuter toutes les opérations
            pipe.execute()
            
            logger.info(f"✅ Session créée: user_id={user_data['user_id']}, token={token[:20]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur création session: {e}")
            return False
    
    def get_session(self, token: str) -> Optional[Dict]:
        """
        Récupère session depuis Redis
        
        Args:
            token: JWT token
            
        Returns:
            Dict avec les données session ou None
        """
        try:
            session_key = self._get_session_key(token)
            session_data = self.redis_client.get(session_key)
            
            if not session_data:
                return None
            
            # Parser JSON
            session = json.loads(session_data)
            
            # Vérifier expiration (avec sécurité)
            try:
                if 'expires_at' not in session:
                    logger.warning(f"⚠️ Session corrompue (pas d'expiration): {token[:20]}...")
                    self.delete_session(token)
                    return None
                    
                expires_at = datetime.fromisoformat(session['expires_at'])
                if datetime.now(timezone.utc) > expires_at:
                    # Session expirée
                    self.delete_session(token)
                    return None
            except Exception as e:
                logger.error(f"❌ Erreur validation date session: {e}")
                self.delete_session(token)
                return None
            
            # Mettre à jour last_activity
            session['last_activity'] = datetime.now(timezone.utc).isoformat()
            self.redis_client.setex(
                session_key,
                self.session_ttl,
                json.dumps(session)
            )
            
            return session
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération session: {e}")
            return None
    
    def delete_session(self, token: str) -> bool:
        """
        Supprime une session
        
        Args:
            token: JWT token
            
        Returns:
            bool: True si succès
        """
        try:
            # Récupérer user_id avant suppression
            session = self.get_session(token)
            
            session_key = self._get_session_key(token)
            self.redis_client.delete(session_key)
            
            # Retirer de la liste des sessions user
            if session:
                user_sessions_key = self._get_user_sessions_key(session['user_id'])
                self.redis_client.srem(user_sessions_key, token)
            
            logger.info(f"✅ Session supprimée: {token[:20]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression session: {e}")
            return False
    
    def get_user_sessions(self, user_id: int) -> list:
        """
        Récupère toutes les sessions actives d'un utilisateur
        
        Args:
            user_id: ID utilisateur
            
        Returns:
            Liste des tokens actifs
        """
        try:
            user_sessions_key = self._get_user_sessions_key(user_id)
            tokens = self.redis_client.smembers(user_sessions_key)
            
            # Vérifier que les sessions existent encore
            valid_tokens = []
            for token in tokens:
                if self.get_session(token):
                    valid_tokens.append(token)
                else:
                    # Nettoyer token invalide
                    self.redis_client.srem(user_sessions_key, token)
            
            return valid_tokens
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération sessions user: {e}")
            return []
    
    def cleanup_expired_sessions(self) -> int:
        """
        Nettoie les sessions expirées
        NOTE: Redis s'en charge automatiquement avec TTL, mais cette méthode
        permet un nettoyage manuel si nécessaire
        
        Returns:
            Nombre de sessions supprimées
        """
        try:
            # Récupérer toutes les clés de session
            session_keys = self.redis_client.keys("session:*")
            
            deleted = 0
            for key in session_keys:
                try:
                    session_data = self.redis_client.get(key)
                    if session_data:
                        session = json.loads(session_data)
                        if 'expires_at' in session:
                            expires_at = datetime.fromisoformat(session['expires_at'])
                            
                            if datetime.now(timezone.utc) > expires_at:
                                token = key.replace("session:", "")
                                self.delete_session(token)
                                deleted += 1
                        else:
                            # Session invalide (pas d'expiration ?) -> Suppression
                            logger.warning(f"⚠️ Session sans expiration trouvée: {key}")
                            token = key.replace("session:", "")
                            self.delete_session(token)
                            deleted += 1
                except Exception as e:
                    logger.error(f"❌ Erreur parsing session {key}: {e}")
            
            if deleted > 0:
                logger.info(f"🧹 {deleted} sessions expirées nettoyées")
            
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage sessions: {e}")
            return 0
    
    def get_active_sessions_count(self) -> int:
        """Retourne le nombre de sessions actives"""
        try:
            return len(self.redis_client.keys("session:*"))
        except Exception as e:
            logger.error(f"❌ Erreur comptage sessions: {e}")
            return 0
    
    def health_check(self) -> bool:
        """Vérifie état de Redis"""
        try:
            return self.redis_client.ping()
        except:
            return False


# Export
__all__ = ['RedisSessionManager']
