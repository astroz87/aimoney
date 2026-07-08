"""후킹 컷 기반 대본 생성.

문장 단위 Scene JSON 을 생성한다. Mock(규칙 기반) 과 LLM(주입) 두 경로.
"""

from .base import ScriptGenerator, SCRIPT_RULES
from .mock_generator import MockScriptGenerator
from .llm_generator import LLMScriptGenerator

__all__ = ["ScriptGenerator", "SCRIPT_RULES", "MockScriptGenerator", "LLMScriptGenerator"]
