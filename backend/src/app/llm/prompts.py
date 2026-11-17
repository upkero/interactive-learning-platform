"""Prompt texts used by the llm package.

Rule: prompt strings live here and nowhere else — services receive ready
prompts or reference these constants. Prompt language is English.
"""

SCHEMA_RETRY_PROMPT = "The previous reply failed schema validation: {error}. Return only the corrected JSON."
