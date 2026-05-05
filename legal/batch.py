import asyncio
import json
import logging
import os
import re
import difflib
from glob import glob
from typing import Any, List, Dict

from .registry import LegalSkillRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


def read_document(file_path: str) -> str:
    """Read supported file formats: MD, TXT, JSON, JSONL."""
    with open(file_path, "r", encoding="utf-8") as f:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".json":
            data = json.load(f)
            return json.dumps(data, ensure_ascii=False)
        if ext == ".jsonl":
            return "\n".join(f.readlines())
        return f.read()


def structural_chunking(content: str, max_chunk_size: int = 20000) -> List[str]:
    """Chunk text by markdown headers first, then paragraph fallback."""
    sections = re.split(r"\n(?=#{1,4}\s)", content)

    chunks: List[str] = []
    current_chunk = ""
    for sec in sections:
        if len(sec) > max_chunk_size:
            sub_sections = sec.split("\n\n")
            for sub in sub_sections:
                if len(current_chunk) + len(sub) > max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sub + "\n\n"
                else:
                    current_chunk += sub + "\n\n"
        else:
            if len(current_chunk) + len(sec) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sec + "\n"
            else:
                current_chunk += sec + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks


async def merge_with_existing_skill_async(llm: Any, existing_md_content: str, new_skill_dict: Dict) -> Dict:
    """Merge a newly extracted skill into an existing skill file using LLM."""
    merge_prompt = """You are an elite Legal Knowledge Expert.
We have an existing legal skill AND a newly extracted skill that are highly similar or identical in scope.
Your task is to MERGE the new skill's insights (new conditions, steps, legal bases, examples) into the existing skill, producing ONE comprehensive, exhaustive JSON object. 
Do not lose any important nuances from the existing skill.

Outputs MUST follow this JSON structure precisely:
{
  "yaml_frontmatter": {"name": "...", "description": "...", "tags": ["..."], "triggers": ["..."], "category": "L1 -> L2"},
  "objectives_and_background": "...",
  "workflow_steps": "...",
  "legal_basis": ["..."],
  "example": "...",
  "tools": []
}"""
    
    new_skill_str = json.dumps(new_skill_dict, ensure_ascii=False, indent=2)
    content = f"# Existing Skill (Markdown):\\n{existing_md_content}\\n\\n# Newly Extracted Skill:\\n{new_skill_str}"
    
    messages = [("system", merge_prompt), ("human", content)]
    try:
        response = await llm.ainvoke(input=messages)
        text = response.content if hasattr(response, "content") else str(response)
        
        # Try to parse json block
        import re
        fenced = re.search(r"```json\s*(.*?)\s*```", text, flags=re.S)
        if fenced:
            return json.loads(fenced.group(1).strip())
        obj = re.search(r"\{.*\}", text, flags=re.S)
        if obj:
            return json.loads(obj.group(0))
        
        return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to merge skills via LLM: {e}")
        return new_skill_dict # fallback to new skill


async def check_semantic_overlap_async(llm: Any, existing_meta: Dict, new_skill: Dict) -> bool:
    """Use LLM to judge if two skills are semantically redundant or one contains the other."""
    judge_prompt = """You are a Legal Knowledge Architect. 
I will provide you with the metadata of an EXISTING skill and a NEWLY extracted skill.
Your task is to determine if they are SEMANTICALLY REDUNDANT, highly overlapping, or if one is a subset of the other.

Decision Criteria:
- YES: They cover the same legal problem, reasoning steps, or the new one is just a variation/subset of the existing one.
- NO: They cover distinct legal issues, different procedures, or apply to fundamentally different scenarios.

Output ONLY 'YES' or 'NO'."""
    
    existing_text = f"Name: {existing_meta.get('name')}\nDescription: {existing_meta.get('description')}"
    new_text = f"Name: {new_skill.get('yaml_frontmatter', {}).get('name')}\nDescription: {new_skill.get('yaml_frontmatter', {}).get('description')}"
    
    content = f"# EXISTING SKILL:\n{existing_text}\n\n# NEW SKILL:\n{new_text}"
    messages = [("system", judge_prompt), ("human", content)]
    
    try:
        response = await llm.ainvoke(input=messages)
        text = (response.content if hasattr(response, "content") else str(response)).strip().upper()
        return "YES" in text
    except Exception as e:
        logger.error(f"Semantic overlap check failed: {e}")
        return False


async def process_chunk_concurrently(i: int, chunk: str, extractor: Any, existing_skills_context: str = ""):
    """Extract skills from a single chunk with semaphore rate limiting."""
    async with semaphore:
        logger.info("  -> Extracting from chunk %d (Length: %d chars)", i + 1, len(chunk))
        item = {"content": chunk, "skill_library": existing_skills_context}
        try:
            result = await extractor.extract(item)
            extraction_data = result.get("plan_step_metadata", {}).get("doc_extraction", [])

            if extraction_data:
                if len(extraction_data) > 0 and "yaml_frontmatter" in extraction_data[0]:
                    skills = extraction_data
                else:
                    skills = [s.get("skill", s) for s in extraction_data if isinstance(s, dict)]
                logger.info("  -> ✅ Retrieved %d skills from chunk %d", len(skills), i + 1)
                return skills

            logger.info("  -> ⏭️ No valid skills found in chunk %d (Dropped/Skipped)", i + 1)
            return []
        except Exception as e:
            logger.error("  -> ❌ Error extracting from chunk %d: %s", i + 1, e)
            return []


async def process_file(file_path: str, extractor: Any, chunk_size: int = 20000, existing_skills_context: str = ""):
    """Read file, structurally chunk, then extract skills concurrently."""
    try:
        content = read_document(file_path)
    except Exception as e:
        logger.error("Failed to read %s: %s", file_path, e)
        return []

    chunks = structural_chunking(content, max_chunk_size=chunk_size)
    logger.info("Processing '%s' split into %d contextual chunks...", os.path.basename(file_path), len(chunks))

    tasks = [process_chunk_concurrently(i, chunk, extractor, existing_skills_context) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)

    all_extracted_skills = []
    for res in results:
        all_extracted_skills.extend(res)
    return all_extracted_skills


async def batch_extract(target_folder: str, output_base: str, chunk_size: int = 20000, build_registry: bool = True):
    """Run full batch extraction over supported documents in target_folder."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise ImportError("Missing dependency: langchain_openai. Please install it before running legal batch extraction.") from e

    from .extension import LegalTextSkillExtractor, dump_skills_to_markdown

    import os
    api_base = os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "qwen3-32b")
    if not api_base or not api_key:
        raise RuntimeError("Please set OPENAI_API_BASE and OPENAI_API_KEY environment variables before running extraction.")

    llm = ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base=api_base,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        temperature=0.1,
    )
    extractor = LegalTextSkillExtractor(llm=llm, verbose=True)

    patterns = ["**/*.md", "**/*.json", "**/*.jsonl", "**/*.txt"]
    docs = []
    for p in patterns:
        docs.extend(glob(os.path.join(target_folder, p), recursive=True))

    if not docs:
        logger.warning("No valid documents (MD, JSON, JSONL, TXT) found in %s", target_folder)
        return

    logger.info("Found %d documents. Starting processing.", len(docs))
    
    registry = LegalSkillRegistry(output_base)
    registry.build_from_filesystem()
    from .extension import sanitize_category

    for file_path in docs:
        skills = await process_file(file_path=file_path, extractor=extractor, chunk_size=chunk_size, existing_skills_context="")
        if skills:
            logger.info("  -> File complete: '%s'. Extracted: %d. Checking for overlaps...", os.path.basename(file_path), len(skills))
            
            final_skills = []
            for skill in skills:
                fm = skill.get("yaml_frontmatter", {})
                new_cat = sanitize_category(fm.get("category", "其他 -> 其他"))
                new_name = fm.get("name", "Unnamed_Skill").replace(" ", "_").replace("/", "_")
                
                similar_match = None
                
                # 1. First pass: Quick string similarity for efficiency
                cadidates = []
                for ext_id, ext_info in registry.registry.items():
                    if ext_info.get("category") == new_cat:
                        ratio = difflib.SequenceMatcher(None, new_name, ext_info.get("name", "")).ratio()
                        if ratio > 0.5:
                            cadidates.append((ratio, ext_info))
                
                # Sort by string ratio
                cadidates.sort(key=lambda x: x[0], reverse=True)
                
                # 2. Second pass: Use LLM for semantic judgment (top 3 candidates)
                for ratio, ext_info in cadidates[:3]:
                    is_redundant = await check_semantic_overlap_async(llm, ext_info, skill)
                    if is_redundant:
                        similar_match = ext_info
                        logger.info("    -> Semantic Overlap Detected with '%s' (Judged by LLM)", similar_match['name'])
                        break

                if similar_match:
                    ext_file_path = os.path.join(output_base, similar_match["file_path"])
                    if os.path.exists(ext_file_path):
                        with open(ext_file_path, "r", encoding="utf-8") as f:
                            old_md = f.read()
                        merged_skill = await merge_with_existing_skill_async(llm, old_md, skill)
                        # Keep the old name so it overwrites correctly
                        merged_skill.setdefault("yaml_frontmatter", {})["name"] = similar_match["name"]
                        merged_skill["yaml_frontmatter"]["category"] = similar_match["category"]
                        final_skills.append(merged_skill)
                    else:
                        final_skills.append(skill)
                else:
                    final_skills.append(skill)

            msg = dump_skills_to_markdown(final_skills, base_path=output_base)
            logger.info("  -> %s", msg)
            
            # Update memory registry to catch duplicates within the same batch
            for sk in final_skills:
                fm = sk.get("yaml_frontmatter", {})
                nm = fm.get("name", "Unnamed")
                cat = sanitize_category(fm.get("category", "其他 -> 其他"))
                registry.registry[nm] = {
                    "name": nm,
                    "category": cat,
                    "file_path": os.path.join(cat.replace(" -> ", "/"), nm, "SKILL.md")
                }
        else:
            logger.info("  -> File complete: '%s'. No new skills extracted.", os.path.basename(file_path))

    if build_registry:
        logger.info("Batch extraction finished. Building registry...")
        registry = LegalSkillRegistry(output_base)
        registry.build_from_filesystem()

    logger.info("Batch legal pipeline completed.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Full Legal Skill Extraction Pipeline")
    parser.add_argument("--folder", type=str, required=True, help="Folder containing legal files")
    parser.add_argument("--output", type=str, default="./SkillBank", help="Output base path for skill bank")
    parser.add_argument("--chunk-size", type=int, default=20000, help="Max chars per chunk")
    parser.add_argument("--skip-registry", action="store_true", help="Skip registry build after extraction")
    args = parser.parse_args()

    asyncio.run(
        batch_extract(
            target_folder=args.folder,
            output_base=args.output,
            chunk_size=args.chunk_size,
            build_registry=not args.skip_registry,
        )
    )


if __name__ == "__main__":
    main()
