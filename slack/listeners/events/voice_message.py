from slack_bolt import BoltContext
from slack_sdk import WebClient
from logging import Logger
from ai.transcription import transcribe_audio
from ai.providers import get_provider_response
from state_store.conversation_memory import add_to_conversation_history, get_conversation_history
from state_store.user_preferences import get_user_preferences, get_system_prompt

def handle_voice_message(client: WebClient, event: dict, context: BoltContext, logger: Logger):
    """
    Handle voice messages sent in Slack channels or DMs.
    Transcribes the audio and responds with AI-generated content.
    """
    try:
        # Extract necessary information
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))
        
        # Get the file information
        files = event.get("files", [])
        if not files or len(files) == 0:
            logger.error("No files found in voice message event")
            return
        
        # Find the voice message file
        voice_file = None
        for file in files:
            if file.get("filetype") in ["m4a", "mp3", "ogg", "wav"]:
                voice_file = file
                break
        
        if not voice_file:
            logger.error("No voice file found in message")
            return
        
        # Get the URL for the voice file
        file_url = voice_file.get("url_private")
        if not file_url:
            logger.error("No URL found for voice file")
            return
        
        # Post a "transcribing" message
        response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="🎤 Transcribing voice message..."
        )
        
        # Transcribe the audio
        transcription = transcribe_audio(file_url, logger)
        
        # If transcription failed or is empty
        if transcription.startswith("Error:") or not transcription.strip():
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                text=f"❌ {transcription if transcription.strip() else 'Failed to transcribe voice message.'}"
            )
            return
        
        # Update with transcription
        client.chat_update(
            channel=channel_id,
            ts=response["ts"],
            text=f"🎤 *Transcription:*\n>{transcription}\n\n⏳ Thinking..."
        )
        
        # Get user preferences
        preferences = get_user_preferences(user_id)
        
        # Get conversation history if memory is enabled
        conversation_context = []
        if preferences["memory_enabled"]:
            conversation_context = get_conversation_history(user_id, channel_id)
            # Add transcription to history
            add_to_conversation_history(user_id, transcription, True, channel_id)
        
        # Get system prompt based on user preferences
        system_content = get_system_prompt(user_id)
        
        # Generate AI response
        try:
            ai_response = get_provider_response(user_id, transcription, conversation_context, system_content)
            
            # Update the message with the response
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                blocks=[
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {"type": "text", "text": "🎤 "},
                                    {"type": "text", "text": "Transcription:", "style": {"bold": True}}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_quote",
                                "elements": [{"type": "text", "text": transcription}]
                            }
                        ]
                    },
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": ai_response}]
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
                text=f"🎤 *Transcription:*\n>{transcription}\n\n❌ Error generating response: {e}"
            )
            
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ Error processing voice message: {e}"
            )
        except:
            pass