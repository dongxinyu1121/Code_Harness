"""模型提供方适配器共享的接口。"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Agent 运行时调用语言模型时使用的小型边界接口。"""

    @abstractmethod
    def complete(self, prompt, max_new_tokens):
        """返回模型针对已渲染提示词生成的文本响应。"""
        raise NotImplementedError
