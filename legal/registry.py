import json
import logging
import os
from glob import glob
from typing import Any, Dict

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LegalSkillRegistry:
    def __init__(self, base_path: str, registry_file: str = "skill_registry.json"):
        self.base_path = base_path
        self.registry_file = os.path.join(base_path, registry_file)
        self.registry: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_file):
            with open(self.registry_file, "r", encoding="utf-8") as f:
                self.registry = json.load(f)
        return self.registry

    def save(self) -> None:
        os.makedirs(self.base_path, exist_ok=True)
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)
        logger.info("Registry saved to %s", self.registry_file)

    def build_from_filesystem(self) -> None:
        """Scan base_path for SKILL.md files and build the registry."""
        search_pattern = os.path.join(self.base_path, "**", "SKILL.md")
        skill_files = glob(search_pattern, recursive=True)

        self.registry = {}
        for file_path in skill_files:
            self._add_skill_from_file(file_path)

        self.save()
        logger.info("Built registry with %d skills.", len(self.registry))

    def _add_skill_from_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                return

            end_idx = content.find("---", 3)
            if end_idx == -1:
                return

            fm_text = content[3:end_idx].strip()
            fm = yaml.safe_load(fm_text)
            if not fm or "name" not in fm:
                return

            skill_id = fm.get("name")
            self.registry[skill_id] = {
                "name": skill_id,
                "category": fm.get("category", "未知"),
                "description": fm.get("description", ""),
                "tags": fm.get("tags", []),
                "file_path": os.path.relpath(file_path, self.base_path),
            }
        except Exception as e:
            logger.error("Failed to parse skill at %s: %s", file_path, e)

    def add_or_update_skill(self, fm: Dict, file_path: str) -> None:
        skill_id = fm.get("name")
        self.registry[skill_id] = {
            "name": skill_id,
            "category": fm.get("category", "未知"),
            "description": fm.get("description", ""),
            "tags": fm.get("tags", []),
            "file_path": os.path.relpath(file_path, self.base_path),
        }
        self.save()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build legal skill registry from SKILL.md files")
    parser.add_argument("--base", type=str, default="./LegalSkill", help="Skill library base directory")
    parser.add_argument("--registry-file", type=str, default="skill_registry.json", help="Registry output filename")
    args = parser.parse_args()

    registry = LegalSkillRegistry(base_path=args.base, registry_file=args.registry_file)
    registry.build_from_filesystem()


if __name__ == "__main__":
    main()
