"""测试使用的确定性模型提供方。"""


class FakeModelClient:
    """不发起网络调用，直接返回预配置响应。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def complete(self, prompt, max_new_tokens):
        self.prompts.append(prompt)
        if not self.outputs:
            raise RuntimeError("fake model ran out of outputs")
        return self.outputs.pop(0)
