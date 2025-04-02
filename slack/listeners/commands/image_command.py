from slack_bolt import Ack, Say, BoltContext
from logging import Logger
from slack_sdk import WebClient
from ai.providers.image_generation import generate_image

def image_callback(client: WebClient, ack: Ack, command, say: Say, logger: Logger, context: BoltContext):
    """
    Callback for handling the 'image' command. It generates an image based on the provided prompt
    using the DALL-E model and posts it to the channel.
    """
    try:
        ack()
        user_id = context["user_id"]
        channel_id = context["channel_id"]
        prompt = command["text"]

        if prompt == "":
            client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Please provide a prompt for the image generation."
            )
            return
            
        # Post "thinking" message
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="🎨 Generating image..."
        )
        
        # Generate image
        try:
            image_url = generate_image(prompt)
            
            if not image_url:
                client.chat_update(
                    channel=channel_id,
                    ts=response["ts"],
                    text="Sorry, I couldn't generate an image. Please try again with a different prompt."
                )
                return
                
            # Post the image to the channel
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Image prompt:* {prompt}"
                        }
                    },
                    {
                        "type": "image",
                        "image_url": image_url,
                        "alt_text": prompt
                    }
                ]
            )
                
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            client.chat_update(
                channel=channel_id,
                ts=response["ts"],
                text=f"Error generating image: {e}"
            )
            
    except Exception as e:
        logger.error(e)
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=f"Received an error while generating image: {e}")