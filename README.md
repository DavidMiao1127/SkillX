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
- [File Formats & Output](#file-formats--output)
- [Acknowledgement](#acknowledgement)

## 📖 Overview
**Legal-SkillX** is an open-source framework adapted from [SkillX](https://github.com/zjunlp/SkillX) specifically for the **Legal Domain**. It automates the extraction of profound, reusable legal reasoning skills from unstructured legal documents, case laws, and textbooks.

Instead of relying on trivial generic wrappers, Legal-SkillX distills deep legal deductions, burden of proof shifts, and statutory matching into a standardized Markdown-based Knowledge Base.

## 🤖 Key Features
- **Strict Taxonomy Mapping**: Automatically categorizes extracted skills into a robust 2-level Chinese Legal Taxonomy (e.g., `民法商法 -> 合同与准合同`).
- **Anti-Fragmentation & Deep Synthesis**: Forces the LLM to merge related legal concepts into unified, high-level deductive workflows instead of mechanically splitting texts.
- **Structural Chunking**: Intelligently chunks large documents using Markdown headers to preserve contextual boundaries.
- **High-Concurrency Pipeline**: Asynchronous batch processing with semaphore rate-limiting for rapid corpus analysis.
- **Real-time Persistence**: Dumps skills instantly to a hierarchical folder structure (`SkillBank/Level1/Level2/SkillName/SKILL.md`) upon chunk completion.

## 🔧 Installation
```bash
pip install -r requirements.txt
pip install langchain-openai PyYAML
```

## 🏃 Quick Start
Use the `batch_legal_extraction.py` script to process a corpus of legal texts. The pipeline supports `.md`, `.txt`, `.json`, and `.jsonl`.

```bash
python batch_legal_extraction.py     --folder "/path/to/your/legal_books_or_cases"     --output "./SkillBank"
```

**Runtime Features:**
- The script will automatically discover valid documents.
- Structurally chunk them avoiding context loss.
- Extract skills concurrently using the configured LLM API.
- Safely save them directly into the `--output` directory tree.

## 📂 Output Architecture
Extracted skills are stored in an organized Markdown format containing a YAML frontmatter for seamless Agent integrations:

```
SkillBank/
└── 民法商法/
    └── 合同与准合同/
        └── 合同编调整范围的识别与适用边界判断/
            └── SKILL.md
```
Inside `SKILL.md`, you will find: `Objectives & Background`, `Workflow Steps` (decision trees and reasoning), `Legal Basis`, and practical `Examples`.

## 🙏 Acknowledgement
This adaptation is built on top of **SkillX** (by zjunlp). We sincerely thank the original authors for their pioneering framework in Agent experience learning.
