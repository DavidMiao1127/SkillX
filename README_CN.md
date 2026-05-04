<div align="center">
<h1 align="center"> ⚖️ Legal-SkillX (法律技能提取框架) </h1>
<b>面向法律垂直领域的自动化技能知识库构建框架</b>

[English](README.md) | [中文](README_CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
</div>

## 目录
- [项目概述](#项目概述)
- [核心特性](#核心特性)
- [安装指南](#安装指南)
- [快速开始](#快速开始)
- [输出格式与存储](#输出格式与存储)
- [技能聚类与合并](#技能聚类与合并)
- [致谢](#致谢)

## 项目概述
**Legal-SkillX** 是基于开源项目 [SkillX](https://github.com/zjunlp/SkillX) 改良的**法律领域专用技能生成框架**。该框架旨在从非结构化的法律文书、判例、法学专著中，自动萃取可复用的法律推理模型或执行工作流，并转化为标准化的技能（Skill）知识库，供大模型 Agent 直接挂载使用。

## 核心特性
- **严谨的法律分类树 (Taxonomy)**：强制约束 LLM 将生成的技能精准挂载到中国权威法律两级分类体系（如 `民法商法 -> 合同与准合同`，详见[分类体系](https://github.com/DavidMiao1127/SkillX/blob/main/prompts/legal/法律Skill分类体系.md)）下，拒绝碎片化杜撰的目录。
- **结构化智能分块**：通过 Markdown 标题级别和自然段落智能切分长文本，最大程度保留法律文献的上下文连贯性；同时，也支持json、jsonl等多种来源文本格式。
- **高并发与容错管线**：支持并发调度，使用 Semaphore 信号量控制并发数，防止触发大模型 API 的流控，保证海量文档的稳定提取。
- **自动化、结构化管理**：实时拦截提取结果，并直接以 `LegalSkill/一级分类/二级分类/Skill名称/SKILL.md` 的规范目录及包含 YAML 元数据的形式持久化。
- **聚类与合并**：支持对提取的skill基于分类体系进行DBSCAN聚类、对语义及功能相似的skill进行合并，以更好实现对技能的管理。

## 安装指南
```bash
pip install -r requirements.txt
pip install langchain-openai PyYAML
```

**环境变量配置：**
在运行抽取或合并前，必须自行设置 OpenAI 兼容的 API 地址和密钥。例如：

```sh
export OPENAI_API_BASE="https://your-openai-compatible-endpoint"
export OPENAI_API_KEY="your-api-key"
# （可选）export OPENAI_MODEL="qwen3-32b"
```

## 快速开始
通过 `batch_legal_extraction.py` 脚本来批处理您的法律资料夹，支持 `.md`、`.txt`、`.json` 和 `.jsonl` 格式。

```bash
python3 batch_legal_extraction.py \
    --folder "../books" \
    --output "./LegalSkill"

# 或直接使用封装脚本
sh extract.sh ../books ./SkillBank
```

**脚本会自动执行以下流程：**
1. 扫描文件夹并读取内容。
2. 对文本进行智能上下文分库。
3. 并发请求 LLM 抽取专业法律技能。
4. 自动过滤毫无营养的内容，并将非平凡的技能提取存入本地文件树。

## 输出格式与存储
每一个提取的技能都会被标准化为具有 YAML 前言的 Markdown 文件，方便后续的检索增强（RAG）和 Agent 加载：

```
SkillBank/
└── 民法商法/
    └── 合同与准合同/
        └── 合同履行中违约方单方解除权的认定与限制/
            └── SKILL.md
```
`SKILL.md` 正文包含了深刻的：`Objectives & Background`（背景与目的）、`Workflow Steps`（逻辑推演链/执行工作流）、`Legal Basis`（法律依据，引用真实法律条款）、及 `Example`（真实的案例）。

## 技能聚类与合并
在提取完成后，可通过模块命令维护 registry 并执行相似技能合并：

```bash
python3 -m legal.merger \
    --base ./LegalSKill \
    --embedding-base http://127.0.0.1:7000 \
    --embedding-model Qwen3-Embedding-8B
```

### 聚类与合并流程
1. 从当前 `SKILL.md` 全量重建 registry。
2. 先按**二级分类（L2）**分组。
3. 在每个 L2 组内用 embedding + **DBSCAN** 做聚类。
4. 为每个聚类生成一个**三级分类目录（L3）**（如 `聚类_001`、`聚类_002`），并把该簇所有技能挂载到对应 L3 下。
5. 若某个簇内技能数量 > 1，再调用 LLM 识别相似skill进行融合，并将融合后的 `SKILL.md` 也写入同一 L3 目录。
6. 最后再次重建 registry，确保新目录结构被索引。

## 致谢
本项目构建于 **SkillX** (由 zjunlp 开发) 基础之上并进行了垂直领域的重构。我们真诚地感谢原作者在 Agent 经验学习方面提供的优秀基座。
