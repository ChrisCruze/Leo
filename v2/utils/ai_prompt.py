"""
AI Prompt Utility

This module provides reusable functions for interfacing with Claude AI API.
Scripts can use these functions instead of managing their own Anthropic clients.

PURPOSE:
--------
Reusable AI prompt utilities for Claude AI integration across the pipeline.
Handles API calls, JSON parsing, and quality checking workflows.

ENVIRONMENT REQUIREMENTS:
------------------------
- ANTHROPIC_API_KEY: Must be set in .env file at leo-dev root or as environment variable
- python-dotenv: Optional but recommended for .env file support (pip install python-dotenv)

MODEL DEFAULTS:
---------------
- Default model: "claude-sonnet-4-20250514"
- Default temperature: 0.7 (can be overridden)
- Default max_tokens: 4096 (can be overridden)

USAGE EXAMPLES:
--------------
See main() function at bottom for example usage patterns.

FUNCTIONS:
---------
- call_claude(): Calls Claude AI API and returns raw response text
- parse_json_response(): Parses JSON from Claude response text with fallbacks
- generate_with_quality_check(): Generates content and runs quality check
"""

import os
import json
import re
import logging
from pathlib import Path
from anthropic import Anthropic
from typing import Optional, Union, Dict, List

# Try to import dotenv, but make it optional
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Load .env file from leo-dev root directory
# This file is in utils/, so leo-dev root is 2 levels up
_script_dir = Path(__file__).parent
_leo_dev_root = _script_dir.parent
_env_file = _leo_dev_root / '.env'

if DOTENV_AVAILABLE and _env_file.exists():
    load_dotenv(_env_file)
elif DOTENV_AVAILABLE:
    # Fallback: try to load from current directory
    load_dotenv()


def call_claude(
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    logger: Optional[logging.Logger] = None
) -> str:
    """
    Call Claude AI API and return response text.
    
    Args:
        prompt: The prompt to send to Claude
        model: Claude model to use (default: "claude-sonnet-4-20250514")
        temperature: Creativity level 0-1 (default: 0.7)
        max_tokens: Maximum tokens in response (default: 4096)
        logger: Optional logger instance for logging prompts and responses
        
    Returns:
        Response text from Claude
        
    Raises:
        ValueError: If API key is not provided
        Exception: If API call fails
    """
    # Get API key from environment (loaded from .env file if available)
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        env_file_path = _env_file if _env_file.exists() else "leo-dev root"
        raise ValueError(
            f"ANTHROPIC_API_KEY not found. "
            f"Set it in .env file at {env_file_path} or as environment variable. "
            f"If using .env file, install python-dotenv: pip install python-dotenv"
        )
    
    # Log prompt if logger provided
    if logger:
        logger.info("=" * 80)
        logger.info("CLAUDE AI CALL")
        logger.info("=" * 80)
        logger.info(f"Model: {model}")
        logger.info(f"Temperature: {temperature}")
        logger.info(f"Max Tokens: {max_tokens}")
        logger.info("")
        logger.info("PROMPT:")
        logger.info("-" * 80)
        logger.info(prompt)
        logger.info("-" * 80)
    
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
    
    # Log response if logger provided
    if logger:
        logger.info("")
        logger.info("RESPONSE:")
        logger.info("-" * 80)
        logger.info(response_text)
        logger.info("-" * 80)
        logger.info("=" * 80)
        logger.info("")
    
    return response_text


def parse_json_response(
    response_text: str,
    logger: Optional[logging.Logger] = None
) -> Union[Dict, List]:
    """
    Parse JSON from Claude response text with multiple fallback strategies.
    
    Args:
        response_text: Response text from Claude
        logger: Optional logger instance for logging parsing attempts
        
    Returns:
        Parsed JSON object (dict or list)
        
    Raises:
        json.JSONDecodeError: If no valid JSON can be parsed
    """
    if logger:
        logger.debug("Parsing JSON from response...")
    
    # First, try to find JSON array (for arrays)
    array_match = re.search(r'\[[\s\S]*?\]', response_text, re.DOTALL)
    if array_match:
        json_str = array_match.group(0)
        try:
            parsed = json.loads(json_str)
            if logger:
                logger.debug("Successfully parsed JSON array")
            return parsed
        except json.JSONDecodeError:
            if logger:
                logger.debug("Failed to parse JSON array, trying object...")
    
    # Try to extract JSON object (non-greedy to get first complete object)
    json_match = re.search(r'\{[\s\S]*?\}', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            parsed = json.loads(json_str)
            if logger:
                logger.debug("Successfully parsed JSON object (non-greedy)")
            return parsed
        except json.JSONDecodeError:
            if logger:
                logger.debug("Failed to parse JSON object (non-greedy), trying balanced braces...")
    
    # If non-greedy didn't work, try to find the first complete JSON structure
    # by finding balanced braces/brackets
    def find_json_start(text, start_char='{'):
        """Find the start of a JSON structure with balanced braces/brackets"""
        if start_char == '{':
            end_char = '}'
        else:
            end_char = ']'
        
        start_idx = text.find(start_char)
        if start_idx == -1:
            return None
        
        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start_idx, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    return text[start_idx:i+1]
        
        return None
    
    # Try array first
    json_str = find_json_start(response_text, '[')
    if json_str:
        try:
            parsed = json.loads(json_str)
            if logger:
                logger.debug("Successfully parsed JSON array (balanced brackets)")
            return parsed
        except json.JSONDecodeError:
            if logger:
                logger.debug("Failed to parse JSON array (balanced brackets), trying object...")
    
    # Try object
    json_str = find_json_start(response_text, '{')
    if json_str:
        try:
            parsed = json.loads(json_str)
            if logger:
                logger.debug("Successfully parsed JSON object (balanced braces)")
            return parsed
        except json.JSONDecodeError:
            if logger:
                logger.debug("Failed to parse JSON object (balanced braces)")
    
    # If no JSON found, raise error with more context
    error_msg = f"Could not find valid JSON object or array in response. Response preview: {response_text[:500]}..."
    if logger:
        logger.error(error_msg)
    raise json.JSONDecodeError(error_msg, response_text, 0)


def generate_with_quality_check(
    initial_prompt: str,
    quality_check_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    logger: Optional[logging.Logger] = None
) -> Dict:
    """
    Generate content and run quality check on the result.
    
    Args:
        initial_prompt: First prompt to generate content
        quality_check_prompt: Prompt template to critique the initial response
                             Use {initial_response} placeholder for the generated content
        model: Claude model to use
        temperature: Creativity level 0-1
        max_tokens: Maximum tokens in response
        logger: Optional logger instance
        
    Returns:
        Dictionary containing:
        - 'initial_response': The original generated content (parsed JSON)
        - 'quality_check_response': The critique/quality check response (parsed JSON)
        - 'iterations': Number of iterations performed (always 1 for now)
    """
    if logger:
        logger.info("Generating initial response...")
    
    # Call Claude with initial prompt
    initial_response_text = call_claude(
        prompt=initial_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        logger=logger
    )
    
    # Parse initial response
    initial_response = parse_json_response(initial_response_text, logger)
    
    if logger:
        logger.info("Running quality check...")
    
    # Format quality_check_prompt by replacing {initial_response} placeholder
    # Convert initial_response to string for replacement
    initial_response_str = json.dumps(initial_response, indent=2) if isinstance(initial_response, (dict, list)) else str(initial_response)
    formatted_quality_prompt = quality_check_prompt.replace('{initial_response}', initial_response_str)
    
    # Call Claude with quality check prompt
    quality_check_response_text = call_claude(
        prompt=formatted_quality_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        logger=logger
    )
    
    # Parse quality check response
    quality_check_response = parse_json_response(quality_check_response_text, logger)
    
    # Return dictionary with both responses
    return {
        'initial_response': initial_response,
        'quality_check_response': quality_check_response,
        'iterations': 1
    }


def main():
    """
    Example usage of ai_prompt utility functions.
    
    This demonstrates how step5_match_message.py would use these functions.
    """
    import logging
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('ai_prompt_example')
    
    # Example 1: Simple call to Claude
    logger.info("Example 1: Simple call to Claude")
    logger.info("=" * 80)
    
    prompt = """Return a JSON object with:
{
  "greeting": "Hello",
  "number": 42
}"""
    
    try:
        response_text = call_claude(prompt, logger=logger)
        parsed = parse_json_response(response_text, logger)
        logger.info(f"Parsed response: {parsed}")
    except Exception as e:
        logger.error(f"Error: {e}")
    
    logger.info("")
    
    # Example 2: Call with custom temperature
    logger.info("Example 2: Call with custom temperature (more creative)")
    logger.info("=" * 80)
    
    creative_prompt = """Generate a funny one-liner about programming. Return as JSON:
{
  "joke": "your joke here"
}"""
    
    try:
        response_text = call_claude(
            creative_prompt,
            temperature=0.9,
            logger=logger
        )
        parsed = parse_json_response(response_text, logger)
        logger.info(f"Parsed response: {parsed}")
    except Exception as e:
        logger.error(f"Error: {e}")
    
    logger.info("")
    
    # Example 3: Quality check workflow
    logger.info("Example 3: Quality check workflow")
    logger.info("=" * 80)
    
    initial_prompt = """Write a short SMS message (under 100 chars) about a dinner event.
Return JSON:
{
  "message": "your message here"
}"""
    
    quality_check_prompt = """Review this SMS message and check if it:
1. Is under 100 characters
2. Is friendly and engaging
3. Has no typos

Message: {initial_response}

Return JSON:
{
  "approved": true/false,
  "issues": ["list of issues"],
  "improved_message": "improved version if needed"
}"""
    
    try:
        result = generate_with_quality_check(
            initial_prompt,
            quality_check_prompt,
            logger=logger
        )
        logger.info(f"Initial response: {result['initial_response']}")
        logger.info(f"Quality check: {result['quality_check_response']}")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()

