from slack_bolt import Ack, Say, BoltContext
from logging import Logger
from ai.providers import get_provider_response
from ai.streaming import stream_response
from slack_sdk import WebClient
from state_store.conversation_memory import add_to_conversation_history, get_conversation_history
from state_store.user_preferences import get_user_preferences, get_system_prompt
import uuid

"""
Callback for handling the 'ask-bolty' command. It acknowledges the command, retrieves the user's ID and prompt,
checks if the prompt is empty, and responds with either an error message or the provider's response.
"""


def ask_callback(client: WebClient, ack: Ack, command, say: Say, logger: Logger, context: BoltContext):
    try:
        ack()
        user_id = context["user_id"]
        channel_id = context["channel_id"]
        prompt = command["text"]

        if prompt == "":
            client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Looks like you didn't provide a prompt. Try again."
            )
            return
            
        # Get user preferences
        preferences = get_user_preferences(user_id)
        
        # Get conversation history if memory is enabled
        conversation_context = []
        if preferences["memory_enabled"]:
            conversation_context = get_conversation_history(user_id, channel_id)
            # Add current message to history
            add_to_conversation_history(user_id, prompt, True, channel_id)
        
        # Get system prompt based on user preferences
        system_content = get_system_prompt(user_id)
        
        # Post "thinking" message
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="⏳ Thinking..."
        )
        
        # Generate response
        try:
            from state_store.get_user_state import get_user_state
            provider_name, model_name = get_user_state(user_id, False)
            
            # Use streaming response if not in ephemeral message
            ai_response = get_provider_response(user_id, prompt, conversation_context, system_content)
            
            # Update the message with the response and add interactive buttons
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                blocks=[
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_quote",
                                "elements": [{"type": "text", "text": prompt}],
                            },
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": ai_response}],
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
            
            # Add AI response to conversation history if memory is enabled
            if preferences["memory_enabled"]:
                add_to_conversation_history(user_id, ai_response, False, channel_id)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                text=f"Error generating response: {e}"
            )
            
    except Exception as e:
        logger.error(e)
        client.chat_postEphemeral(
            channel=channel_id, 
            user=user_id, 
            text=f"Received an error from Bolty: {e}"
        )
