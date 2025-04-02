import os
import requests
import logging
from .base_provider import BaseAPIProvider

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class LocalAI_API(BaseAPIProvider):
    """
    Provider for LocalAI compatible APIs including DeepInfra and other LocalAI compatible services.
    This provider allows configuring custom API endpoints and models.
    """
    
    # Default models - can be extended by users
    MODELS = {
        # DeepInfra models
        "deepinfra/mistralai/Mistral-7B-Instruct-v0.2": {
            "name": "Mistral 7B Instruct",
            "provider": "DeepInfra",
            "max_tokens": 4096
        },
        "deepinfra/meta-llama/Llama-2-70b-chat-hf": {
            "name": "Llama 2 70B Chat",
            "provider": "DeepInfra",
            "max_tokens": 4096
        },
        "deepinfra/codellama/CodeLlama-34b-Instruct-hf": {
            "name": "CodeLlama 34B Instruct",
            "provider": "DeepInfra",
            "max_tokens": 4096
        },
        "deepinfra/jondurbin/airoboros-l2-70b-gpt4-1.4.1": {
            "name": "Airoboros L2 70B",
            "provider": "DeepInfra",
            "max_tokens": 4096
        },
        "deepseek-ai/DeepSeek-R1": {
            "name": "DeepSeek R1",
            "provider": "DeepInfra",
            "max_tokens": 4096
        },
        # Add more models as needed
    }

    def __init__(self):
        # Get API key and base URL from environment variables
        # First check LOCALAI_* variables, then fall back to OPENAI_* variables
        self.api_key = os.environ.get("LOCALAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        self.base_url = os.environ.get("LOCALAI_API_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai"))
        
        # Set default model from environment if available
        self.default_model = os.environ.get("LOCALAI_MODEL", os.environ.get("OPENAI_MODEL", ""))
        
        # Load custom models from environment if available
        self._load_custom_models()

    def _load_custom_models(self):
        """Load custom models from environment variables if available"""
        custom_models_str = os.environ.get("LOCALAI_CUSTOM_MODELS", "")
        if custom_models_str:
            try:
                # Format: model_id1:name1:provider1:max_tokens1,model_id2:name2:provider2:max_tokens2
                custom_models = custom_models_str.split(",")
                for model_str in custom_models:
                    parts = model_str.split(":")
                    if len(parts) == 4:
                        model_id, name, provider, max_tokens = parts
                        self.MODELS[model_id] = {
                            "name": name,
                            "provider": provider,
                            "max_tokens": int(max_tokens)
                        }
            except Exception as e:
                logger.error(f"Error loading custom models: {e}")

    def set_model(self, model_name: str):
        if model_name not in self.MODELS.keys():
            raise ValueError(f"Invalid model: {model_name}")
        self.current_model = model_name

    def get_models(self) -> dict:
        if self.api_key:
            # If we have a default model from environment, ensure it's in the models list
            if self.default_model and self.default_model not in self.MODELS:
                # Add the default model if it's not already in the list
                self.MODELS[self.default_model] = {
                    "name": self.default_model.split("/")[-1],
                    "provider": "DeepInfra",
                    "max_tokens": 4096
                }
            return self.MODELS
        else:
            return {}

    def generate_response(self, prompt: str, system_content: str) -> str:
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.current_model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.MODELS[self.current_model]["max_tokens"]
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")
                
            response_json = response.json()
            return response_json["choices"][0]["message"]["content"]
            
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            raise e
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise e