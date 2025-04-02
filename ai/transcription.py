import os
import requests
import tempfile
from logging import Logger

def transcribe_audio(audio_url: str, logger: Logger = None) -> str:
    """
    Transcribe audio from a Slack voice message URL.
    
    Args:
        audio_url: URL of the audio file from Slack
        logger: Optional logger for debugging
        
    Returns:
        Transcribed text or error message
    """
    try:
        # Check if we have OpenAI API key for Whisper API
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return "Error: OpenAI API key not found for transcription."
        
        # Download the audio file
        response = requests.get(audio_url, stream=True)
        if response.status_code != 200:
            if logger:
                logger.error(f"Failed to download audio: {response.status_code}")
            return "Error: Failed to download audio file."
        
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # Use OpenAI's Whisper API for transcription
        try:
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            # Check if we're using a custom OpenAI base URL
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            
            # If we're using DeepInfra, fall back to OpenAI for transcription
            if "deepinfra.com" in base_url:
                base_url = "https://api.openai.com/v1"
            
            with open(temp_file_path, "rb") as audio_file:
                files = {
                    "file": audio_file,
                    "model": (None, "whisper-1")
                }
                
                response = requests.post(
                    f"{base_url}/audio/transcriptions",
                    headers=headers,
                    files=files
                )
                
                if response.status_code != 200:
                    if logger:
                        logger.error(f"Transcription API error: {response.status_code}, {response.text}")
                    return f"Error: Transcription service returned status {response.status_code}"
                
                result = response.json()
                return result.get("text", "No transcription returned")
                
        except Exception as e:
            if logger:
                logger.error(f"Transcription error: {e}")
            return f"Error during transcription: {str(e)}"
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    except Exception as e:
        if logger:
            logger.error(f"Audio processing error: {e}")
        return f"Error processing audio: {str(e)}"