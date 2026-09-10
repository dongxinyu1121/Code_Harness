"""Providers for OpenAI-compatible Responses and Chat Completions APIs."""

import json
import http.client
import socket
import time
import urllib.error
import urllib.request

from .base import BaseLLMProvider


class OpenAICompatibleProvider(BaseLLMProvider):
    """Call a provider exposing an OpenAI-compatible model endpoint."""

    def __init__(
        self,
        model,
        base_url,
        api_key,
        wire_api="chat_completions",
        tools=None,
        instructions=None,
        temperature=0.2,
        top_p=0.9,
        timeout=900,
    ):
        if not str(api_key or "").strip():
            raise ValueError("LLM_API_KEY or OPENAI_API_KEY is required")
        if not str(base_url or "").strip():
            raise ValueError("LLM_BASE_URL or OPENAI_BASE_URL is required")
        if not str(model or "").strip():
            raise ValueError("LLM_MODEL is required")
        if wire_api not in {"chat_completions", "responses"}:
            raise ValueError("LLM_WIRE_API must be 'chat_completions' or 'responses'")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.wire_api = wire_api
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout

        raw_tools = tools or []
        if wire_api == "chat_completions":
            self.tools = self._to_chat_tools(raw_tools)
        else:
            self.tools = raw_tools

        self.instructions = instructions

        # Responses API state
        self.previous_response_id = None
        self.pending_call_id = None
        self.pending_tool_output = None

        # Chat Completions state
        self.messages = []
        self.pending_tool_call_id = None
        self.pending_tool_result = None

    @staticmethod
    def _to_chat_tools(tools):
        """Convert Responses API flat tool format to Chat Completions nested format."""
        converted = []
        for tool in tools:
            if tool.get("type") != "function":
                continue
            fn = {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object"}),
            }
            if "strict" in tool:
                fn["strict"] = tool["strict"]
            converted.append({"type": "function", "function": fn})
        return converted

    def complete(self, prompt, max_new_tokens):
        if self.wire_api == "responses":
            return self._complete_responses(prompt, max_new_tokens)
        return self._complete_chat(prompt, max_new_tokens)

    # ------------------------------------------------------------------
    # Responses API path (unchanged behaviour)
    # ------------------------------------------------------------------

    def _complete_responses(self, prompt, max_new_tokens):
        endpoint = "/v1/responses"
        is_tool_follow_up = (
            self.previous_response_id is not None
            and self.pending_call_id is not None
            and self.pending_tool_output is not None
        )
        payload = {
            "model": self.model,
            "max_output_tokens": max_new_tokens,
        }
        if is_tool_follow_up:
            payload["previous_response_id"] = self.previous_response_id
            payload["input"] = [
                {
                    "type": "function_call_output",
                    "call_id": self.pending_call_id,
                    "output": self.pending_tool_output,
                }
            ]
        else:
            payload["input"] = str(prompt)
        if self.instructions:
            payload["instructions"] = self.instructions
        if self.tools:
            payload["tools"] = self.tools

        data = self._send(self.base_url + endpoint, payload)

        if data.get("error"):
            error = data["error"]
            message = error.get("message", error) if isinstance(error, dict) else error
            raise RuntimeError(f"LLM provider error: {message}")

        if is_tool_follow_up:
            self.pending_call_id = None
            self.pending_tool_output = None
        self.previous_response_id = data.get("id")

        for output in data.get("output", []):
            if not isinstance(output, dict) or output.get("type") != "function_call":
                continue
            try:
                arguments = json.loads(output.get("arguments", "{}"))
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("LLM function call contained invalid JSON arguments") from exc
            self.pending_call_id = output.get("call_id")
            return "<tool>" + json.dumps(
                {"name": output.get("name", ""), "args": arguments}
            ) + "</tool>"

        content = data.get("output_text")
        if content is None:
            content = "".join(
                item.get("text", "")
                for output in data.get("output", [])
                if isinstance(output, dict)
                for item in output.get("content", [])
                if isinstance(item, dict) and item.get("type") in {"output_text", "text"}
            )
        if content is None:
            raise RuntimeError("LLM response did not contain output_text")
        return str(content)

    # ------------------------------------------------------------------
    # Chat Completions path (with multi-turn tool support)
    # ------------------------------------------------------------------

    def _complete_chat(self, prompt, max_new_tokens):
        self._advance_chat(prompt)

        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": False,
            "max_tokens": max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.instructions:
            payload["messages"] = [
                {"role": "system", "content": self.instructions},
                *self.messages,
            ]
        if self.tools:
            payload["tools"] = self.tools
            payload["tool_choice"] = "auto"

        data = self._send(self.base_url + "/v1/chat/completions", payload)

        if data.get("error"):
            error = data["error"]
            message = error.get("message", error) if isinstance(error, dict) else error
            raise RuntimeError(f"LLM provider error: {message}")

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response did not contain choices[0].message") from exc

        # Append the raw assistant message to history so future turns include it.
        self.messages.append(message)

        tool_calls = message.get("tool_calls")
        if tool_calls:
            tc = tool_calls[0]
            self.pending_tool_call_id = tc.get("id")
            try:
                arguments = json.loads(tc["function"].get("arguments", "{}"))
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("LLM function call contained invalid JSON arguments") from exc
            return "<tool>" + json.dumps(
                {"name": tc["function"].get("name", ""), "args": arguments}
            ) + "</tool>"

        # No tool call — clear any stale pending state.
        self.pending_tool_call_id = None
        self.pending_tool_result = None

        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        return str(content or "")

    def _advance_chat(self, prompt):
        """Append a tool result or start a new turn."""
        if self.pending_tool_call_id and self.pending_tool_result is not None:
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": self.pending_tool_call_id,
                    "content": self.pending_tool_result,
                }
            )
            self.pending_tool_call_id = None
            self.pending_tool_result = None
        else:
            self.messages = [{"role": "user", "content": str(prompt)}]

    # ------------------------------------------------------------------
    # Shared HTTP helper
    # ------------------------------------------------------------------

    def _send(self, url, payload):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
                time.sleep(min(2**attempt, 8))
            except (urllib.error.URLError, http.client.RemoteDisconnected, TimeoutError, socket.timeout) as exc:
                if attempt == 2:
                    if isinstance(exc, urllib.error.URLError):
                        raise RuntimeError(
                            "Could not reach the configured LLM provider.\n"
                            f"Base URL: {self.base_url}\n"
                            f"Model: {self.model}"
                        ) from exc
                    raise RuntimeError(
                        "The LLM provider closed or timed out the connection.\n"
                        f"Base URL: {self.base_url}\n"
                        f"Model: {self.model}"
                    ) from exc
                time.sleep(min(2**attempt, 8))

    # ------------------------------------------------------------------
    # Tool result submission (called by the agent loop after each tool run)
    # ------------------------------------------------------------------

    def submit_tool_result(self, result):
        """Queue a local tool result for the next request."""
        if self.wire_api == "responses":
            self.pending_tool_output = str(result)
        else:
            if self.pending_tool_call_id:
                self.pending_tool_result = str(result)
