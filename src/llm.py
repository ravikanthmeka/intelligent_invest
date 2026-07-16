import os
import json
import boto3
from openai import OpenAI
from typing import Dict, Any, Optional

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
                region_name=os.getenv("AWS_REGION", "us-east-1")
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
            return self._call_openai(prompt, system_prompt, temperature, max_tokens)
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
        return response.choices[0].message.content.strip()

    def _call_bedrock(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int) -> str:
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

        response = self.bedrock_client.converse(**kwargs)
        return response["output"]["message"]["content"][0]["text"].strip()
