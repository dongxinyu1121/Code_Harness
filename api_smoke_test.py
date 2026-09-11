"""使用 .env 中的 OpenAI 兼容配置发送一次最小请求。"""

import argparse
import json
import os
import socket
import urllib.error
import urllib.request

from cli.config import load_local_env


def responses_url(base_url):
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return base_url + "/responses"
    return base_url + "/v1/responses"


def output_text(data):
    if data.get("output_text") is not None:
        return str(data["output_text"])
    return "".join(
        part.get("text", "")
        for item in data.get("output", [])
        if isinstance(item, dict)
        for part in item.get("content", [])
        if isinstance(part, dict) and part.get("type") in {"output_text", "text"}
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Test the .env API configuration directly.")
    parser.add_argument("--prompt", default="Reply with OK.", help="Text sent to the model.")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
    args = parser.parse_args(argv)

    load_local_env()
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("LLM_MODEL", "")

    missing = [
        name
        for name, value in (
            ("OPENAI_BASE_URL", base_url),
            ("OPENAI_API_KEY", api_key),
            ("LLM_MODEL", model),
        )
        if not value
    ]
    if missing:
        print("Missing configuration: " + ", ".join(missing))
        return 2

    endpoint = responses_url(base_url)
    print("Effective configuration:")
    print(f"  endpoint: {endpoint}")
    print(f"  model: {model}")
    print(f"  api_key: present, suffix ...{api_key[-4:]}")
    print(f"  timeout: {args.timeout}s")
    print("Sending one request without Agent tools...")

    payload = {"model": model, "input": args.prompt}
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            print(f"HTTP status: {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP status: {exc.code}")
        print("Server error:")
        print(body)
        return 1
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        print(f"Request failed: {type(exc).__name__}: {exc}")
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Response was not JSON:")
        print(raw)
        return 1

    text = output_text(data)
    if text:
        print("Model output:")
        print(text)
    else:
        print("Response JSON:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
