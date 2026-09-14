from app.duplex.voice.agent_adapter import AgentRegistry, DirectLLMAdapter


class FakeAdapter:
    agent_id = "agent-x"
    engine_code = "fake"

    def __init__(self):
        self.calls = []

    async def run_voice_turn(self, audio_b64=None, text=None, history=None, tools=None):
        self.calls.append(text)
        return {"text": text}

    async def call_tool(self, name, args):
        return {"name": name}


def test_registry_register_get():
    a = FakeAdapter()
    AgentRegistry.register(a)
    assert AgentRegistry.get("agent-x") is a
    assert AgentRegistry.exists("agent-x")


def test_direct_llm_adapter_echo():
    import asyncio
    out = asyncio.run(DirectLLMAdapter("a").run_voice_turn(text="hi"))
    assert out["text"] == "[echo] hi"
