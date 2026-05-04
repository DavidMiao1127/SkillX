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
- [致谢](#致谢)

## 📖 项目概述
**Legal-SkillX** 是基于开源项目 [SkillX](https://github.com/zjunlp/SkillX) 深度改良的**法律领域专用技能生成框架**。该框架旨在从非结构化的法律文书、判例、法学专著中，自动萃取可复用的深层次法律推理模型，并转化为标准化的技能（Skill）知识库，供大模型 Agent 直接挂载使用。

它摒弃了浅层的法条复读，强制要求萃取包含**隐性逻辑、举证责任分配及法定核心要件**的深度工作流。

## 🤖 核心特性
- **严谨的法律分类树 (Taxonomy)**：强制约束 LLM 将生成的技能精准挂载到中国权威法律两级分类体系（如 `民法商法 -> 合同与准合同`）下，拒绝碎片化瞎编目录。
- **反切分与穿透式重写 (Anti-Fragmentation)**：严禁机械式文本切块，强制要求将相关法律概念融合成一个宏观、具有树状或并行判定分支的高级演绎工作流。
- **结构化智能分块 (Structural Chunking)**：通过 Markdown 标题级别和自然段落智能切分长文本，最大程度保留法律文献的上下文连贯性。
- **高并发与容错管线**：支持并发调度，使用 Semaphore 信号量控制并发数，防止触发大模型 API 的流控，保证海量文档的稳定提取。
- **自动化落盘与结构化管理**：实时拦截提取结果，并直接以 `SkillBank/一级分类/二级分类/Skill名称/SKILL.md` 的规范目录及包含 YAML 元数据的形式持久化。

## 🔧 安装指南
```bash
pip install -r requirements.txt
pip install langchain-openai PyYAML
```

## 🏃 快速开始
通过 `batch_legal_extraction.py` 脚本来批处理您的法律资料夹，支持 `.md`、`.txt`、`.json` 和 `.jsonl` 格式。

```bash
python batch_legal_extraction.py     --folder "/指向/您的/法律书籍或裁判文书文件夹"     --output "./SkillBank"
```

**脚本会自动执行以下流程：**
1. 扫描文件夹并读取内容。
2. 基于 Markdown 语法进行智能上下文分库。
3. 并发请求 LLM 抽取专业法律技能。
4. 自动过滤毫无营养的内容，并将非平凡的技能提取存入本地文件树。

## 📂 输出格式与存储
每一个提取的技能都会被标准化为具有 YAML 前言的 Markdown 文件，方便后续的检索增强（RAG）和 Agent 加载：

```
SkillBank/
└── 民法商法/
    └── 合同与准合同/
        └── 合同编调整范围的识别与适用边界判断/
            └── SKILL.md
```
`SKILL.md` 正文包含了深刻的：`Objectives & Background`（背景与目的）、`Workflow Steps`（逻辑推演链）、`Legal Basis`（法律依据）、及 `Example`（抗辩博弈场景）。

## 🙏 致谢
本项目构建于 **SkillX** (由 zjunlp 开发) 基础之上并进行了垂直领域的重构。我们真诚地感谢原作者在 Agent 经验学习方面提供的优秀基座。
