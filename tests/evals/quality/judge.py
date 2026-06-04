"""LLM-as-Judge — 根因质量评估

用强模型 (Opus) + 温度 0 评判 Agent 根因输出。
"""

import os
from typing import Literal

from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic


class JudgeVerdict(BaseModel):
    verdict: Literal["correct", "partial", "wrong"] = "wrong"
    score: float = Field(ge=0, le=1, default=0.0)
    reason: str = ""


_SYS = (
    "你是严格的运营根因评审。只按根因的【本质类别】和证据是否合理判分，"
    "不要因措辞不同而扣分。\n\n"
    "评分标准：\n"
    "- correct (1.0): 命中根因类别且证据合理\n"
    "- partial (0.5): 方向对但不全/证据弱\n"
    "- wrong (0.0): 方向错"
)


def _judge():
    model = os.getenv("VCR_OPS_JUDGE_MODEL", "claude-opus-4.6")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "") or None
    return ChatAnthropic(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        max_tokens=512,
    ).with_structured_output(JudgeVerdict)


async def judge_root_cause(
    description: str,
    expected_category: str,
    agent_root_cause: str,
) -> JudgeVerdict:
    user_prompt = (
        f"场景: {description}\n"
        f"预期根因类别: {expected_category}\n"
        f"Agent 根因: {agent_root_cause}\n\n"
        "命中类别且证据合理→correct(1.0)；方向对但不全/证据弱→partial(0.5)；方向错→wrong(0.0)。"
    )
    return await _judge().ainvoke([
        {"role": "system", "content": _SYS},
        {"role": "user", "content": user_prompt},
    ])