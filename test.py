import os
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# 1. Create a custom OpenAIProvider instance configured with NVIDIA's client endpoints
nvidia_provider = OpenAIProvider(
    base_url="https://integrate.api.nvidia.com/v1",  # Core API URL for the NIM catalog
    api_key="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",
)

# 2. Initialize your model passing the provider instance directly into the context
nvidia_model = OpenAIChatModel(
    model_name="nvidia/nemotron-3.5-super-vl-120b-a12b",
    provider=nvidia_provider,
)

# 3. Inject it straight into your standard chat Agent
agent = Agent(
    model=nvidia_model,
    system_prompt="You are a brilliant clinical medical tourism advisor."
)

def run_chat():
    print("Chatting securely with NVIDIA NIM platform via PydanticAI provider schema...\n")
    result = agent.run_sync("What is immunotherapy?")
    print("Response:")
    print(result.output)

if __name__ == "__main__":
    run_chat()
