from __future__ import annotations

import unittest

from responses_api_transport import ResponsesStream, build_payload


class ResponsesPayloadTests(unittest.TestCase):
    def test_payload_preserves_roles_and_reasoning(self):
        messages = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "u2"},
        ]
        payload = build_payload(messages, "deepseek-v4-pro", 32768, "max")
        self.assertEqual(payload["input"], messages)
        self.assertEqual(payload["reasoning"], {"effort": "max"})
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["max_output_tokens"], 32768)

    def test_payload_rejects_unapproved_roles(self):
        with self.assertRaises(ValueError):
            build_payload([{"role": "developer", "content": "x"}], "deepseek-v4-pro", 10, "max")


class ResponsesStreamTests(unittest.TestCase):
    def completed_stream(self):
        stream = ResponsesStream()
        identity = {"id": "resp_1", "model": "deepseek-v4-pro"}
        stream.accept("response.created", {"type": "response.created", "sequence_number": 0,
                                             "response": {**identity, "status": "in_progress"}})
        stream.accept("response.output_text.delta", {"type": "response.output_text.delta", "sequence_number": 1,
                                                       "delta": "hello "})
        stream.accept("response.output_text.delta", {"type": "response.output_text.delta", "sequence_number": 2,
                                                       "delta": "world"})
        stream.accept("response.completed", {"type": "response.completed", "sequence_number": 3,
                                               "response": {**identity, "status": "completed", "output": [
                                                   {"type": "message", "role": "assistant", "content": [
                                                       {"type": "output_text", "text": "hello world"}]}], "usage": {
                                                   "input_tokens": 10,
                                                   "input_tokens_details": {"cached_tokens": 4},
                                                   "output_tokens": 8,
                                                   "output_tokens_details": {"reasoning_tokens": 5},
                                                   "total_tokens": 18,
                                               }}})
        return stream

    def test_completed_normalizes_for_existing_provider_accounting(self):
        body = self.completed_stream().normalized_chat_completion()
        self.assertEqual(body["choices"][0]["message"]["content"], "hello world")
        self.assertEqual(body["choices"][0]["finish_reason"], "stop")
        self.assertEqual(body["usage"]["prompt_cache_hit_tokens"], 4)
        self.assertEqual(body["usage"]["prompt_cache_miss_tokens"], 6)
        self.assertEqual(body["usage"]["completion_tokens_details"]["reasoning_tokens"], 5)

    def test_rejects_non_monotonic_sequence(self):
        stream = ResponsesStream()
        identity = {"id": "resp_1", "model": "deepseek-v4-pro"}
        stream.accept("response.created", {"type": "response.created", "sequence_number": 2,
                                             "response": {**identity, "status": "in_progress"}})
        with self.assertRaises(ValueError):
            stream.accept("response.in_progress", {"type": "response.in_progress", "sequence_number": 2,
                                                     "response": {**identity, "status": "in_progress"}})

    def test_rejects_identity_change(self):
        stream = ResponsesStream()
        stream.accept("response.created", {"type": "response.created", "sequence_number": 0,
                                             "response": {"id": "a", "model": "deepseek-v4-pro", "status": "in_progress"}})
        with self.assertRaises(ValueError):
            stream.accept("response.in_progress", {"type": "response.in_progress", "sequence_number": 1,
                                                     "response": {"id": "b", "model": "deepseek-v4-pro", "status": "in_progress"}})

    def test_failed_or_incomplete_is_terminal_but_not_accepted(self):
        for event, status in (("response.failed", "failed"), ("response.incomplete", "incomplete")):
            stream = ResponsesStream()
            stream.accept(event, {"type": event, "sequence_number": 0,
                                  "response": {"id": "r", "model": "deepseek-v4-pro", "status": status}})
            with self.assertRaises(ValueError):
                stream.normalized_chat_completion()

    def test_rejects_event_after_terminal(self):
        stream = self.completed_stream()
        with self.assertRaises(ValueError):
            stream.accept("response.output_text.delta", {"type": "response.output_text.delta", "sequence_number": 4,
                                                           "delta": "late"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
