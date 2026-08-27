import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_skill_frontmatter_and_directory_name():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    name = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE).group(1).strip()
    description = re.search(r"^description:\s*([^\n]+)$", frontmatter, re.MULTILINE).group(1).strip()
    assert name == ROOT.name == "novelty-audit"
    assert 1 <= len(description) <= 1024
    assert len(text.splitlines()) < 500


def test_every_skill_reference_exists():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    paths = re.findall(r"\]\((references/[^)]+)\)", text)
    assert paths
    assert all((ROOT / path).is_file() for path in paths)


def test_openai_interface_assets_and_prompt():
    text = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for field in ("icon_small", "icon_large"):
        value = re.search(rf'^\s*{field}:\s*"([^"]+)"$', text, re.MULTILINE).group(1)
        assert (ROOT / value).is_file()
    assert "$novelty-audit" in text

