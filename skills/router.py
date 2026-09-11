"""根据用户请求保守选择 Skill。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSelection:
    """一次自动路由的选择结果。"""

    name: str
    confidence: int


class SkillRouter:
    """用关键词做低成本、高置信度的 Skill 路由。"""

    def __init__(self, threshold=2):
        self.threshold = threshold

    def choose(self, user_message, skills):
        """高置信度时返回 Skill 名称，否则返回 ``None``。"""
        available = {skill.name: skill for skill in skills}
        if not available:
            return None

        text = str(user_message).lower()
        best = None
        for name in sorted(available):
            score = self._score(name, available[name].description, text)
            if score < self.threshold:
                continue
            if best is None or score > best.confidence:
                best = SkillSelection(name=name, confidence=score)
        return best

    def _score(self, name, description, text):
        haystack = f"{name} {description}".lower()
        score = 0
        if name.lower() in text:
            score += 3
        if "skill" in text or "技能" in text:
            score += 1
        if name == "ask-matt" and any(word in text for word in ("用哪个", "哪一个", "适合", "推荐", "怎么做", "流程", "route")):
            score += 2
        if name == "diagnosing-bugs" and any(word in text for word in ("报错", "失败", "bug", "traceback", "debug", "broken")):
            score += 3
        if name == "tdd" and any(word in text for word in ("tdd", "测试驱动", "先写测试", "pytest")):
            score += 3
        if name == "code-review" and any(word in text for word in ("review", "代码审查", "检查代码", "pr")):
            score += 3
        if name == "codebase-design" and any(word in text for word in ("架构", "模块", "接口", "重构", "设计")):
            score += 3
        if score and any(token in haystack for token in text.split()):
            score += 1
        return score
