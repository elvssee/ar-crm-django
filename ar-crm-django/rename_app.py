"""Renames the app in every template. Safe to run as many times as you like."""
from pathlib import Path

NAME = "archdo."  # the brand is written lowercase with a full stop

OLD_NAMES = ["Architecture CRM", "ArchDo", "Arch Do"]

templates = Path(__file__).resolve().parent / "templates"
changed = 0
for path in templates.rglob("*.html"):
    text = path.read_text(encoding="utf-8")
    new = text
    for old in OLD_NAMES:
        new = new.replace(old.upper(), NAME.lower()).replace(old, NAME)
    if new != text:
        path.write_text(new, encoding="utf-8", newline="")
        changed += 1
        print("updated", path.relative_to(templates))
print(f"Done: {changed} file(s) changed.")