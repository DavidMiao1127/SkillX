import sys
import os
import re
import json
import asyncio
import logging
from glob import glob

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir in sys.path:
    sys.path.remove(current_dir)
sys.path.insert(0, parent_dir)

from langchain_openai import ChatOpenAI
from SkillX.legal_extension import LegalTextSkillExtractor, dump_skills_to_markdown

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent LLM requests and prevent rate limits / timeouts
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

def read_document(file_path: str) -> str:
    """Read different file formats (MD, TXT, JSON, JSONL)."""
    with open(file_path, "r", encoding="utf-8") as f:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".json":
            data = json.load(f)
            # If it's a list or dict, stringify it to extract text
            return json.dumps(data, ensure_ascii=False)
        elif ext == ".jsonl":
            lines = f.readlines()
            # Combine all objects
            return "\n".join(lines)
        else:
            return f.read()

def structural_chunking(content: str, max_chunk_size: int = 20000) -> list:
    """Intelligently chunk text based on Markdown headers or double newlines."""
    # Split by Markdown Headers (e.g. ## Title)
    sections = re.split(r'\n(?=#{1,4}\s)', content)
    
    chunks = []
    current_chunk = ""
    for sec in sections:
        # If a single section is larger than max_chunk_size, we split it by double newline
        if len(sec) > max_chunk_size:
            sub_secs = sec.split('\n\n')
            for sub in sub_secs:
                if len(current_chunk) + len(sub) > max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sub + '\n\n'
                else:
                    current_chunk += sub + '\n\n'
        else:
            if len(current_chunk) + len(sec) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sec + '\n'
            else:
                current_chunk += sec + '\n'
                
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

async def process_chunk_concurrently(i: int, chunk: str, extractor: LegalTextSkillExtractor):
    """Process a single chunk with semaphore rate-limiting."""
    async with semaphore:
        logger.info(f"  -> Extracting from chunk {i+1} (Length: {len(chunk)} chars)")
        item = {"content": chunk, "skill_library": []}
        try:
            result = await extractor.extract(item)
            extraction_data = result.get("plan_step_metadata", {}).get("doc_extraction", [])
            
            if extraction_data:
                # Interpret returned array properly
                if len(extraction_data) > 0 and "yaml_frontmatter" in extraction_data[0]:
                    skills = extraction_data
                else:
                    skills = [s.get("skill", s) for s in extraction_data if isinstance(s, dict)]
                logger.info(f"  -> ✅ Retrieved {len(skills)} skills from chunk {i+1}")
                return skills
            else:
                logger.info(f"  -> ⏭️ No valid skills found in chunk {i+1} (Dropped/Skipped)")
                return []
        except Exception as e:
            logger.error(f"  -> ❌ Error extracting from chunk {i+1}: {e}")
            return []

async def process_file(file_path: str, extractor: LegalTextSkillExtractor, chunk_size: int = 20000):
    """Intelligently read a file, chunk it structurally, and extract skills concurrently."""
    try:
        content = read_document(file_path)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return []

    # Structural chunking to respect markdown/paragraphs
    chunks = structural_chunking(content, max_chunk_size=chunk_size)
    
    logger.info(f"Processing '{os.path.basename(file_path)}' split into {len(chunks)} contextual chunks...")
    
    # Launch concurrent extraction for all chunks in this file
    tasks = [process_chunk_concurrently(i, chunk, extractor) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    
    all_extracted_skills = []
    for res in results:
        all_extracted_skills.extend(res)
        
    return all_extracted_skills

async def batch_extract(target_folder: str, output_base: str):
    """Run full batch extraction over all supported documents in a folder."""
    openai_api_key = "EMPTY"
    openai_api_base = "http://web.megatechai.com:33652/v1"

    llm = ChatOpenAI(
        model="qwen3-32b",
        openai_api_key=openai_api_key,
        openai_api_base=openai_api_base,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        temperature=0.1
    )
    
    extractor = LegalTextSkillExtractor(llm=llm, verbose=True)
    
    search_pattern_md = os.path.join(target_folder, "**/*.md")
    search_pattern_json = os.path.join(target_folder, "**/*.json")
    search_pattern_jsonl = os.path.join(target_folder, "**/*.jsonl")
    search_pattern_txt = os.path.join(target_folder, "**/*.txt")
    
    docs = glob(search_pattern_md, recursive=True) + \
           glob(search_pattern_json, recursive=True) + \
           glob(search_pattern_jsonl, recursive=True) + \
           glob(search_pattern_txt, recursive=True)
    
    if not docs:
        logger.warning(f"No valid documents (MD, JSON, JSONL, TXT) found in {target_folder}")
        return
        
    logger.info(f"Found {len(docs)} documents. Starting full concurrent processing.")
    
    for file_path in docs:
        skills = await process_file(file_path, extractor)
        if skills:
            logger.info(f"  -> File complete: '{os.path.basename(file_path)}'. New skills: {len(skills)}. Dumping...")
            msg = dump_skills_to_markdown(skills, base_path=output_base)
            logger.info(f"  -> {msg}")
        else:
            logger.info(f"  -> File complete: '{os.path.basename(file_path)}'. No new skills extracted.")
    
    logger.info("Batch extraction task finished.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Full Legal Skill Extraction Pipeline")
    parser.add_argument("--folder", type=str, required=True, help="Path to the folder containing legal markdown books")
    parser.add_argument("--output", type=str, default="/raid/miaoshuo/LegalSkill/SkillBank", help="Base path for the SkillBank")
    
    args = parser.parse_args()
    
    asyncio.run(batch_extract(args.folder, args.output))
