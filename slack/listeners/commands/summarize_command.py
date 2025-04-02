from slack_bolt import Ack, Say, BoltContext
from logging import Logger
from ai.providers import get_provider_response
from slack_sdk import WebClient
from state_store.user_preferences import get_user_preferences, get_system_prompt
import time

def summarize_callback(client: WebClient, ack: Ack, command, say: Say, logger: Logger, context: BoltContext):
    """
    Callback for handling the 'summarize' command. It retrieves recent messages from a channel
    and generates a summary using the AI provider.
    """
    try:
        ack()
        user_id = context["user_id"]
        channel_id = context["channel_id"]
        
        # Parse command options
        text = command.get("text", "")
        
        # Default to 50 messages if not specified
        message_count = 50
        
        # Check if a number was provided
        if text.strip().isdigit():
            message_count = min(int(text.strip()), 100)  # Limit to 100 messages max
        
        # Post "thinking" message
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"⏳ Retrieving the last {message_count} messages and generating a summary..."
        )
        
        # Get channel history
        try:
            # Get conversation history
            history_response = client.conversations_history(
                channel=channel_id,
                limit=message_count
            )
            
            messages = history_response.get("messages", [])
            
            if not messages:
                client.chat_update(
                    channel=channel_id,
                    ts=response["ts"],
                    text="No messages found to summarize."
                )
                return
                
            # Format messages for the AI
            formatted_messages = []
            for msg in reversed(messages):  # Reverse to get chronological order
                # Skip bot messages and system messages
                if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                    continue
                    
                user_info = {}
                try:
                    if msg.get("user"):
                        user_info = client.users_info(user=msg.get("user")).get("user", {})
                except Exception:
                    # If we can't get user info, just use the user ID
                    pass
                    
                user_name = user_info.get("real_name") or user_info.get("name") or msg.get("user", "Unknown user")
                timestamp = msg.get("ts", "")
                if timestamp:
                    # Convert Unix timestamp to readable format
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(timestamp)))
                
                text = msg.get("text", "")
                
                formatted_messages.append(f"{user_name} ({timestamp}): {text}")
            
            if not formatted_messages:
                client.chat_update(
                    channel=channel_id,
                    ts=response["ts"],
                    text="No valid messages found to summarize."
                )
                return
                
            # Get user preferences
            preferences = get_user_preferences(user_id)
            
            # Get system prompt based on user preferences
            system_content = get_system_prompt(user_id)
            
            # Create a special system prompt for summarization
            summary_system_prompt = f"{system_content}\n\nYou are tasked with summarizing a Slack conversation. Please provide a concise summary that captures the main points, decisions, and action items from the conversation. Format your response with clear sections and bullet points where appropriate."
            
            # Create the prompt for the AI
            conversation_text = "\n".join(formatted_messages)
            prompt = f"Please summarize the following Slack conversation:\n\n{conversation_text}"
            
            # Get AI response
            ai_response = get_provider_response(user_id, prompt, [], summary_system_prompt)
            
            # Update the message with the response
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📝 Summary of last {len(formatted_messages)} messages"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": ai_response}],
                            }
                        ],
                    }
                ],
            )
                
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                text=f"Error generating summary: {e}"
            )
            
    except Exception as e:
        logger.error(e)
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=f"Received an error while summarizing: {e}")