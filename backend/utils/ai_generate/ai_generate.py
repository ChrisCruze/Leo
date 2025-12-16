#!/usr/bin/env python3
"""
AI Generate Utility

This module provides centralized functions for interfacing with Claude AI API.
Scripts can use these functions instead of managing their own Anthropic clients.
"""

import os
import json
import re
from anthropic import Anthropic
from typing import Optional, Union, Dict, List


def ai_generate_meta_tag_parse(
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    api_key: Optional[str] = None
) -> Union[Dict, List]:
    """
    Generate content from Claude and parse response from XML/JSON tags.

    Args:
        prompt: The prompt to send to Claude
        model: Claude model to use (default: claude-sonnet-4-20250514)
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Creativity level 0-1 (default: 0.7)
        api_key: Optional API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Parsed object/dict from the LLM response

    Raises:
        ValueError: If API key is not provided
        json.JSONDecodeError: If response cannot be parsed
    """
    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv('ANTHROPIC_API_KEY')

    if not api_key:
        raise ValueError("API key not provided. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

    # Initialize Anthropic client
    client = Anthropic(api_key=api_key)

    # Call messages.create() with the prompt
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    # Extract response text
    response_text = response.content[0].text

    # Parse JSON using regex patterns
    # Try to extract JSON object first
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        json_str = json_match.group(0)
        return json.loads(json_str)

    # Try to extract JSON array
    array_match = re.search(r'\[[\s\S]*\]', response_text)
    if array_match:
        json_str = array_match.group(0)
        return json.loads(json_str)

    # If no JSON found, raise error
    raise json.JSONDecodeError(
        f"Could not find JSON object or array in response: {response_text[:200]}...",
        response_text,
        0
    )


def ai_generate_with_quality_check(
    initial_prompt: str,
    quality_check_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    max_iterations: int = 1
) -> Dict:
    """
    Generate content and run quality check on the result.

    Args:
        initial_prompt: First prompt to generate content
        quality_check_prompt: Prompt template to critique the initial response
                             Use {initial_response} placeholder for the generated content
        model: Claude model to use
        max_tokens: Maximum tokens in response
        temperature: Creativity level 0-1
        api_key: Optional API key
        max_iterations: Number of quality check iterations (default: 1)

    Returns:
        Dictionary containing:
        - 'initial_response': The original generated content
        - 'quality_check_response': The critique/quality check response
        - 'iterations': Number of iterations performed
    """
    # Call ai_generate_meta_tag_parse() with initial_prompt
    initial_response = ai_generate_meta_tag_parse(
        prompt=initial_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        api_key=api_key
    )

    # Format quality_check_prompt by replacing {initial_response} placeholder
    # Convert initial_response to string for replacement
    initial_response_str = json.dumps(initial_response, indent=2) if isinstance(initial_response, (dict, list)) else str(initial_response)
    formatted_quality_prompt = quality_check_prompt.replace('{initial_response}', initial_response_str)

    # Call ai_generate_meta_tag_parse() with the quality check prompt
    quality_check_response = ai_generate_meta_tag_parse(
        prompt=formatted_quality_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        api_key=api_key
    )

    # Return dictionary with both responses
    return {
        'initial_response': initial_response,
        'quality_check_response': quality_check_response,
        'iterations': max_iterations
    }
