import asyncio
import json
from kademlia.network import Server
from typing import Optional, Dict, Any
import pickle
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DHTManager:
    _instance = None
    _server = None
    _initialized = False
    _bootstrap_nodes = [
        ("127.0.0.1", 8468),
        ("127.0.0.1", 9000)  # Backup bootstrap node
    ]   
    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
            await cls._instance.initialize()
        return cls._instance
    async def initialize(self):
        if not self._initialized:
            try:
                self._server = Server()
                await self._server.listen(8468)
                
                # Try multiple bootstrap nodes
                bootstrap_successful = False
                for node in self._bootstrap_nodes:
                    try:
                        await self._server.bootstrap([node])
                        bootstrap_successful = True
                        logger.info(f"Successfully bootstrapped with node {node}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to bootstrap with {node}: {e}")
                
                if not bootstrap_successful:
                    # If no bootstrap nodes available, this becomes the first node
                    logger.info("No bootstrap nodes available. Starting as initial node.")
                
                self._initialized = True
                logger.info("DHT Manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize DHT Manager: {e}")
                raise
    
    @asynccontextmanager
    async def connection(self):
        """Context manager to ensure proper connection handling"""
        try:
            if not self._initialized:
                await self.initialize()
            yield self
        except Exception as e:
            logger.error(f"DHT connection error: {e}")
            raise
    
    async def set(self, key: str, value: Any) -> bool:
        """Store a key-value pair in the DHT with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                serialized_value = pickle.dumps(value)
                await self._server.set(key.encode(), serialized_value)
                logger.info(f"Successfully stored key {key} in DHT")
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final attempt to store value in DHT failed: {e}")
                    return False
                logger.warning(f"Attempt {attempt + 1} to store value failed: {e}")
                await asyncio.sleep(1)  # Wait before retry
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the DHT with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await self._server.get(key.encode())
                if result:
                    return pickle.loads(result)
                logger.info(f"No value found for key {key}")
                return None
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final attempt to retrieve value failed: {e}")
                    return None
                logger.warning(f"Attempt {attempt + 1} to retrieve value failed: {e}")
                await asyncio.sleep(1)
    
    async def store_room(self, code: str, admin_username: str, members: Optional[list] = None) -> bool:
        """Store room information in DHT with additional metadata."""
        key = f"room:{code}"
        value = {
            "admin": admin_username,
            "members": members or [admin_username],
            "created_at": str(asyncio.get_event_loop().time()),
            "status": "active"
        }
        
        async with self.connection():
            success = await self.set(key, value)
            if success:
                logger.info(f"Room {code} created successfully")
            return success
    
    async def get_room(self, code: str) -> Optional[Dict]:
        """Retrieve room information from DHT with validation."""
        key = f"room:{code}"
        async with self.connection():
            data = await self.get(key)
            if data and isinstance(data, dict) and data.get("status") == "active":
                return data
            return None

# Singleton instance initialization
async def initialize_dht():
    try:
        dht = await DHTManager.get_instance()
        logger.info("DHT Server initialized successfully")
        return dht
    except Exception as e:
        logger.error(f"Failed to initialize DHT server: {e}")
        raise

# Initialization should be done within an async context
def get_dht_instance():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(initialize_dht())