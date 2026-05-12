from anthropic import Anthropic
import time
import os
from config import CLAUDE_API_KEY, CLAUDE_MODEL

# Initialize Anthropic client
client = Anthropic(api_key=CLAUDE_API_KEY)

def get_claude_response(system_prompt, messages, max_tokens=300, temperature=1.0
):
    """Get a response from the Claude API"""
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages
        )

        if hasattr(response, 'content') and len(response.content) > 0 and hasattr(response.content[0], 'text'):
            message_content = response.content[0].text
            print(f"Got Claude response: {message_content[:50]}...")  # Log first 50 chars for debugging
            return message_content
        else:
            print(f"Claude API response structure issue: {response}")
            return ""
    except Exception as e:
        print(f"Claude API Error: {str(e)}")
        return ""
