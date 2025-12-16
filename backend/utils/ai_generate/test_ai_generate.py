#!/usr/bin/env python3
"""Test script for AI generate utilities"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_module_imports():
    """Test that the ai_generate module can be imported"""
    try:
        from utils.ai_generate import ai_generate_meta_tag_parse, ai_generate_with_quality_check
        print("✓ Module imports successful")
        return True
    except ImportError as e:
        print(f"✗ Module import failed: {e}")
        return False

def test_function_signatures():
    """Test that functions have correct signatures"""
    from utils.ai_generate import ai_generate_meta_tag_parse, ai_generate_with_quality_check
    import inspect

    # Check ai_generate_meta_tag_parse signature
    sig1 = inspect.signature(ai_generate_meta_tag_parse)
    params1 = list(sig1.parameters.keys())
    expected_params1 = ['prompt', 'model', 'max_tokens', 'temperature', 'api_key']
    assert params1 == expected_params1, f"Expected {expected_params1}, got {params1}"
    print("✓ ai_generate_meta_tag_parse has correct signature")

    # Check ai_generate_with_quality_check signature
    sig2 = inspect.signature(ai_generate_with_quality_check)
    params2 = list(sig2.parameters.keys())
    expected_params2 = ['initial_prompt', 'quality_check_prompt', 'model', 'max_tokens',
                        'temperature', 'api_key', 'max_iterations']
    assert params2 == expected_params2, f"Expected {expected_params2}, got {params2}"
    print("✓ ai_generate_with_quality_check has correct signature")

    return True

def test_basic_generation():
    """Test basic AI generation with JSON parsing (requires API key)"""
    # Check if API key is available
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("⊘ Skipping live API test (ANTHROPIC_API_KEY not set)")
        print("  To run live tests, set ANTHROPIC_API_KEY environment variable")
        return True

    from utils.ai_generate import ai_generate_meta_tag_parse

    prompt = """Return a JSON object with:
    - name: "Test User"
    - email: "test@example.com"
    - age: 25

    Return only the JSON object."""

    try:
        result = ai_generate_meta_tag_parse(prompt, api_key=api_key)
        print("Basic generation result:", result)
        assert isinstance(result, dict), "Result should be a dictionary"
        assert result.get('name') == 'Test User', "Name should be 'Test User'"
        print("✓ Basic generation test passed")
        return True
    except Exception as e:
        print(f"✗ Basic generation test failed: {e}")
        return False

def test_quality_check():
    """Test quality check functionality (requires API key)"""
    # Check if API key is available
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("⊘ Skipping quality check test (ANTHROPIC_API_KEY not set)")
        return True

    from utils.ai_generate import ai_generate_with_quality_check

    initial_prompt = """Write a short welcome message for a new user joining a social dining app."""

    quality_check_prompt = """Review this welcome message and provide feedback:

{initial_response}

Return a JSON object with:
- score: number 1-10
- feedback: string with improvement suggestions
- approved: boolean
"""

    try:
        result = ai_generate_with_quality_check(
            initial_prompt=initial_prompt,
            quality_check_prompt=quality_check_prompt,
            api_key=api_key
        )

        print("Quality check result:", result)
        assert 'initial_response' in result, "Result should contain 'initial_response'"
        assert 'quality_check_response' in result, "Result should contain 'quality_check_response'"
        print("✓ Quality check test passed")
        return True
    except Exception as e:
        print(f"✗ Quality check test failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Testing AI Generate Utilities")
    print("=" * 60)

    all_passed = True

    # Run tests
    all_passed &= test_module_imports()
    all_passed &= test_function_signatures()
    all_passed &= test_basic_generation()
    all_passed &= test_quality_check()

    print("=" * 60)
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")
        sys.exit(1)
    print("=" * 60)
