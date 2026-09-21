"""Offline adapter using the same strict parser as the formal runtime."""
from __future__ import annotations
import json
import sys
from pathlib import Path
CODE = Path(__file__).resolve().parents[3] / 'persona_core/operational_runtime_v1'
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
from provider_transport import ResponsesAssembly, Lifecycle, encode
TERMINAL_EVENTS = ResponsesAssembly.TERMINALS


def build_payload(messages: list[dict], model: str, max_output_tokens: int, reasoning_effort: str) -> dict:
    if not isinstance(messages, list) or not messages or any(
            not isinstance(message, dict) or set(message) != {'role', 'content'} for message in messages):
        raise ValueError('invalid message shape')
    if any(message['role'] not in {'system', 'user', 'assistant'} or not isinstance(message['content'], str)
           for message in messages):
        raise ValueError('invalid message role/content')
    if reasoning_effort != 'max':
        raise ValueError('Responses scope requires max reasoning')
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 131072:
        raise ValueError('invalid output bound')
    return {'model': model, 'input': messages, 'reasoning': {'effort': reasoning_effort},
            'max_output_tokens': max_output_tokens, 'stream': True}


class ResponsesStream:
    def __init__(self):
        self.assembly = ResponsesAssembly(Lifecycle())

    def accept(self, event_type: str, payload: dict) -> None:
        self.assembly.record(event_type, encode(payload))

    def normalized_chat_completion(self) -> dict:
        if self.assembly.terminal != 'response.completed':
            raise ValueError('response is not completed')
        return json.loads(self.assembly.body())
