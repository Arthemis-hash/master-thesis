
import os
import redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redis_debug")

# Mocking the load_dotenv behavior by checking os.environ directly first
# In the actual app, load_dotenv() is called, which loads from .env if variables aren't already set.
# We will just check what is currently set.

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))
raw_password = os.getenv('REDIS_PASSWORD')

print(f"DEBUG: RAW REDIS_PASSWORD from env: {repr(raw_password)}")

if raw_password == '':
    print("DEBUG: REDIS_PASSWORD is empty string")
elif raw_password is None:
    print("DEBUG: REDIS_PASSWORD is None")
else:
    print("DEBUG: REDIS_PASSWORD is set to something non-empty")

# Logic from redis_session.py
redis_password = raw_password if raw_password and raw_password.strip() else None
print(f"DEBUG: Processed redis_password: {repr(redis_password)}")

redis_config = {
    'host': redis_host,
    'port': redis_port,
    'db': redis_db,
    'decode_responses': True,
    'socket_connect_timeout': 5,
    'socket_timeout': 5
}

if redis_password:
    print(f"DEBUG: Adding password to config: {redis_password}")
    redis_config['password'] = redis_password
else:
    print("DEBUG: NOT adding password to config")

print(f"DEBUG: Final redis_config keys: {list(redis_config.keys())}")

try:
    print("DEBUG: Attempting connection...")
    client = redis.Redis(**redis_config)
    client.ping()
    print("DEBUG: ✅ Connection successful!")
except Exception as e:
    print(f"DEBUG: ❌ Connection failed: {e}")
