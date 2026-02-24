#!/usr/bin/env python3
"""
Rate Limiter avec Redis
Protège contre les attaques brute force
"""

import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter basé sur Redis"""

    def __init__(self):
        import redis
        from config.security_config import get_security_config

        self.config = get_security_config()

        redis_config = {
            "host": self.config.REDIS_HOST,
            "port": self.config.REDIS_PORT,
            "decode_responses": True,
        }
        if self.config.REDIS_PASSWORD:
            redis_config["password"] = self.config.REDIS_PASSWORD

        self.redis = redis.Redis(**redis_config)

    def check_rate_limit(self, identifier: str, limit: int, window: int) -> tuple:
        """
        Vérifie si la limite est atteinte
        Returns: (is_allowed, current_count, reset_seconds)
        """
        key = f"rate_limit:{identifier}"

        try:
            current = self.redis.get(key)

            if current is None:
                self.redis.setex(key, window, "1")
                return True, 1, window

            count = int(current)
            ttl = self.redis.ttl(key)

            if count >= limit:
                logger.warning(f"⚠️ Rate limit atteint pour {identifier}")
                return False, count, ttl

            self.redis.incr(key)
            return True, count + 1, ttl

        except Exception as e:
            logger.error(f"Erreur rate limiter: {e}")
            return True, 0, 0

    def check_login_rate_limit(self, email: str) -> tuple:
        """Vérifie le rate limit pour login (5 tentatives / 15 min)"""
        return self.check_rate_limit(
            f"login:{email.lower()}",
            self.config.RATE_LIMIT_LOGIN_ATTEMPTS,
            self.config.RATE_LIMIT_WINDOW_SECONDS,
        )

    def check_ip_rate_limit(self, ip: str) -> tuple:
        """Vérifie le rate limit par IP (100 requêtes / 15 min)"""
        return self.check_rate_limit(
            f"ip:{ip}", 100, self.config.RATE_LIMIT_WINDOW_SECONDS
        )

    def check_register_rate_limit(self, email: str) -> tuple:
        """Vérifie le rate limit pour inscription"""
        return self.check_rate_limit(
            f"register:{email.lower()}", self.config.RATE_LIMIT_REGISTER_ATTEMPTS, 3600
        )

    def reset_rate_limit(self, identifier: str):
        """Reset le rate limit (après connexion réussie)"""
        key = f"rate_limit:{identifier}"
        self.redis.delete(key)
        logger.info(f"🔄 Rate limit reset pour {identifier}")


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Récupère l'instance du rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        try:
            _rate_limiter = RateLimiter()
        except Exception as e:
            logger.error(f"Erreur création rate limiter: {e}")
            return None
    return _rate_limiter
