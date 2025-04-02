import os
import json
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Maximum number of messages to store in conversation history
MAX_HISTORY_LENGTH = 10

def get_conversation_history(user_id: str, channel_id: str = None, thread_ts: str = None) -> List[Dict]:
    """
    Retrieve conversation history for a user in a specific context (channel/thread)
    
    Args:
        user_id: The Slack user ID
        channel_id: Optional channel ID for channel-specific history
        thread_ts: Optional thread timestamp for thread-specific history
        
    Returns:
        List of message dictionaries containing 'user', 'text', and 'timestamp'
    """
    try:
        # Create a unique identifier for this conversation context
        context_id = f"{user_id}"
        if channel_id:
            context_id += f"_{channel_id}"
        if thread_ts:
            context_id += f"_{thread_ts}"
            
        filepath = f"./data/conversations/{context_id}.json"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if os.path.exists(filepath):
            with open(filepath, "r") as file:
                return json.load(file)
        else:
            return []
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        return []

def add_to_conversation_history(user_id: str, message: str, is_user: bool, 
                               channel_id: str = None, thread_ts: str = None) -> None:
    """
    Add a message to the conversation history
    
    Args:
        user_id: The Slack user ID
        message: The message text
        is_user: True if the message is from the user, False if from the bot
        channel_id: Optional channel ID for channel-specific history
        thread_ts: Optional thread timestamp for thread-specific history
    """
    try:
        # Create a unique identifier for this conversation context
        context_id = f"{user_id}"
        if channel_id:
            context_id += f"_{channel_id}"
        if thread_ts:
            context_id += f"_{thread_ts}"
            
        filepath = f"./data/conversations/{context_id}.json"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Get existing history or create new
        history = get_conversation_history(user_id, channel_id, thread_ts)
        
        # Add new message
        history.append({
            "user": "User" if is_user else "Assistant",
            "text": message,
            "timestamp": str(int(float(thread_ts) if thread_ts else 0))
        })
        
        # Limit history length
        if len(history) > MAX_HISTORY_LENGTH:
            history = history[-MAX_HISTORY_LENGTH:]
        
        # Save updated history
        with open(filepath, "w") as file:
            json.dump(history, file)
    except Exception as e:
        logger.error(f"Error adding to conversation history: {e}")

def clear_conversation_history(user_id: str, channel_id: str = None, thread_ts: str = None) -> None:
    """
    Clear the conversation history for a user in a specific context
    
    Args:
        user_id: The Slack user ID
        channel_id: Optional channel ID for channel-specific history
        thread_ts: Optional thread timestamp for thread-specific history
    """
    try:
        # Create a unique identifier for this conversation context
        context_id = f"{user_id}"
        if channel_id:
            context_id += f"_{channel_id}"
        if thread_ts:
            context_id += f"_{thread_ts}"
            
        filepath = f"./data/conversations/{context_id}.json"
        
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")

def summarize_conversation(user_id: str, channel_id: str = None, thread_ts: str = None) -> Optional[str]:
    """
    Generate a summary of the conversation history using the selected AI provider
    
    Args:
        user_id: The Slack user ID
        channel_id: Optional channel ID for channel-specific history
        thread_ts: Optional thread timestamp for thread-specific history
        
    Returns:
        A summary of the conversation or None if error
    """
    try:
        from ai.providers import get_provider_response
        
        history = get_conversation_history(user_id, channel_id, thread_ts)
        
        if not history or len(history) < 3:
            return None
            
        # Format conversation for summarization
        conversation_text = "\n".join([f"{msg['user']}: {msg['text']}" for msg in history])
        
        # Create summarization prompt
        prompt = f"Please summarize the following conversation concisely, focusing on the main points and any decisions made:\n\n{conversation_text}"
        
        # Use the user's selected AI provider to generate summary
        system_content = "You are a helpful assistant that summarizes conversations accurately and concisely."
        summary = get_provider_response(user_id, prompt, [], system_content)
        
        return summary
    except Exception as e:
        logger.error(f"Error summarizing conversation: {e}")
        return None