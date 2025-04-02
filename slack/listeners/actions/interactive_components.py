from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from logging import Logger
from ai.providers import get_provider_response
from state_store.conversation_memory import add_to_conversation_history, get_conversation_history
from state_store.user_preferences import get_user_preferences, get_system_prompt
import json
import uuid

def handle_button_click(ack: Ack, body: dict, client: WebClient, context: BoltContext, logger: Logger):
    """
    Handle button click actions in interactive messages
    """
    try:
        ack()
        
        # Extract necessary information
        user_id = body["user"]["id"]
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        action_id = body["actions"][0]["action_id"]
        
        # Get the original message
        original_message = body["message"]
        
        # Handle different button actions
        if action_id.startswith("regenerate_"):
            # Extract the original prompt from the message
            original_prompt = None
            for block in original_message.get("blocks", []):
                if block.get("type") == "rich_text":
                    for element in block.get("elements", []):
                        if element.get("type") == "rich_text_quote":
                            quote_elements = element.get("elements", [])
                            if quote_elements and quote_elements[0].get("type") == "text":
                                original_prompt = quote_elements[0].get("text")
                                break
            
            if not original_prompt:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="Could not find the original prompt to regenerate a response."
                )
                return
            
            # Update the message to show "regenerating"
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text="⏳ Regenerating response..."
            )
            
            # Get user preferences
            preferences = get_user_preferences(user_id)
            
            # Get conversation history if memory is enabled
            conversation_context = []
            if preferences["memory_enabled"]:
                conversation_context = get_conversation_history(user_id, channel_id)
            
            # Get system prompt based on user preferences
            system_content = get_system_prompt(user_id)
            
            # Generate new response
            try:
                new_response = get_provider_response(user_id, original_prompt, conversation_context, system_content)
                
                # Update the message with the new response
                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    blocks=[
                        {
                            "type": "rich_text",
                            "elements": [
                                {
                                    "type": "rich_text_quote",
                                    "elements": [{"type": "text", "text": original_prompt}],
                                },
                                {
                                    "type": "rich_text_section",
                                    "elements": [{"type": "text", "text": new_response}],
                                },
                            ],
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "🔄 Regenerate", "emoji": True},
                                    "action_id": f"regenerate_{uuid.uuid4()}",
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "👍 Helpful", "emoji": True},
                                    "action_id": f"feedback_helpful_{uuid.uuid4()}"
                                },
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "👎 Not Helpful", "emoji": True},
                                    "action_id": f"feedback_not_helpful_{uuid.uuid4()}"
                                }
                            ]
                        }
                    ]
                )
                
                # Add new response to conversation history if memory is enabled
                if preferences["memory_enabled"]:
                    add_to_conversation_history(user_id, new_response, False, channel_id)
                    
            except Exception as e:
                logger.error(f"Error regenerating response: {e}")
                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"Error regenerating response: {e}"
                )
                
        elif action_id.startswith("feedback_helpful_"):
            # Handle positive feedback
            # Update the message to acknowledge feedback
            blocks = original_message.get("blocks", [])
            
            # Remove the actions block
            blocks = [block for block in blocks if block.get("type") != "actions"]
            
            # Add feedback acknowledgment
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "✅ *Feedback received:* Thanks for the positive feedback!"
                    }
                ]
            })
            
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=blocks
            )
            
            # Here you could log the positive feedback for future model improvements
            
        elif action_id.startswith("feedback_not_helpful_"):
            # Handle negative feedback
            # Update the message to acknowledge feedback
            blocks = original_message.get("blocks", [])
            
            # Remove the actions block
            blocks = [block for block in blocks if block.get("type") != "actions"]
            
            # Add feedback acknowledgment and follow-up options
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "📝 *Feedback received:* Thanks for letting us know this response wasn't helpful."
                    }
                ]
            })
            
            # Add follow-up actions
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔄 Try Again", "emoji": True},
                        "action_id": f"regenerate_{uuid.uuid4()}",
                        "style": "primary"
                    }
                ]
            })
            
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=blocks
            )
            
            # Here you could log the negative feedback for future model improvements
            
    except Exception as e:
        logger.error(f"Error handling button click: {e}")
        try:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Error processing your action: {e}"
            )
        except:
            pass