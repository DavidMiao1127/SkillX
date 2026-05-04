<div align="center">
<h1 align="center"> ⚖️ Legal-SkillX </h1>
<b>Automated Legal Skill Knowledge Base Construction Framework</b>

[English](README.md) | [中文](README_CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
</div>

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Output Format & Storage](#output-format--storage)
- [Skill Clustering & Merging](#skill-clustering--merging)
- [Acknowledgement](#acknowledgement)

## Overview
**Legal-SkillX** is an open-source framework adapted from [SkillX](https://github.com/zjunlp/SkillX) specifically for the **Legal Domain**. It automates the extraction of profound, reusable legal reasoning skills from unstructured legal documents, case laws, and textbooks.

Instead of relying on trivial generic wrappers, Legal-SkillX distills deep legal deductions, burden of proof shifts, and statutory matching into a standardized Markdown-based Knowledge Base.

## Key Features
- **Strict Legal Taxonomy**: Forces the LLM to assign each skill to an authoritative 2-level Chinese legal taxonomy (e.g., `Civil and Commercial Law → Contracts and Quasi-Contracts`, see `./prompts/legal/法律Skill分类体系.md`), preventing fragmented or made-up categories.
- **Structured Chunking**: Splits long documents by Markdown headers and paragraphs to preserve context; supports `.md`, `.txt`, `.json`, `.jsonl` and more.
- **High-Concurrency & Robust Pipeline**: Uses async semaphore to control LLM concurrency, preventing API rate limits and ensuring stable extraction for large corpora.
- **Automated, Structured Output**: Dumps each extracted skill as a Markdown file with YAML frontmatter, organized as `SkillBank/L1/L2/SkillName/SKILL.md` for easy RAG and agent loading.
- **Clustering & Merging**: Supports DBSCAN-based clustering and LLM-powered merging of similar skills within each category for better knowledge management.

## Installation
```bash
pip install -r requirements.txt
pip install langchain-openai PyYAML
```

**Configuration:**
You must set your own OpenAI-compatible API endpoint and key before running extraction or merging. For example:

```sh
export OPENAI_API_BASE="https://your-openai-compatible-endpoint"
export OPENAI_API_KEY="your-api-key"
# (Optional) export OPENAI_MODEL="qwen3-32b"
```

## Quick Start
Use the `batch_legal_extraction.py` script to process your legal corpus. Supports `.md`, `.txt`, `.json`, `.jsonl` and more.

```bash
# Make sure you have set OPENAI_API_BASE and OPENAI_API_KEY as above!
python3 batch_legal_extraction.py \
    --folder "../books" \
    --output "./LegalSkill"

# Or use the wrapper shell script
sh extract.sh ../books ./SkillBank
```

**The script will automatically:**
1. Scan the folder and read all supported files.
2. Chunk text contextually by structure.
3. Extract professional legal skills concurrently via LLM.
4. Filter out trivial content and persist non-trivial skills to the output directory tree.

## Output Format & Storage
Each extracted skill is standardized as a Markdown file with YAML frontmatter, for easy RAG and agent integration:

```
SkillBank/
└── Civil and Commercial Law/
    └── Contracts and Quasi-Contracts/
        └── Determining Unilateral Termination Rights in Contract Performance/
            └── SKILL.md
```
Each `SKILL.md` contains: `Objectives & Background`, `Workflow Steps` (reasoning/execution flow), `Legal Basis` (real legal articles), and `Example` (realistic case).

## Skill Clustering & Merging
After extraction, you can cluster and merge similar skills for better management:

```bash
# Make sure you have set OPENAI_API_BASE and OPENAI_API_KEY as above!
python3 -m legal.merger \
    --base ./LegalSkill \
    --embedding-base YOUR_EMBEDDING_BASE \
    --embedding-model Qwen3-Embedding-8B
```

### Clustering & Merge Workflow
1. Rebuild registry from all current `SKILL.md` files.
2. Group by **L2 category** (e.g., `Civil and Commercial Law → Contracts and Quasi-Contracts`).
3. Within each L2, use embedding + **DBSCAN** to cluster similar skills.
4. For each cluster, create an **L3 directory** (`Cluster_001`, `Cluster_002`, ...), and mount all cluster skills under that L3.
5. If a cluster has more than one skill, call the LLM to merge them, and write the merged `SKILL.md` into the same L3 directory.
6. Rebuild the registry to index the new structure.

## Acknowledgement
This adaptation is built on top of **SkillX** (by zjunlp). We sincerely thank the original authors for their pioneering framework in Agent experience learning.
