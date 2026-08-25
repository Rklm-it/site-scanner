#!/usr/bin/env python3
"""Собирает скилы в архивы для загрузки в аккаунт claude.ai.

Desktop и Cowork не читают ни `~/.claude/skills/` на машине, ни `.claude/`
в репозитории: они берут скилы, включённые в аккаунте. Поэтому единственный
способ получить их в Desktop — загрузить архивы руками один раз.

    python3 tools/package_skills.py           # четыре основных
    python3 tools/package_skills.py --all     # все
    python3 tools/package_skills.py seo       # выборочно

Архивы лягут в out/skills/ (каталог в .gitignore).
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
OUT = ROOT / "out" / "skills"

# Порядок работы: придумать → сделать → проверить, и сверху наш цикл.
CORE = ["lovable-site", "frontend-design", "web-design-engineer", "web-quality-audit"]

# Claude.ai принимает только эти ключи во фронт-маттере; остальные — отказ при
# загрузке, причём сообщение приходит уже после выбора файла.
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata",
                "allowed-tools", "disallowed-tools"}
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git"}
EXCLUDE_NAMES = {".DS_Store"}


def frontmatter_keys(skill_md: Path) -> list[str]:
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return []
    return [m.group(1) for m in re.finditer(r"^([A-Za-z-]+):", match.group(1), re.M)]


def siblings(name: str) -> set[str]:
    """Соседние скилы, на которые ссылается этот.

    В архив попадает только своя папка, поэтому ссылка `../seo/SKILL.md`
    в аккаунте повиснет: скил загрузится и будет работать, но без той части,
    ради которой соседа и писали.
    """
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    return {m.group(1) for m in re.finditer(r"\.\./([a-z0-9-]+)/", text)}


def pack(name: str) -> Path | None:
    src = SKILLS / name
    skill_md = src / "SKILL.md"
    if not skill_md.is_file():
        print(f"  ! {name}: нет SKILL.md, пропускаю")
        return None

    unknown = set(frontmatter_keys(skill_md)) - ALLOWED_KEYS
    if unknown:
        # Не отказываем: скил всё равно нужен, но загрузка споткнётся молча.
        print(f"  ! {name}: claude.ai не примет ключи {sorted(unknown)} — убрать перед загрузкой")

    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / f"{name}.zip"
    count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src.parent)
            if set(rel.parts) & EXCLUDE_DIRS or rel.name in EXCLUDE_NAMES:
                continue
            zf.write(path, rel)  # внутри архива — папка с именем скила
            count += 1
    print(f"  {archive.relative_to(ROOT)}  ({count} файлов, {archive.stat().st_size // 1024} КБ)")
    return archive


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--all"]
    if "--all" in sys.argv:
        names = sorted(p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())
    else:
        names = args or CORE

    print(f"Собираю в {OUT.relative_to(ROOT)}:")
    made = [pack(n) for n in names]
    made = [m for m in made if m]
    if not made:
        print("Нечего собирать.")
        return 1

    chosen = set(names)
    for name in names:
        missing = sorted(s for s in siblings(name) if (SKILLS / s / "SKILL.md").is_file()
                         and s not in chosen)
        if missing:
            print(f"\n  ! {name} ссылается на {', '.join(missing)} — их нет в этой сборке.")
            print(f"    Загрузить и их, либо помнить, что проверка выйдет мельче:")
            print(f"    python3 tools/package_skills.py {' '.join([name] + missing)}")

    print(f"""
Готово: {len(made)} шт. Дальше руками, один раз:

  1. В Claude Desktop — «Customize» в боковой панели (или настройки скилов
     на claude.ai) → добавить скил → выбрать архив.
  2. Включить каждый загруженный скил.

После этого они есть в любой сессии Desktop и Cowork, на любом репозитории —
настройки машины и файлы в репозитории для этого не нужны.

Обновили скил здесь — пересобрать и загрузить заново: аккаунт не следит за
репозиторием.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
