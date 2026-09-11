"""从本地 skills 目录读取可用 Skill。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    """一个可注入 Agent prompt 的 Skill。"""

    name: str
    description: str
    content: str
    path: Path
    disable_model_invocation: bool = False


class SkillRegistry:
    """扫描并加载 ``skills/*/SKILL.md`` 文件。"""

    def __init__(self, root):
        self.root = Path(root)
        self._skills = self._load_skills()

    def list_skills(self):
        """按名称返回全部可用 Skill。"""
        return [self._skills[name] for name in sorted(self._skills)]

    def load_skill(self, name):
        """按名称加载一个 Skill。"""
        key = str(name).strip()
        if key not in self._skills:
            raise KeyError(key)
        return self._skills[key]

    def has_skill(self, name):
        """判断指定 Skill 是否存在。"""
        return str(name).strip() in self._skills

    def _load_skills(self):
        if not self.root.is_dir():
            return {}
        skills = {}
        for path in sorted(self.root.glob("*/SKILL.md")):
            skill = self._parse_skill(path)
            if skill.name:
                skills[skill.name] = skill
        return skills

    @staticmethod
    def _parse_skill(path):
        text = path.read_text(encoding="utf-8")
        metadata, content = _split_frontmatter(text)
        name = metadata.get("name") or path.parent.name
        return Skill(
            name=name,
            description=metadata.get("description", ""),
            content=content.strip(),
            path=path,
            disable_model_invocation=_as_bool(metadata.get("disable-model-invocation", "false")),
        )


def _split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text

    metadata = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, "\n".join(lines[end + 1 :])


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
