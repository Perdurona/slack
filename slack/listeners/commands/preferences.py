import logging
from slack_sdk import WebClient
from slack_bolt import Ack, BoltContext
from state_store.user_preferences import get_user_preferences, set_user_preferences

logger = logging.getLogger(__name__)

def preferences_callback(ack, command, client, context):
    """
    Callback for the /ai-preferences command.
    Opens a modal for configuring AI interaction preferences.
    """
    ack()
    
    # Get current preferences
    user_id = context["user_id"]
    preferences = get_user_preferences(user_id)
    
    try:
        client.views_open(
            trigger_id=command["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "ai_preferences_modal",
                "title": {"type": "plain_text", "text": "AI Preferences"},
                "submit": {"type": "plain_text", "text": "Save"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Configure your AI interaction preferences. These settings will personalize how the AI responds to you."
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "input",
                        "block_id": "response_length_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "response_length_input",
                            "placeholder": {"type": "plain_text", "text": "Select response length"},
                            "initial_option": {
                                "text": {"type": "plain_text", "text": preferences["response_length"].capitalize()},
                                "value": preferences["response_length"]
                            },
                            "options": [
                                {"text": {"type": "plain_text", "text": "Short"}, "value": "short"},
                                {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                                {"text": {"type": "plain_text", "text": "Long"}, "value": "long"}
                            ]
                        },
                        "label": {"type": "plain_text", "text": "Response Length"}
                    },
                    {
                        "type": "input",
                        "block_id": "conversation_style_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "conversation_style_input",
                            "placeholder": {"type": "plain_text", "text": "Select conversation style"},
                            "initial_option": {
                                "text": {"type": "plain_text", "text": preferences["conversation_style"].capitalize()},
                                "value": preferences["conversation_style"]
                            },
                            "options": [
                                {"text": {"type": "plain_text", "text": "Precise"}, "value": "precise"},
                                {"text": {"type": "plain_text", "text": "Balanced"}, "value": "balanced"},
                                {"text": {"type": "plain_text", "text": "Creative"}, "value": "creative"}
                            ]
                        },
                        "label": {"type": "plain_text", "text": "Conversation Style"}
                    },
                    {
                        "type": "input",
                        "block_id": "memory_enabled_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "memory_enabled_input",
                            "placeholder": {"type": "plain_text", "text": "Enable conversation memory?"},
                            "initial_option": {
                                "text": {"type": "plain_text", "text": "Yes" if preferences["memory_enabled"] else "No"},
                                "value": "true" if preferences["memory_enabled"] else "false"
                            },
                            "options": [
                                {"text": {"type": "plain_text", "text": "Yes"}, "value": "true"},
                                {"text": {"type": "plain_text", "text": "No"}, "value": "false"}
                            ]
                        },
                        "label": {"type": "plain_text", "text": "Conversation Memory"}
                    },
                    {
                        "type": "input",
                        "block_id": "summarize_long_conversations_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "summarize_long_conversations_input",
                            "placeholder": {"type": "plain_text", "text": "Summarize long conversations?"},
                            "initial_option": {
                                "text": {"type": "plain_text", "text": "Yes" if preferences["summarize_long_conversations"] else "No"},
                                "value": "true" if preferences["summarize_long_conversations"] else "false"
                            },
                            "options": [
                                {"text": {"type": "plain_text", "text": "Yes"}, "value": "true"},
                                {"text": {"type": "plain_text", "text": "No"}, "value": "false"}
                            ]
                        },
                        "label": {"type": "plain_text", "text": "Summarize Long Conversations"}
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Custom System Prompt*\nOptionally provide a custom system prompt to control how the AI responds. Leave blank to use the default."
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "system_prompt_block",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "system_prompt_input",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "E.g., You are a helpful assistant that specializes in..."},
                            "initial_value": preferences.get("system_prompt", "")
                        },
                        "label": {"type": "plain_text", "text": "Custom System Prompt"}
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error opening AI preferences modal: {e}")
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=command["user_id"],
            text=f"Error opening preferences: {e}"
        )


def handle_preferences_submission(ack, view, client, body):
    """
    Handle the submission of the AI preferences modal.
    """
    ack()
    
    try:
        # Extract values from the view
        response_length = view["state"]["values"]["response_length_block"]["response_length_input"]["selected_option"]["value"]
        conversation_style = view["state"]["values"]["conversation_style_block"]["conversation_style_input"]["selected_option"]["value"]
        memory_enabled = view["state"]["values"]["memory_enabled_block"]["memory_enabled_input"]["selected_option"]["value"] == "true"
        summarize_long_conversations = view["state"]["values"]["summarize_long_conversations_block"]["summarize_long_conversations_input"]["selected_option"]["value"] == "true"
        system_prompt = view["state"]["values"]["system_prompt_block"]["system_prompt_input"]["value"]
        
        # Update user preferences
        preferences = {
            "response_length": response_length,
            "conversation_style": conversation_style,
            "memory_enabled": memory_enabled,
            "summarize_long_conversations": summarize_long_conversations,
            "system_prompt": system_prompt
        }
        
        set_user_preferences(body["user"]["id"], preferences)
        
        # Send confirmation message
        client.chat_postEphemeral(
            channel=body["user"]["id"],
            user=body["user"]["id"],
            text="Your AI preferences have been updated successfully! These settings will be applied to all your future conversations."
        )
    except Exception as e:
        logger.error(f"Error saving AI preferences: {e}")
        client.chat_postEphemeral(
            channel=body["user"]["id"],
            user=body["user"]["id"],
            text=f"Error saving preferences: {e}"
        )