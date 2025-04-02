import os
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

def load_environment_variables():
    """
    Load and normalize environment variables for the application.
    This ensures compatibility between different naming conventions.
    """
    # Load environment variables from .env file if it exists
    env_path = Path('.') / '.env'
    if env_path.exists():
        logger.info(f"Loading environment variables from {env_path}")
        load_dotenv(dotenv_path=env_path)
    else:
        logger.warning("No .env file found. Using environment variables from the system.")
    
    # Map OPENAI_* variables to LOCALAI_* variables if they don't exist
    if not os.environ.get("LOCALAI_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        os.environ["LOCALAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
        logger.info("Using OPENAI_API_KEY for LOCALAI_API_KEY")
    
    if not os.environ.get("LOCALAI_API_URL") and os.environ.get("OPENAI_BASE_URL"):
        os.environ["LOCALAI_API_URL"] = os.environ.get("OPENAI_BASE_URL")
        logger.info("Using OPENAI_BASE_URL for LOCALAI_API_URL")
    
    if not os.environ.get("LOCALAI_MODEL") and os.environ.get("OPENAI_MODEL"):
        os.environ["LOCALAI_MODEL"] = os.environ.get("OPENAI_MODEL")
        logger.info("Using OPENAI_MODEL for LOCALAI_MODEL")
    
    # Log the configuration
    logger.info(f"API URL: {os.environ.get('LOCALAI_API_URL', os.environ.get('OPENAI_BASE_URL', 'Not set'))}")
    logger.info(f"Model: {os.environ.get('LOCALAI_MODEL', os.environ.get('OPENAI_MODEL', 'Not set'))}")
    
    # Mask API key for logging
    api_key = os.environ.get("LOCALAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if api_key:
        masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        logger.info(f"API Key: {masked_key}")
    else:
        logger.warning("No API key found in environment variables")