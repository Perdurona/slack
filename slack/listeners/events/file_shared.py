from slack_bolt import BoltContext
from slack_sdk import WebClient
from logging import Logger
from ai.providers import get_provider_response
from state_store.user_preferences import get_user_preferences, get_system_prompt
from state_store.conversation_memory import add_to_conversation_history, get_conversation_history
import re

def file_shared_callback(client: WebClient, event, logger: Logger, context: BoltContext):
    """
    Handles file_shared events, allowing the bot to process uploaded files.
    Currently supports text files for analysis.
    """
    try:
        # Get file info
        file_id = event.get("file_id")
        if not file_id:
            return
            
        file_info = client.files_info(file=file_id)
        file = file_info.get("file", {})
        
        # Check if this is a text file we can process
        file_type = file.get("filetype", "")
        mime_type = file.get("mimetype", "")
        
        # Get user and channel info
        user_id = event.get("user_id") or context.get("user_id")
        channel_id = file.get("channels", [])[0] if file.get("channels") else event.get("channel_id")
        
        if not user_id or not channel_id:
            logger.error("Missing user_id or channel_id in file_shared event")
            return
            
        # Only process text files for now
        if not (file_type in ["txt", "md", "py", "js", "html", "css", "json", "csv"] or 
                mime_type.startswith("text/")):
            # Acknowledge receipt but explain we can't process this type
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"I see you've shared a {file_type} file, but I can only analyze text files at the moment."
            )
            return
            
        # Get file content
        file_content = ""
        if file.get("url_private"):
            # Download the file content
            response = client.files_info(
                file=file_id,
                include_content=True
            )
            if response and response.get("content"):
                file_content = response.get("content")
            else:
                # Try to get content from permalink
                permalink = file.get("permalink")
                if permalink:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"I can't directly access the file content. You can copy and paste it to me, or use the /ask-bolty command with your question about the file."
                    )
                    return
        
        if not file_content:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="I couldn't read the content of this file. Please try uploading it again or copy and paste the content."
            )
            return
            
        # Truncate very large files
        if len(file_content) > 15000:
            file_content = file_content[:15000] + "\n\n[Content truncated due to length...]"
            
        # Get user preferences
        preferences = get_user_preferences(user_id)
        
        # Get conversation history if memory is enabled
        conversation_context = []
        if preferences["memory_enabled"]:
            conversation_context = get_conversation_history(user_id, channel_id)
            
        # Get system prompt based on user preferences
        system_content = get_system_prompt(user_id)
        
        # Add file context to the system prompt
        file_system_prompt = f"{system_content}\n\nThe user has shared a {file_type} file with the following content:\n\n{file_content}\n\nPlease analyze this content and provide helpful insights or answer questions about it."
        
        # Post "thinking" message
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="⏳ Analyzing your file..."
        )
        
        # Generate response
        try:
            prompt = f"I've uploaded a {file_type} file. Please analyze it and provide insights."
            
            # Add the file content to conversation history
            if preferences["memory_enabled"]:
                add_to_conversation_history(
                    user_id, 
                    f"[Shared a file: {file.get('name', 'unnamed')}]\n\nFile content (may be truncated):\n{file_content[:500]}...", 
                    True, 
                    channel_id
                )
            
            # Get AI response
            ai_response = get_provider_response(user_id, prompt, conversation_context, file_system_prompt)
            
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
                                    {"type": "text", "text": "📄 "},
                                    {"type": "text", "text": file.get("name", "File"), "style": {"bold": True}},
                                    {"type": "text", "text": " analysis:"}
                                ],
                            },
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": "\n\n" + ai_response}],
                            },
                        ],
                    }
                ],
            )
            
            # Add AI response to conversation history if memory is enabled
            if preferences["memory_enabled"]:
                add_to_conversation_history(user_id, ai_response, False, channel_id)
                
        except Exception as e:
            logger.error(f"Error generating response for file: {e}")
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                text=f"Error analyzing file: {e}"
            )
            
    except Exception as e:
        logger.error(f"Error in file_shared_callback: {e}")