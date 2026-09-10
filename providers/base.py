"""Interfaces shared by model provider adapters."""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Small seam used by the agent runtime to call a language model."""

    @abstractmethod
    def complete(self, prompt, max_new_tokens):
        """Return the model's text response for a rendered prompt."""
        raise NotImplementedError
