import unittest

from backend.services.ai.base import AIMessage, DoneEvent, TextChunkEvent, ToolCall, ToolCallEvent
from backend.services.ai.providers import OpenAICompatibleAIProvider
from backend.services.ai.tools import ToolContext
from backend.services.analyzer.chat import AnalysisChatService


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[list[AIMessage]] = []

    async def stream_text_with_tools(self, messages, *, tools, temperature=0.2, max_tokens=1500):
        del tools, temperature, max_tokens
        self.calls.append(list(messages))

        if len(self.calls) == 1:
            yield TextChunkEvent(text="Buscando diff...")
            yield ToolCallEvent(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="get_file_diff",
                        arguments={"file_path": "backend/services/analyzer/prompts.py"},
                    )
                ]
            )
            yield DoneEvent()
            return

        yield TextChunkEvent(text="```diff\n")
        yield TextChunkEvent(text="+ cambio\n")
        yield TextChunkEvent(text="```")
        yield DoneEvent()


class _FakeFile:
    def __init__(self, path: str, patch: str) -> None:
        self.path = path
        self.patch = patch


class _FakeAnalysis:
    def __init__(self) -> None:
        self.files = [_FakeFile("backend/services/analyzer/prompts.py", "@@ -1 +1 @@\n-old\n+new")]
        self.checklist_items = []
        self.repo_full_name = "Carlos0550/mergeintel"
        self.pr_number = 1
        self.commits = []
        self.authors = []


class AnalysisChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_discards_partial_text_when_round_uses_tool(self) -> None:
        provider = _FakeProvider()
        service = AnalysisChatService(provider)  # type: ignore[arg-type]

        chunks = []
        async for chunk in service.stream_answer_with_tools(
            analysis_summary="summary",
            checklist_lines=[],
            file_lines=["- backend/services/analyzer/prompts.py (modified, +1/-1)"],
            history_lines=[],
            user_message="Dame el diff de backend/services/analyzer/prompts.py",
            tool_context=ToolContext(analysis=_FakeAnalysis()),
        ):
            chunks.append(chunk)

        self.assertEqual(chunks, ["```diff\n", "+ cambio\n", "```"])
        self.assertEqual(len(provider.calls), 2)

        second_round_messages = provider.calls[1]
        assistant_with_tool = next(msg for msg in second_round_messages if msg.role == "assistant" and msg.tool_calls)
        self.assertEqual(assistant_with_tool.content, "")
        self.assertEqual(assistant_with_tool.tool_calls[0].id, "call_1")

    def test_openai_message_builder_omits_content_for_tool_calls(self) -> None:
        messages = [
            AIMessage(
                role="assistant",
                content="texto parcial que no debe reenviarse",
                tool_calls=[ToolCall(id="call_1", name="get_file_diff", arguments={"file_path": "a.py"})],
            ),
            AIMessage(role="tool", content='{"file":"a.py","patch":"@@"}', tool_call_id="call_1"),
        ]

        payload = OpenAICompatibleAIProvider._build_openai_messages(messages)

        self.assertEqual(payload[0]["role"], "assistant")
        self.assertIsNone(payload[0]["content"])
        self.assertEqual(payload[0]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(payload[1]["role"], "tool")
        self.assertEqual(payload[1]["tool_call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
