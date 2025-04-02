import os
import logging
from slack_sdk import WebClient
from slack_bolt import Ack, BoltContext

logger = logging.getLogger(__name__)

def localai_settings_callback(ack, command, client, context):
    """
    Callback for the /localai-settings command.
    Opens a modal for configuring LocalAI settings.
    """
    ack()
    
    # Get current settings from environment variables
    current_api_key = os.environ.get("LOCALAI_API_KEY", "")
    current_api_url = os.environ.get("LOCALAI_API_URL", "https://api.deepinfra.com/v1/openai")
    current_custom_models = os.environ.get("LOCALAI_CUSTOM_MODELS", "")
    
    # Mask API key for display
    masked_api_key = "••••••••" if current_api_key else ""
    
    try:
        client.views_open(
            trigger_id=command["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "localai_settings_modal",
                "title": {"type": "plain_text", "text": "LocalAI Settings"},
                "submit": {"type": "plain_text", "text": "Save"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Configure your LocalAI compatible API settings. This includes services like DeepInfra and other LocalAI compatible endpoints."
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "input",
                        "block_id": "api_key_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "api_key_input",
                            "placeholder": {"type": "plain_text", "text": "Enter your API key"},
                            "initial_value": masked_api_key
                        },
                        "label": {"type": "plain_text", "text": "API Key"}
                    },
                    {
                        "type": "input",
                        "block_id": "api_url_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "api_url_input",
                            "placeholder": {"type": "plain_text", "text": "Enter API URL"},
                            "initial_value": current_api_url
                        },
                        "label": {"type": "plain_text", "text": "API URL"}
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Custom Models Configuration*\nFormat: `model_id:display_name:provider:max_tokens`\nMultiple models can be separated by commas."
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "custom_models_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "custom_models_input",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "E.g., my-model:My Custom Model:MyProvider:4096"},
                            "initial_value": current_custom_models
                        },
                        "label": {"type": "plain_text", "text": "Custom Models"}
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error opening LocalAI settings modal: {e}")
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=command["user_id"],
            text=f"Error opening settings: {e}"
        )


def handle_localai_settings_submission(ack, view, client, body):
    """
    Handle the submission of the LocalAI settings modal.
    """
    ack()
    
    try:
        # Extract values from the view
        api_key = view["state"]["values"]["api_key_block"]["api_key_input"]["value"]
        api_url = view["state"]["values"]["api_url_block"]["api_url_input"]["value"]
        custom_models = view["state"]["values"]["custom_models_block"]["custom_models_input"]["value"]
        
        # Don't update API key if it's masked (user didn't change it)
        if api_key == "••••••••":
            api_key = os.environ.get("LOCALAI_API_KEY", "")
        
        # Update environment variables
        os.environ["LOCALAI_API_KEY"] = api_key
        os.environ["LOCALAI_API_URL"] = api_url
        os.environ["LOCALAI_CUSTOM_MODELS"] = custom_models
        
        # Send confirmation message
        client.chat_postEphemeral(
            channel=body["user"]["id"],
            user=body["user"]["id"],
            text="LocalAI settings updated successfully! You can now use LocalAI compatible models in your conversations."
        )
    except Exception as e:
        logger.error(f"Error saving LocalAI settings: {e}")
        client.chat_postEphemeral(
            channel=body["user"]["id"],
            user=body["user"]["id"],
            text=f"Error saving settings: {e}"
        )