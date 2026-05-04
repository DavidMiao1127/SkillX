import asyncio
import json
import logging
import os
import re
from glob import glob
from typing import Any, List

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


async def process_chunk_concurrently(i: int, chunk: str, extractor: Any):
    """Extract skills from a single chunk with semaphore rate limiting."""
    async with semaphore:
        logger.info("  -> Extracting from chunk %d (Length: %d chars)", i + 1, len(chunk))
        item = {"content": chunk, "skill_library": []}
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


async def process_file(file_path: str, extractor: Any, chunk_size: int = 20000):
    """Read file, structurally chunk, then extract skills concurrently."""
    try:
        content = read_document(file_path)
    except Exception as e:
        logger.error("Failed to read %s: %s", file_path, e)
        return []

    chunks = structural_chunking(content, max_chunk_size=chunk_size)
    logger.info("Processing '%s' split into %d contextual chunks...", os.path.basename(file_path), len(chunks))

    tasks = [process_chunk_concurrently(i, chunk, extractor) for i, chunk in enumerate(chunks)]
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

    for file_path in docs:
        skills = await process_file(file_path=file_path, extractor=extractor, chunk_size=chunk_size)
        if skills:
            logger.info("  -> File complete: '%s'. New skills: %d. Dumping...", os.path.basename(file_path), len(skills))
            msg = dump_skills_to_markdown(skills, base_path=output_base)
            logger.info("  -> %s", msg)
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
