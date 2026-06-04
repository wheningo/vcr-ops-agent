"""Agent 注册表单元测试"""

import pytest

from vcr_ops_agent.agents.base import AgentRegistry, BaseAgent
from vcr_ops_agent.state import OpsState


class DummyAgent(BaseAgent):
    name = "dummy"
    domain = "test"

    async def run(self, state: OpsState, **kwargs):
        return {"next": "end"}


@pytest.fixture(autouse=True)
def clean_registry():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


def test_register_and_get():
    agent = DummyAgent()
    AgentRegistry.register(agent)
    assert AgentRegistry.get("dummy") is agent


def test_list_by_domain():
    agent = DummyAgent()
    AgentRegistry.register(agent)
    assert "dummy" in AgentRegistry.list_by_domain("test")
    assert AgentRegistry.list_by_domain("nonexistent") == []