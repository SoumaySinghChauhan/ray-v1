"""
Local Ollama-based LLM diagnosis provider.

Runs inference entirely on localhost - NO external API calls.
Suitable for Apple M1 8GB MacBook Air with small models.
"""

import json
import time
import requests
from typing import Any


class LocalDiagnosisProvider:
    """Local Ollama inference provider for RAY diagnosis."""

    def __init__(
        self,
        model: str = "qwen3:4b-instruct",
        host: str = "http://localhost:11434",
        temperature: float = 0.7,
        num_ctx: int = 2048,
    ):
        """
        Initialize local provider.

        Args:
            model: Ollama model identifier
            host: Ollama API endpoint (must be localhost)
            temperature: Sampling temperature
            num_ctx: Context window size (keep conservative for 8GB RAM)
        """
        # Security: Only allow localhost
        if "localhost" not in host and "127.0.0.1" not in host:
            raise ValueError(
                f"Local provider must use localhost, got: {host}"
            )

        self.model = model
        self.host = host
        self.temperature = temperature
        self.num_ctx = num_ctx

        # Verify service is reachable
        self._verify_service()

    def _verify_service(self):
        """Verify Ollama service is running."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"Ollama service not reachable at {self.host}: {e}"
            )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[dict[str, Any], float]:
        """
        Generate diagnosis using local Ollama model.

        Args:
            system_prompt: System instructions
            user_prompt: User query

        Returns:
            (parsed_json_response, duration_ms)

        Raises:
            ValueError: If JSON parsing fails
            RuntimeError: If API call fails
        """
        start_time = time.time()

        # Combine system + user into single prompt for Ollama
        full_prompt = f"{system_prompt}\n\n{user_prompt}\n\nReturn ONLY valid JSON."

        # Call Ollama API
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "format": "json",  # Request JSON mode
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=120,  # 2 minute timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama inference timeout after 120 seconds")
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {e}")

        duration_ms = (time.time() - start_time) * 1000

        # Parse response
        try:
            data = response.json()
            response_text = data.get("response", "")

            # Parse JSON from response
            parsed = json.loads(response_text)

            return parsed, duration_ms

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from model: {e}. Response: {response_text[:200]}")
        except Exception as e:
            raise RuntimeError(f"Error parsing Ollama response: {e}")

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()

            # Find our model
            for model in data.get("models", []):
                if model.get("name") == self.model:
                    return {
                        "name": model.get("name"),
                        "size_bytes": model.get("size"),
                        "size_gb": model.get("size", 0) / (1024**3),
                        "parameter_size": model.get("details", {}).get("parameter_size"),
                        "quantization": model.get("details", {}).get("quantization_level"),
                        "family": model.get("details", {}).get("family"),
                    }

            return {"name": self.model, "error": "Model not found in Ollama"}

        except Exception as e:
            return {"name": self.model, "error": str(e)}
