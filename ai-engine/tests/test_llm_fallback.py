import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import llm as llm_module


def test_extract_json_plain():
    text = '{"a": 1, "b": "two"}'
    assert llm_module._extract_json(text) == {"a": 1, "b": "two"}


def test_extract_json_with_markdown_fences():
    text = '```json\n{"a": 1}\n```'
    assert llm_module._extract_json(text) == {"a": 1}


def test_extract_json_with_leading_commentary():
    text = 'Here is the JSON you asked for:\n{"a": 1}'
    assert llm_module._extract_json(text) == {"a": 1}


def test_extract_json_with_trailing_commentary():
    text = '{"a": 1}\nLet me know if you need anything else!'
    assert llm_module._extract_json(text) == {"a": 1}


def test_extract_json_with_both_leading_and_trailing_commentary():
    text = 'Sure, here you go:\n{"a": 1, "nested": {"b": 2}}\nHope that helps!'
    assert llm_module._extract_json(text) == {"a": 1, "nested": {"b": 2}}


def test_extract_json_invalid_raises():
    with pytest.raises(Exception):
        llm_module._extract_json("not json at all")


def test_llm_not_configured_raises_unavailable():
    original = llm_module.LLM_API_KEY
    llm_module.LLM_API_KEY = ""
    try:
        with pytest.raises(llm_module.LLMUnavailableError):
            llm_module._call_anthropic("system", "user")
    finally:
        llm_module.LLM_API_KEY = original
