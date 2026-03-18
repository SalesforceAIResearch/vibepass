from dataclasses import dataclass
import requests
import os
from openai import OpenAI
from sympy import false
import time
from google import genai
from anthropic import AnthropicVertex
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import signal
from functools import wraps

@dataclass
class OpenAIGenerator:
    model: str = None
    effort: str = None
    stream: bool = False

    def __post_init__(self):
        # Use custom base URL if provided via environment, otherwise use OpenAI default
        base_url = os.environ.get('OPENAI_BASE_URL', None)
        api_key = os.environ.get('OPENAI_API_KEY', 'dummy')
        headers = {"X-Api-Key": os.environ['X_API_KEY']} if 'X_API_KEY' in os.environ else None

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
        )
        assert self.model.startswith('gpt-5'), f"Model {self.model} is not supported"
  
    def generate(self, user_content):
        response = self.client.responses.create(
            model=self.model,
            input=user_content,
            reasoning={
                "effort": self.effort
            },
            stream=self.stream
        )
        if self.stream:
            # Stream internally and return concatenated result
            full_response = ""
            for chunk in response:
                # Handle different event types in the streaming response
                if hasattr(chunk, 'type'):
                    if chunk.type == 'content.delta' and hasattr(chunk, 'delta'):
                        full_response += chunk.delta
                    elif chunk.type == 'response.output_item.done' and hasattr(chunk, 'item'):
                        # Final item with complete content
                        if hasattr(chunk.item, 'content') and chunk.item.content:
                            for content_block in chunk.item.content:
                                if hasattr(content_block, 'text'):
                                    full_response += content_block.text
                # Fallback: try common attributes
                elif hasattr(chunk, 'choices') and chunk.choices:
                    if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
            return full_response
        else:
            return response.output[-1].content[0].text

@dataclass
class GeminiGenerator:
    model: str = None
    stream: bool = False

    def __post_init__(self):
        # Use environment variable for project ID or default
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'your-project-id')
        location = os.environ.get('GOOGLE_CLOUD_LOCATION', 'global')
        self.client = genai.Client(vertexai=True, project=project_id, location=location)

    def generate(self, user_content, max_time_limit=3600):
        if self.stream:
            # Use streaming mode
            response = self.client.models.generate_content_stream(
                model=self.model,
                contents=user_content,
            )
            # Stream internally and return concatenated result
            full_response = ""
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    full_response += chunk.text
            return full_response
        else:
            # Non-streaming mode
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_content,
            )
            return response.text

@dataclass
class ClaudeGenerator:
    model: str = None
    location: str = "global"
    do_thinking: bool = False
    max_tokens: int = 32768
    stream: bool = False

    def __post_init__(self):
        if self.model == 'sonnet4.6':
            self.model_id = 'claude-sonnet-4-6'
        elif self.model == 'opus4.6':
            self.model_id = 'claude-opus-4-6'
        elif self.model == 'opus4.5':
            self.model_id = "claude-opus-4-5@20251101"
        elif self.model == 'sonnet4.5':
            self.model_id = "claude-sonnet-4-5@20250929"
        elif self.model == 'haiku4.5':
            self.model_id = "claude-haiku-4-5@20251001"
        elif self.model == 'opus4.1':
            self.model_id = "claude-opus-4-1@20250805"
        elif self.model == 'opus4':
            self.model_id = "claude-opus-4@20250514"
            self.location = "us-east5"
        elif self.model == 'sonnet4':
            self.model_id = "claude-sonnet-4@20250514"
        else:
            raise ValueError(f"Unknown model: {self.model}, supported models: opus4.5, sonnet4.5, haiku4.5, opus4.1, opus4, sonnet4")
        # Use environment variable for project ID
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'your-project-id')
        self.client = AnthropicVertex(region=self.location, project_id=project_id)

    def generate(self, user_content):
        kwargs = {
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": user_content}],
            "model": self.model_id,
            "stream": self.stream,
        }

        if self.do_thinking and '4.6' in self.model:
            print ("Thinking is enabled")
            kwargs["thinking"] = {"type": "adaptive"}
        elif self.do_thinking:
            print ("Thinking is enabled")
            kwargs["thinking"] = {"type": "enabled","budget_tokens": int(0.85*self.max_tokens)}

        response = self.client.messages.create(**kwargs)

        if self.stream:
            # Stream internally and return concatenated result
            full_response = ""
            for event in response:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta" and event.delta.text:
                        full_response += event.delta.text
                elif event.type == "content_block_start":
                    # Initialize content block if needed
                    pass
            return full_response
        else:
            # Extract text from response (handle both regular and extended thinking responses)
            # Extended thinking responses contain ThinkingBlock + TextBlock
            text_parts = []
            for block in response.content:
                if hasattr(block, 'text'):
                    text_parts.append(block.text)

            return '\n'.join(text_parts) if text_parts else response.content[0].text

@dataclass
class CustomGenerator:
    system_content: str = "You are a helpful assistant."
    port: int = None
    max_tokens: int = 16384
    effort: str = 'medium'

    def __post_init__(self):
        # Use environment variable for custom API port if not specified
        if self.port is None:
            self.port = int(os.environ.get('CUSTOM_API_PORT', '8000'))
        self.url = f"http://localhost:{self.port}/v1/chat/completions"
  
    def generate(self, user_content, max_time_limit=None):
        def _generate():
            headers = {"Content-Type": "application/json"}
            data = {
                "messages": [
                    {"role": "system", "content": self.system_content},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": self.max_tokens,
                "reasoning_effort": self.effort
            }
            timeout_val = max_time_limit if max_time_limit else None
            response = requests.post(self.url, headers=headers, json=data, timeout=timeout_val)
            return response.json()['choices'][0]['message']['content']

        return with_timeout(_generate, max_time_limit)

@dataclass
class TogetherAIGenerator:
    model: str = None
    x_api_key: str = os.environ['TOGETHER_API_KEY']
    effort: str = None
    model_id_dict = {
        "gpt-oss-20B": "OpenAI/gpt-oss-20B",
        "gpt-oss-120B": "openai/gpt-oss-120b",
        "glm-5": "zai-org/GLM-5",
    }

    def __post_init__(self):
        from together import Together
        self.client = Together(api_key=self.x_api_key)
        self.model_id = self.model_id_dict.get(self.model)
  
    def generate(self, user_content, max_retries=5):
        if self.model_id in ["openai/gpt-oss-120b", "OpenAI/gpt-oss-20B", "zai-org/GLM-5"]:
            for _ in range(max_retries):
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[
                        {"role": "user", "content": user_content}
                        ],
                        reasoning_effort=self.effort,
                    )
                if response.choices[0].message.content != '':
                    return response.choices[0].message.content
                time.sleep(30)
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unknown model: {self.model}")


def get_generator(model):
    if model.startswith('gemini'):
        return GeminiGenerator(model=model, stream=True)
    elif model.startswith('gpt-5'):
        if model.endswith('_low') or model.endswith('_medium') or model.endswith('_high') or model.endswith('_minimal'):
            return OpenAIGenerator(model=model.split('_')[0], effort=model.split('_')[1], stream=True)
        else:
            return OpenAIGenerator(model=model, effort='medium', stream=True)
    elif model.startswith('sonnet') or model.startswith('opus') or model.startswith('haiku'):
        # Parse thinking budget from model name if provided
        do_thinking = False
        base_model = model
        if '_' in model:
            parts = model.split('_')
            base_model = parts[0]
            do_thinking = parts[1].startswith('think')
        return ClaudeGenerator(max_tokens=128000, model=base_model, do_thinking=do_thinking, stream=True)
        # return ClaudeGenerator(max_tokens=65536, model=base_model, do_thinking=do_thinking)
    elif any(model.startswith(x) for x in ['deepseek', 'qwen', 'llama', 'mistral', 'glm']):
        return TogetherAIGenerator(model=model)
    elif model.startswith('gpt-oss'):
        return CustomGenerator(system_content="You are a helpful assistant.", port=8000, max_tokens=16384, effort=model.split('_')[1])
        # return TogetherAIGenerator(model=model.split('_')[0], effort=model.split('_')[1])
    else:
        raise ValueError(f"Invalid model: {model}")