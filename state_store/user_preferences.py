import os
import json
import logging
from typing import Dict, Optional, Any

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Default user preferences
DEFAULT_PREFERENCES = {
    "system_prompt": "",  # Custom system prompt (empty = use default)
    "response_length": "medium",  # short, medium, long
    "conversation_style": "balanced",  # precise, balanced, creative
    "memory_enabled": True,  # Whether to use conversation memory
    "max_history_length": 10,  # Maximum number of messages to include in history
    "summarize_long_conversations": True,  # Whether to summarize long conversations
}

def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences for AI interactions
    
    Args:
        user_id: The Slack user ID
        
    Returns:
        Dictionary of user preferences
    """
    try:
        filepath = f"./data/preferences/{user_id}.json"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if os.path.exists(filepath):
            with open(filepath, "r") as file:
                preferences = json.load(file)
                # Ensure all default preferences exist
                for key, value in DEFAULT_PREFERENCES.items():
                    if key not in preferences:
                        preferences[key] = value
                return preferences
        else:
            # Return default preferences if no custom preferences exist
            return DEFAULT_PREFERENCES.copy()
    except Exception as e:
        logger.error(f"Error retrieving user preferences: {e}")
        return DEFAULT_PREFERENCES.copy()

def set_user_preferences(user_id: str, preferences: Dict[str, Any]) -> None:
    """
    Set user preferences for AI interactions
    
    Args:
        user_id: The Slack user ID
        preferences: Dictionary of user preferences to set
    """
    try:
        filepath = f"./data/preferences/{user_id}.json"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Get existing preferences
        existing_preferences = get_user_preferences(user_id)
        
        # Update with new preferences
        existing_preferences.update(preferences)
        
        # Save updated preferences
        with open(filepath, "w") as file:
            json.dump(existing_preferences, file)
    except Exception as e:
        logger.error(f"Error setting user preferences: {e}")

def get_system_prompt(user_id: str) -> str:
    """
    Get the system prompt for a user, either custom or default
    
    Args:
        user_id: The Slack user ID
        
    Returns:
        System prompt string
    """
    from ai.ai_constants import DEFAULT_SYSTEM_CONTENT
    
    try:
        preferences = get_user_preferences(user_id)
        custom_prompt = preferences.get("system_prompt", "")
        
        if custom_prompt and custom_prompt.strip():
            return custom_prompt
        else:
            # Modify default system content based on user preferences
            response_length = preferences.get("response_length", "medium")
            conversation_style = preferences.get("conversation_style", "balanced")
            
            system_prompt = DEFAULT_SYSTEM_CONTENT
            
            # Adjust for response length
            if response_length == "short":
                system_prompt += "\nKeep your responses very concise and to the point.\n"
            elif response_length == "long":
                system_prompt += "\nProvide detailed and comprehensive responses when appropriate.\n"
                
            # Adjust for conversation style
            if conversation_style == "precise":
                system_prompt += "\nBe precise, factual, and focus on accuracy.\n"
            elif conversation_style == "creative":
                system_prompt += "\nBe creative, think outside the box, and offer innovative perspectives.\n"
                
            return system_prompt
    except Exception as e:
        logger.error(f"Error getting system prompt: {e}")
        return DEFAULT_SYSTEM_CONTENT