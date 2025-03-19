import asyncio  # Import asyncio for asynchronous operations
import json  # Import json module (unused in this code, likely a leftover)
from kademlia.network import Server  # Import Server class from Kademlia library for DHT functionality
from typing import Optional, Dict, Any  # Import typing hints for better code clarity
import pickle  # Import pickle for serializing/deserializing Python objects
import logging  # Import logging module for debugging and logging
from contextlib import asynccontextmanager  # Import asynccontextmanager for async context handling

logging.basicConfig(level=logging.INFO)  # Configure logging to show INFO level messages and above
logger = logging.getLogger(__name__)  # Create a logger instance for this module

class DHTManager:  # Define a class to manage the DHT
    _instance = None  # Class-level variable to store the singleton instance
    _server = None  # Class-level variable to store the Kademlia server instance
    _initialized = False  # Flag to track whether the DHT has been initialized
    _bootstrap_nodes = [  # List of bootstrap nodes for joining the DHT network
        ("127.0.0.1", 8468),  # Primary bootstrap node (localhost, port 8468)
        ("127.0.0.1", 9000)  # Backup bootstrap node (localhost, port 9000)
    ]   
    @classmethod  # Decorator to define a class method
    async def get_instance(cls):  # Method to get or create the singleton instance
        if not cls._instance:  # Check if the instance doesn’t exist
            cls._instance = cls()  # Create a new instance of DHTManager
            await cls._instance.initialize()  # Initialize the instance asynchronously
        return cls._instance  # Return the singleton instance
    
    
    
    async def initialize(self):  # Method to initialize the DHT server
        if not self._initialized:  # Check if not already initialized
            try:  # Begin try block to handle initialization errors
                self._server = Server()  # Create a new Kademlia Server instance
                await self._server.listen(8468)  # Start listening on port 8468

                # Bootstrap with known nodes
                # Try multiple bootstrap nodes
                bootstrap_successful = False  # Flag to track bootstrap success
                for node in self._bootstrap_nodes:  # Iterate over bootstrap nodes
                    try:  # Try to bootstrap with the current node
                        await self._server.bootstrap([node])  # Connect to the DHT network via the node
                        bootstrap_successful = True  # Mark bootstrap as successful
                        logger.info(f"Successfully bootstrapped with node {node}")  # Log success
                        break  # Exit loop on success
                    except Exception as e:  # Catch any bootstrap errors
                        logger.warning(f"Failed to bootstrap with {node}: {e}")  # Log warning
                
                if not bootstrap_successful:  # If no bootstrap nodes worked
                    # If no bootstrap nodes available, this becomes the first node
                    logger.info("No bootstrap nodes available. Starting as initial node.")  # Log as first node
                
                self._initialized = True  # Mark initialization as complete
                logger.info("DHT Manager initialized successfully")  # Log successful initialization
            except Exception as e:  # Catch any initialization errors
                logger.error(f"Failed to initialize DHT Manager: {e}")  # Log error
                raise  # Re-raise the exception
    
    @asynccontextmanager  # Decorator to define an async context manager
    async def connection(self):  # Context manager for DHT operations
        """Context manager to ensure proper connection handling"""
        try:  # Begin try block for connection handling
            if not self._initialized:  # Check if DHT isn’t initialized
                await self.initialize()  # Initialize if needed
            yield self  # Provide the DHTManager instance for use within the context
        except Exception as e:  # Catch any errors during context usage
            logger.error(f"DHT connection error: {e}")  # Log error
            raise  # Re-raise the exception
    
    async def set(self, key: str, value: Any) -> bool:  # Method to store a key-value pair in the DHT
        """Store a key-value pair in the DHT with retry logic."""
        max_retries = 3  # Set maximum number of retry attempts
        for attempt in range(max_retries):  # Loop through retry attempts
            try:  # Begin try block for storing value
                serialized_value = pickle.dumps(value)  # Serialize the value using pickle
                await self._server.set(key.encode(), serialized_value)  # Store the serialized value in DHT
                logger.info(f"Successfully stored key {key} in DHT")  # Log success
                return True  # Return success
            except Exception as e:  # Catch any storage errors
                if attempt == max_retries - 1:  # If this is the last attempt
                    logger.error(f"Final attempt to store value in DHT failed: {e}")  # Log final failure
                    return False  # Return failure
                logger.warning(f"Attempt {attempt + 1} to store value failed: {e}")  # Log retry failure
                await asyncio.sleep(1)  # Wait 1 second before retrying
    
    async def get(self, key: str) -> Optional[Any]:  # Method to retrieve a value from the DHT
        """Retrieve a value from the DHT with retry logic."""
        max_retries = 3  # Set maximum number of retry attempts
        for attempt in range(max_retries):  # Loop through retry attempts
            try:  # Begin try block for retrieval
                result = await self._server.get(key.encode())  # Get the value from DHT
                if result:  # If a value is found
                    return pickle.loads(result)  # Deserialize and return the value
                logger.info(f"No value found for key {key}")  # Log if no value exists
                return None  # Return None if no value
            except Exception as e:  # Catch any retrieval errors
                if attempt == max_retries - 1:  # If this is the last attempt
                    logger.error(f"Final attempt to retrieve value failed: {e}")  # Log final failure
                    return None  # Return None on failure
                logger.warning(f"Attempt {attempt + 1} to retrieve value failed: {e}")  # Log retry failure
                await asyncio.sleep(1)  # Wait 1 second before retrying
    
    async def store_room(self, code: str, admin_username: str, members: Optional[list] = None) -> bool:  # Method to store room info
        """Store room information in DHT with additional metadata."""
        key = f"room:{code}"  # Create a unique key for the room
        value = {  # Define the room data structure
            "admin": admin_username,  # Store the admin’s username
            "members": members or [admin_username],  # List of members, default to admin if none provided
            "created_at": str(asyncio.get_event_loop().time()),  # Timestamp of creation
            "status": "active"  # Room status
        }
        
        async with self.connection():  # Use the connection context manager
            success = await self.set(key, value)  # Store the room data
            if success:  # If storage succeeds
                logger.info(f"Room {code} created successfully")  # Log success
            return success  # Return success status
    
    async def get_room(self, code: str) -> Optional[Dict]:  # Method to retrieve room info
        """Retrieve room information from DHT with validation."""
        key = f"room:{code}"  # Create the key for the room
        async with self.connection():  # Use the connection context manager
            data = await self.get(key)  # Retrieve the room data
            if data and isinstance(data, dict) and data.get("status") == "active":  # Validate the data
                return data  # Return the room data if valid
            return None  # Return None if invalid or not found

# Singleton instance initialization
async def initialize_dht():  # Function to initialize the DHT singleton
    try:  # Begin try block for initialization
        dht = await DHTManager.get_instance()  # Get or create the DHTManager instance
        logger.info("DHT Server initialized successfully")  # Log success
        return dht  # Return the instance
    except Exception as e:  # Catch any initialization errors
        logger.error(f"Failed to initialize DHT server: {e}")  # Log error
        raise  # Re-raise the exception

# Initialization should be done within an async context
def get_dht_instance():  # Synchronous wrapper to get DHT instance
    loop = asyncio.get_event_loop()  # Get the current event loop
    return loop.run_until_complete(initialize_dht())  # Run the async initialization and return result

async def run():
    node = Server()
    await node.listen(5678)
    await node.bootstrap([("123.123.123.123", 5678)])
    await node.set("my-key", "my awesome value")
    result = await node.get("my-key")
    print(result)

asyncio.run(run())