import asyncio
import json
import logging
import os
import re
import shutil
from collections import defaultdict
from typing import Dict, List, Tuple

from clustering.dbscan import DBSCANClusterer
from clustering.embedding import EmbeddingService
from .registry import LegalSkillRegistry

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MERGE_PROMPT = """You are an elite Legal Knowledge Expert.
I will provide you with a list of highly similar legal skills that were extracted separately.
Your task is to MERGE them into ONE single, comprehensive, and exhaustive legal skill.
Do not omit any important nuances, conditions, or legal bases from the original skills.
Integrate their workflows into a unified, logical, deductive process (using Markdown branching).

Output EXACTLY one JSON object:
{
  "yaml_frontmatter": {"name": "...", "description": "...", "tags": ["..."], "triggers": ["..."], "category": "L1 -> L2"},
  "objectives_and_background": "...",
  "workflow_steps": "...",
  "legal_basis": ["..."],
  "example": "...",
  "tools": []
}
"""


class LegalSkillMerger:
    def __init__(
        self,
        llm,
        base_path: str,
        embedding_service: EmbeddingService,
        clusterer: DBSCANClusterer,
    ):
        self.llm = llm
        self.base_path = base_path
        self.registry_manager = LegalSkillRegistry(base_path)
        self.registry_manager.load()
        self.embedding_service = embedding_service
        self.clusterer = clusterer

    def identify_merge_candidates(self) -> Dict[str, List[Dict]]:
        """Group skills by exact category and keep categories with multiple skills."""
        categories = defaultdict(list)
        for _, skill_meta in self.registry_manager.registry.items():
            cat = skill_meta.get("category", "其他 -> 其他")
            categories[cat].append(skill_meta)

        return {cat: skills for cat, skills in categories.items() if len(skills) > 1}

    @staticmethod
    def _split_category(category: str) -> Tuple[str, str]:
        parts = [p.strip() for p in category.split("->") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return parts[0], "其他"
        return "其他", "其他"

    def _read_skill_markdown(self, meta: Dict) -> Dict:
        file_path = os.path.join(self.base_path, meta["file_path"])
        if not os.path.exists(file_path):
            return {"meta": meta, "content": "", "frontmatter": {}}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = {}
        if content.startswith("---"):
            end_idx = content.find("---", 3)
            if end_idx != -1:
                fm_text = content[3:end_idx].strip()
                try:
                    import yaml

                    frontmatter = yaml.safe_load(fm_text) or {}
                except Exception:
                    frontmatter = {}

        return {
            "meta": meta,
            "content": content,
            "frontmatter": frontmatter,
            "file_path": file_path,
        }

    @staticmethod
    def _embedding_text(item: Dict) -> str:
        meta = item.get("meta", {})
        fm = item.get("frontmatter", {})
        body = item.get("content", "")
        return "\n".join(
            [
                str(meta.get("name", "")),
                str(meta.get("description", "")),
                str(fm.get("description", "")),
                ",".join(meta.get("tags", []) if isinstance(meta.get("tags", []), list) else []),
                body,
            ]
        )

    async def cluster_category_skills(self, category: str, group: List[Dict]) -> List[Dict]:
        """Cluster skills within one L2 category and return cluster descriptors."""
        loaded = [self._read_skill_markdown(meta) for meta in group]
        if not loaded:
            return []

        cluster_inputs = [{"embedding_text": self._embedding_text(item)} for item in loaded]
        cluster_index_map = await self.clusterer.cluster_async(cluster_inputs)

        clusters = []
        for cluster_id, indices in cluster_index_map.items():
            members = [loaded[i] for i in indices]
            l3_name = f"聚类_{cluster_id + 1:03d}"
            clusters.append(
                {
                    "category": category,
                    "l3_name": l3_name,
                    "members": members,
                }
            )
        return clusters

    def mount_cluster_to_l3(self, category: str, l3_name: str, members: List[Dict], move: bool = True) -> None:
        """Mount all skills from one cluster into the corresponding L3 directory."""
        l1, l2 = self._split_category(category)
        l3_root = os.path.join(self.base_path, l1, l2, l3_name)
        os.makedirs(l3_root, exist_ok=True)

        for member in members:
            meta = member.get("meta", {})
            src_md = member.get("file_path")
            if not src_md or not os.path.exists(src_md):
                continue

            src_skill_dir = os.path.dirname(src_md)
            skill_name = os.path.basename(src_skill_dir)
            dst_skill_dir = os.path.join(l3_root, skill_name)

            if os.path.abspath(src_skill_dir) == os.path.abspath(dst_skill_dir):
                continue

            if os.path.exists(dst_skill_dir):
                shutil.rmtree(dst_skill_dir)

            if move:
                shutil.move(src_skill_dir, dst_skill_dir)
            else:
                shutil.copytree(src_skill_dir, dst_skill_dir)

            logger.info("  - Mounted '%s' to L3 '%s'", meta.get("name", skill_name), l3_name)

    async def merge_skill_group(self, group: List[Dict], l3_name: str = "聚类_001") -> Dict:
        loaded_skills = []
        for item in group:
            loaded_skills.append(item.get("content", ""))

        content = f"# Skills to Merge ({len(loaded_skills)} total):\\n\\n"
        for i, skill_md in enumerate(loaded_skills, start=1):
            content += f"## Skill {i}\\n{skill_md}\\n\\n"

        response = await self.llm.ainvoke([("system", MERGE_PROMPT), ("human", content)])
        text = response.content if hasattr(response, "content") else str(response)

        fenced = re.search(r"```json\s*(.*?)\s*```", text, flags=re.S)
        if fenced:
            return json.loads(fenced.group(1).strip())

        obj = re.search(r"\{.*\}", text, flags=re.S)
        if obj:
            merged = json.loads(obj.group(0))
            merged.setdefault("yaml_frontmatter", {})
            merged["yaml_frontmatter"].setdefault("tags", [])
            tags = merged["yaml_frontmatter"].get("tags", [])
            if isinstance(tags, list) and l3_name not in tags:
                tags.append(l3_name)
            merged["yaml_frontmatter"]["tags"] = tags
            return merged

        merged = json.loads(text)
        merged.setdefault("yaml_frontmatter", {})
        merged["yaml_frontmatter"].setdefault("tags", [])
        tags = merged["yaml_frontmatter"].get("tags", [])
        if isinstance(tags, list) and l3_name not in tags:
            tags.append(l3_name)
        merged["yaml_frontmatter"]["tags"] = tags
        return merged

    def _write_merged_skill_to_l3(self, merged_skill: Dict, category: str, l3_name: str) -> None:
        import yaml

        fm = merged_skill.get("yaml_frontmatter", {})
        skill_name = fm.get("name", "Merged_Skill").replace("/", "_").replace(" ", "_")
        l1, l2 = self._split_category(category)
        target_dir = os.path.join(self.base_path, l1, l2, l3_name, skill_name)
        os.makedirs(target_dir, exist_ok=True)

        skill_file = os.path.join(target_dir, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(fm, f, allow_unicode=True, sort_keys=False)
            f.write("---\n\n")
            f.write("## 1. Objectives & Background\n")
            f.write(str(merged_skill.get("objectives_and_background", "")).replace("\\n", "\n") + "\n\n")
            f.write("## 2. Workflow Steps\n")
            f.write(str(merged_skill.get("workflow_steps", "")).replace("\\n", "\n") + "\n\n")
            f.write("## 3. Legal Basis\n")
            for basis in merged_skill.get("legal_basis", []):
                f.write(f"- {basis}\n")
            f.write("\n")
            f.write("## 4. Example\n")
            f.write(str(merged_skill.get("example", "")).replace("\\n", "\n") + "\n\n")

            tools = merged_skill.get("tools", [])
            if tools:
                f.write("## 5. Tools\n")
                for tool in tools:
                    f.write(f"- {tool}\n")
                f.write("\n")

        logger.info("  - Wrote merged skill to %s", skill_file)

    async def run_merge_pipeline(self, remove_merged_sources: bool = False, mount_l3: bool = True) -> None:

        self.registry_manager.build_from_filesystem()
        candidates = self.identify_merge_candidates()
        logger.info("Found %d categories with multiple skills.", len(candidates))

        for cat, group in candidates.items():
            logger.info("Clustering %d skills in L2 category '%s'...", len(group), cat)
            clusters = await self.cluster_category_skills(cat, group)
            logger.info("Category '%s' clustered into %d groups.", cat, len(clusters))

            for cluster in clusters:
                members = cluster["members"]
                l3_name = cluster["l3_name"]

                if mount_l3:
                    self.mount_cluster_to_l3(cat, l3_name, members, move=remove_merged_sources)

                if len(members) <= 1:
                    continue

                try:
                    merged_skill = await self.merge_skill_group(members, l3_name=l3_name)
                    self._write_merged_skill_to_l3(merged_skill, cat, l3_name)
                except Exception as e:
                    logger.error(
                        "Failed to merge cluster '%s' in category '%s': %s",
                        l3_name,
                        cat,
                        e,
                    )

        self.registry_manager.build_from_filesystem()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Merge similar legal skills in SkillBank")
    parser.add_argument("--base", type=str, default="./SkillBank", help="Skill library base directory")
    parser.add_argument("--model", type=str, default=os.environ.get("OPENAI_MODEL", "qwen3-32b"), help="LLM model for merge")
    parser.add_argument("--api-base", type=str, default=os.environ.get("OPENAI_API_BASE", "YOUR_API_BASE"), help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY"), help="OpenAI-compatible API key")
    parser.add_argument("--remove-sources", action="store_true", help="Remove original source folders after moving/mounting into L3")
    parser.add_argument("--no-mount-l3", action="store_true", help="Disable mounting source skills into L3 folders")
    parser.add_argument("--cluster-eps", type=float, default=0.10, help="DBSCAN eps (cosine distance threshold)")
    parser.add_argument("--cluster-min-samples", type=int, default=1, help="DBSCAN min_samples")
    parser.add_argument("--embedding-model", type=str, default=os.environ.get("EMBEDDING_MODEL", "Qwen3-Embedding-8B"), help="Embedding model name")
    parser.add_argument("--embedding-base", type=str, default=os.environ.get("EMBEDDING_BASE", "YOUR_EMBEDDING_BASE"), help="Embedding service base URL")
    parser.add_argument("--embedding-api-key", type=str, default=os.environ.get("EMBEDDING_API_KEY", "YOUR_EMBEDDING_API_KEY"), help="Embedding service API key")
    args = parser.parse_args()

    if ChatOpenAI is None:
        raise ImportError(
            "Missing dependency: langchain_openai. Please install it before running legal merger."
        )

    if not args.api_base or args.api_base == "YOUR_API_BASE" or not args.api_key or args.api_key == "YOUR_API_KEY":
        raise RuntimeError("Please set OPENAI_API_BASE and OPENAI_API_KEY environment variables or pass them as arguments.")

    llm = ChatOpenAI(
        model=args.model,
        openai_api_key=args.api_key,
        openai_api_base=args.api_base,
        temperature=0.1,
        max_tokens=4096,
    )

    embedding_service = EmbeddingService(
        model=args.embedding_model,
        base_url=args.embedding_base,
        api_key=args.embedding_api_key,
    )
    clusterer = DBSCANClusterer(
        eps=args.cluster_eps,
        min_samples=args.cluster_min_samples,
        metric="cosine",
        embedding_service=embedding_service,
    )

    merger = LegalSkillMerger(
        llm=llm,
        base_path=args.base,
        embedding_service=embedding_service,
        clusterer=clusterer,
    )
    asyncio.run(
        merger.run_merge_pipeline(
            remove_merged_sources=args.remove_sources,
            mount_l3=not args.no_mount_l3,
        )
    )


if __name__ == "__main__":
    main()
