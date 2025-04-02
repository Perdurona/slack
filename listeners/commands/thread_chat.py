import logging
from logging import Logger
from slack_bolt import Ack, Say, BoltContext
from slack_sdk import WebClient
from ai.providers import get_provider_response
from ai.streaming import stream_response
from state_store.conversation_memory import get_conversation_history, add_to_conversation_history, summarize_conversation
from state_store.user_preferences import get_user_preferences, get_system_prompt
from state_store.get_user_state import get_user_state

logger = logging.getLogger(__name__)

def thread_chat_callback(client: WebClient, ack: Ack, command, say: Say, logger: Logger, context: BoltContext):
    """
    Callback for handling the 'chat' command.
    Starts a new thread-based conversation with the AI.
    """
    try:
        ack()
        user_id = context["user_id"]
        channel_id = context["channel_id"]
        prompt = command["text"]
        
        if prompt == "":
            client.chat_postEphemeral(
                channel=channel_id, 
                user=user_id, 
                text="Please provide a message to start the conversation."
            )
            return
            
        # Post initial message to create a thread
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"*Thread chat with AI*\n\n> {prompt}"
        )
        
        thread_ts = response["ts"]
        
        # Get user preferences
        preferences = get_user_preferences(user_id)
        
        # Add user message to conversation history if memory is enabled
        if preferences["memory_enabled"]:
            add_to_conversation_history(user_id, prompt, True, channel_id, thread_ts)
        
        # Get provider and model
        provider_name, model_name = get_user_state(user_id, False)
        
        # Get system prompt based on user preferences
        system_content = get_system_prompt(user_id)
        
        # Generate response (streaming if possible)
        try:
            # Use streaming response
            stream_response(
                provider_name=provider_name,
                model_name=model_name,
                prompt=prompt,
                system_content=system_content,
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts
            )
        except Exception as e:
            logger.error(f"Error with streaming response: {e}")
            # Fall back to non-streaming response
            ai_response = get_provider_response(user_id, prompt, [], system_content)
            
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=ai_response
            )
            
            # Add AI response to conversation history if memory is enabled
            if preferences["memory_enabled"]:
                add_to_conversation_history(user_id, ai_response, False, channel_id, thread_ts)
                
    except Exception as e:
        logger.error(e)
        client.chat_postEphemeral(
            channel=channel_id, 
            user=user_id, 
            text=f"Received an error from the AI:\n{e}"
        )

def handle_thread_message(client: WebClient, event, logger: Logger, context: BoltContext):
    """
    Handle messages posted in threads that were started by the chat command.
    """
    try:
        # Check if this is a thread and if the bot is mentioned
        if "thread_ts" not in event or "bot_id" in event:
            return
            
        # Get message details
        user_id = event["user"]
        channel_id = event["channel"]
        thread_ts = event["thread_ts"]
        message_text = event["text"]
        
        # Check if this is a thread started by the bot
        thread_parent = client.conversations_history(
            channel=channel_id,
            latest=thread_ts,
            limit=1,
            inclusive=True
        )
        
        if not thread_parent["messages"] or "bot_id" not in thread_parent["messages"][0]:
            return
            
        # Get user preferences
        preferences = get_user_preferences(user_id)
        
        # Get conversation history if memory is enabled
        conversation_context = []
        if preferences["memory_enabled"]:
            conversation_context = get_conversation_history(user_id, channel_id, thread_ts)
            # Add current message to history
            add_to_conversation_history(user_id, message_text, True, channel_id, thread_ts)
        
        # Check if we should summarize a long conversation
        summary = None
        if preferences["summarize_long_conversations"] and len(conversation_context) > 8:
            summary = summarize_conversation(user_id, channel_id, thread_ts)
        
        # Get provider and model
        provider_name, model_name = get_user_state(user_id, False)
        
        # Get system prompt based on user preferences
        system_content = get_system_prompt(user_id)
        
        # Add summary to system content if available
        if summary:
            system_content += f"\n\nHere is a summary of the conversation so far:\n{summary}\n\n"
        
        # Generate response (streaming if possible)
        try:
            # Use streaming response
            stream_response(
                provider_name=provider_name,
                model_name=model_name,
                prompt=message_text,
                system_content=system_content,
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts
            )
        except Exception as e:
            logger.error(f"Error with streaming response: {e}")
            # Fall back to non-streaming response
            ai_response = get_provider_response(user_id, message_text, conversation_context, system_content)
            
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=ai_response
            )
            
            # Add AI response to conversation history if memory is enabled
            if preferences["memory_enabled"]:
                add_to_conversation_history(user_id, ai_response, False, channel_id, thread_ts)
                
    except Exception as e:
        logger.error(f"Error handling thread message: {e}")
        # Don't send error messages in threads to avoid spam