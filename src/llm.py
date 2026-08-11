import os
import json
import boto3
from openai import OpenAI
from typing import Dict, Any, Optional
from src.token_tracker import TokenTracker

class LLMClient:
    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize unified LLM Client supporting AWS Bedrock and OpenAI.
        """
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai").lower()
        self.model = model or os.getenv("LLM_MODEL")

        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            self.openai_client = OpenAI(api_key=api_key)
        elif self.provider == "bedrock":
            # Bedrock client loads credentials from the environment / IAM role
            self.bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name=os.getenv("AWS_REGION") or "us-east-1"
            )
            # Default Bedrock model if not specified
            if not self.model:
                self.model = "google.gemma-3-12b-it"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def call(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2, max_tokens: int = 1500) -> str:
        """
        Uniform text generation interface.
        """
        if self.provider == "openai":
            try:
                return self._call_openai(prompt, system_prompt, temperature, max_tokens)
            except Exception as e:
                import logging
                logger = logging.getLogger("LLMClient")
                logger.error(f"OpenAI call failed: {e}. Falling back to Bedrock (Gemma).")
                
                try:
                    from src.notifications import NotificationClient
                    NotificationClient().send_brainstorm_alert("LLM Fallback Alert", f"OpenAI failed with error: {e}. Falling back to Bedrock.")
                except Exception as notif_e:
                    logger.error(f"Failed to send fallback notification: {notif_e}")
                    
                # Initialize bedrock client if not already initialized
                if not hasattr(self, 'bedrock_client'):
                    self.bedrock_client = boto3.client(
                        service_name="bedrock-runtime",
                        region_name=os.getenv("AWS_REGION") or "us-east-1"
                    )
                # Fallback to Bedrock implementation
                original_model = self.model
                self.model = "google.gemma-3-12b-it" 
                res = self._call_bedrock(prompt, system_prompt, temperature, max_tokens)
                self.model = original_model
                return res
        elif self.provider == "bedrock":
            return self._call_bedrock(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider {self.provider}")

    def _call_openai(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.openai_client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        try:
            if response.usage:
                prompt_tokens = response.usage.prompt_tokens
                comp_tokens = response.usage.completion_tokens
                TokenTracker.log("openai", self.model or "gpt-4o", prompt_tokens, comp_tokens)
        except Exception:
            pass
            
        return response.choices[0].message.content.strip()

    def _call_bedrock(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
        import time
        import logging
        logger = logging.getLogger("LLMClient")
        
        model_id = self.model or "google.gemma-3-12b-it"

        # Construct messages parameter
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]

        # Construct system parameter
        system = []
        if system_prompt:
            system.append({"text": system_prompt})

        # Construct inference config
        inference_config = {
            "temperature": temperature,
            "maxTokens": max_tokens
        }

        kwargs = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": inference_config
        }
        if system:
            kwargs["system"] = system

        max_retries = 8
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = self.bedrock_client.converse(**kwargs)
                break
            except Exception as e:
                error_str = str(e)
                if "ThrottlingException" in error_str or "TooManyRequests" in error_str or "429" in error_str:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for Bedrock API. Failing.")
                        raise e
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning(f"Throttled by Bedrock. Retrying in {sleep_time} seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    raise e
        
        try:
            usage = response.get("usage", {})
            prompt_tokens = usage.get("inputTokens", 0)
            comp_tokens = usage.get("outputTokens", 0)
            TokenTracker.log("bedrock", model_id, prompt_tokens, comp_tokens)
        except Exception:
            pass
            
        return response["output"]["message"]["content"][0]["text"].strip()
