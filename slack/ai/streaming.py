import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Any
import queue

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class StreamingResponseHandler:
    """
    Handler for streaming responses from AI providers
    """
    
    def __init__(self, client, channel_id: str, thread_ts: Optional[str] = None):
        """
        Initialize the streaming response handler
        
        Args:
            client: Slack client
            channel_id: Channel ID to post messages to
            thread_ts: Optional thread timestamp for threaded responses
        """
        self.client = client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.message_ts = None
        self.buffer = ""
        self.last_update_time = 0
        self.update_interval = 0.5  # Update message every 0.5 seconds
        self.queue = queue.Queue()
        self.is_complete = False
        self.is_running = False
        
    def start(self):
        """Start the streaming response handler"""
        self.is_running = True
        self.last_update_time = time.time()
        
        # Create initial message
        response = self.client.chat_postMessage(
            channel=self.channel_id,
            text="⏳ Thinking...",
            thread_ts=self.thread_ts
        )
        self.message_ts = response["ts"]
        
        # Start update thread
        threading.Thread(target=self._update_message_loop, daemon=True).start()
        
    def add_content(self, content: str):
        """
        Add content to the streaming response
        
        Args:
            content: Content to add
        """
        self.queue.put(content)
        
    def complete(self):
        """Mark the streaming response as complete"""
        self.is_complete = True
        
    def _update_message_loop(self):
        """Update message loop that runs in a separate thread"""
        while self.is_running:
            try:
                # Process all available content in the queue
                while not self.queue.empty():
                    self.buffer += self.queue.get_nowait()
                
                current_time = time.time()
                # Update the message if enough time has passed or the response is complete
                if (current_time - self.last_update_time >= self.update_interval) or self.is_complete:
                    if self.buffer:
                        # Replace "Thinking..." with actual content on first update
                        text = self.buffer
                        
                        # Update the message
                        self.client.chat_update(
                            channel=self.channel_id,
                            ts=self.message_ts,
                            text=text
                        )
                        
                        self.last_update_time = current_time
                
                # If complete and no more content in queue, exit loop
                if self.is_complete and self.queue.empty():
                    self.is_running = False
                    break
                    
                # Small sleep to prevent CPU hogging
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in streaming update loop: {e}")
                self.is_running = False
                break

def stream_response(provider_name: str, model_name: str, prompt: str, system_content: str, 
                   client, channel_id: str, thread_ts: Optional[str] = None) -> str:
    """
    Stream a response from an AI provider
    
    Args:
        provider_name: Name of the AI provider
        model_name: Name of the model to use
        prompt: User prompt
        system_content: System content/instructions
        client: Slack client
        channel_id: Channel ID to post messages to
        thread_ts: Optional thread timestamp for threaded responses
        
    Returns:
        The complete response text
    """
    try:
        # Import here to avoid circular imports
        from ai.providers import _get_provider
        
        # Initialize streaming handler
        handler = StreamingResponseHandler(client, channel_id, thread_ts)
        handler.start()
        
        # Get provider
        provider = _get_provider(provider_name)
        provider.set_model(model_name)
        
        # Check if provider supports streaming
        if hasattr(provider, 'generate_streaming_response'):
            # Use streaming API
            for chunk in provider.generate_streaming_response(prompt, system_content):
                handler.add_content(chunk)
                
            # Mark as complete
            handler.complete()
            return handler.buffer
        else:
            # Fall back to non-streaming API
            response = provider.generate_response(prompt, system_content)
            handler.add_content(response)
            handler.complete()
            return response
            
    except Exception as e:
        logger.error(f"Error in streaming response: {e}")
        # Try to update the message with the error
        if 'handler' in locals() and handler.message_ts:
            try:
                client.chat_update(
                    channel=channel_id,
                    ts=handler.message_ts,
                    text=f"Error generating response: {str(e)}"
                )
            except:
                pass
        raise e