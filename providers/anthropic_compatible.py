"""Anthropic Messages 兼容端点的模型提供方适配器。"""

import http.client
import json
import socket
import time
import urllib.error
import urllib.request

from .base import BaseLLMProvider


class AnthropicCompatibleProvider(BaseLLMProvider):
    """调用 Anthropic 兼容的 ``/v1/messages`` 端点。"""

    def __init__(
        self,
        model,
        base_url,
        api_key,
        tools=None,
        instructions=None,
        timeout=900,
    ):
        if not str(api_key or "").strip():
            raise ValueError("ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY is required")
        if not str(base_url or "").strip():
            raise ValueError("ANTHROPIC_BASE_URL is required")
        if not str(model or "").strip():
            raise ValueError("ANTHROPIC_MODEL or LLM_MODEL is required")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tools = self._convert_tools(tools or [])
        self.instructions = instructions
        self.timeout = timeout
        self.messages = []
        self.pending_assistant_content = None
        self.pending_tool_use_id = None
        self.pending_tool_result = None

    @staticmethod
    def _convert_tools(tools):
        """将 OpenAI 函数定义转换为 Anthropic 工具结构。"""
        converted = []
        for tool in tools:
            if tool.get("type") != "function":
                continue
            converted.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {"type": "object"}),
                }
            )
        return converted

    def complete(self, prompt, max_new_tokens):
        self._advance_conversation(prompt)
        payload = {
            "model": self.model,
            "max_tokens": max_new_tokens,
            "messages": self.messages,
        }
        if self.instructions:
            payload["system"] = self.instructions
        if self.tools:
            payload["tools"] = self.tools

        request = urllib.request.Request(
            self.base_url + "/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        data = self._send(request)
        content = data.get("content")
        if not isinstance(content, list):
            raise RuntimeError("Anthropic response did not contain content blocks")

        self.pending_assistant_content = content
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            self.pending_tool_use_id = block.get("id")
            return "<tool>" + json.dumps(
                {"name": block.get("name", ""), "args": block.get("input", {})}
            ) + "</tool>"

        self._clear_pending_tool_state()
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    def submit_tool_result(self, result):
        """将结果排队为用户侧的 ``tool_result`` 内容块。"""
        if not self.pending_tool_use_id:
            return
        self.pending_tool_result = str(result)

    def _advance_conversation(self, prompt):
        if self.pending_assistant_content is None:
            self.messages = [{"role": "user", "content": str(prompt)}]
            return
        if self.pending_tool_result is None or not self.pending_tool_use_id:
            self._clear_pending_tool_state()
            self.messages = [{"role": "user", "content": str(prompt)}]
            return
        self.messages.append({"role": "assistant", "content": self.pending_assistant_content})
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": self.pending_tool_use_id,
                        "content": self.pending_tool_result,
                    }
                ],
            }
        )
        self._clear_pending_tool_state()

    def _clear_pending_tool_state(self):
        self.pending_assistant_content = None
        self.pending_tool_use_id = None
        self.pending_tool_result = None

    def _send(self, request):
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f"Anthropic request failed with HTTP {exc.code}: {body}") from exc
                time.sleep(min(2**attempt, 8))
            except (urllib.error.URLError, http.client.RemoteDisconnected, TimeoutError, socket.timeout) as exc:
                if attempt == 2:
                    raise RuntimeError(
                        "Could not reach the configured Anthropic provider.\n"
                        f"Base URL: {self.base_url}\n"
                        f"Model: {self.model}"
                    ) from exc
                time.sleep(min(2**attempt, 8))
