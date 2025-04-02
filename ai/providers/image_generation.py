import os
import requests
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def generate_image(prompt: str, size: str = "1024x1024") -> Optional[str]:
    """
    Generate an image using the OpenAI DALL-E model.
    
    Args:
        prompt: The text prompt to generate an image from
        size: Image size (256x256, 512x512, or 1024x1024)
        
    Returns:
        URL of the generated image, or None if generation failed
    """
    try:
        # Get API key and base URL from environment variables
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        # Check if we're using a custom API endpoint
        if "deepinfra.com" in base_url:
            # DeepInfra doesn't support DALL-E, so we'll use the default OpenAI endpoint
            base_url = "https://api.openai.com/v1"
            logger.warning("Using default OpenAI endpoint for image generation as DeepInfra doesn't support DALL-E")
        
        if not api_key:
            logger.error("No OpenAI API key found in environment variables")
            return None
            
        # Validate size
        valid_sizes = ["256x256", "512x512", "1024x1024"]
        if size not in valid_sizes:
            logger.warning(f"Invalid size: {size}. Using default 1024x1024")
            size = "1024x1024"
            
        # Make API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": "dall-e-2",  # Using DALL-E 2 as it's more widely available
            "prompt": prompt,
            "n": 1,
            "size": size
        }
        
        response = requests.post(
            f"{base_url}/images/generations",
            headers=headers,
            data=json.dumps(data)
        )
        
        if response.status_code != 200:
            logger.error(f"Error generating image: {response.text}")
            return None
            
        response_data = response.json()
        if not response_data.get("data") or len(response_data["data"]) == 0:
            logger.error("No image data returned from API")
            return None
            
        # Return the URL of the generated image
        return response_data["data"][0]["url"]
        
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None