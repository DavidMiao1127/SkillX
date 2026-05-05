import json
import logging
import os
import re
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .registry import LegalSkillRegistry

try:
    from SkillX.extraction.base import BaseSkillExtractor
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)          # .../SkillX
    project_parent = os.path.dirname(project_root)       # .../LegalSkill
    if project_parent not in sys.path:
        sys.path.insert(0, project_parent)
    from SkillX.extraction.base import BaseSkillExtractor

logger = logging.getLogger(__name__)

LEGAL_SKILL_PROMPT = """You are a top-tier Legal Knowledge Engineer and Meta-Skill Generator. Your task is to extract reusable, non-trivial, and highly synthesized legal skills from complex legal documents, case laws, or books.

1. Inputs Description
- **Document Text**: The raw legal text to be analyzed.
- **Skill Library**: A collection of all currently available skills.

2. Core Meta-Skill Constraints (Strict Compliance Required)
- **Strict Rejection (No Forced Extraction)**: If the document is a table of contents, purely factual/procedural without legal reasoning, or trivial common sense, DO NOT force an extraction. You MUST return an empty list `[]`.
- **Deconstruction & Noise filtering**: Filter out common knowledge and mechanical recitations of statutes. Exact deeply hidden implicit reasoning logic and burden of proof shifts.
- **Name-Content Match (名实相符)**: The skill's `name` MUST perfectly align with the `content`.
- **Role Metaphors**: BAN all non-legal metaphors (e.g. therapist). Use standard legal roles (e.g., "法官", "当事人", "律师", "原告").
- **No Redundancy**: Do not duplicate the "triggers" inside the workflow text.

3. Strict Taxonomy Mapping (CRITICAL)
Your output `category` MUST strictly match one of the following exact Level 1 (L1) and Level 2 (L2) combinations. Format strictly as `L1 -> L2`. Do NOT create any Level 3 categories.
- **宪法相关法** -> (国家机构组织与职权 / 选举与代表制度 / 国家主权与领土完整 / 公民基本政治权利保障 / 立法与宪法实施 / 监察制度)
- **民法商法** -> (物权 / 合同与准合同 / 知识产权 / 人格权 / 婚姻家庭 / 继承 / 侵权责任 / 商事主体与商事行为 / 民法总则及其他)
- **行政法** -> (行政主体与公务员 / 行政行为 / 行政监督与问责 / 政务与救济 / 部门行政法)
- **经济法** -> (宏观调控 / 市场秩序与竞争规则 / 产业与行业监管 / 对外经济贸易)
- **社会法** -> (劳动关系与劳动保障 / 社会保障与福利 / 特殊群体权益保障 / 社会组织与社会治理)
- **生态环境法** -> (生态环境总则与基础制度 / 污染防治 / 生态保护与修复 / 绿色低碳发展 / 生态环境法律责任与救济)
- **刑法** -> (刑法总则 / 刑法分则 / 刑事执行与合规)
- **诉讼与非诉讼程序法** -> (民事诉讼 / 刑事诉讼 / 行政诉讼与行政复议 / 仲裁与非诉纠纷解决 / 国家赔偿程序)
- **通用法律技能** -> (法律信息检索与要素提取 / 法律文本标准化处理 / 法律逻辑推理与要件分析 / 争议解决标准化分析 / 非诉合规标准化处理 / 法律AI工具协同与数据处理 / 法律输出结果合规性校验)

4. Detailed Skill Output Structure
You must output skills as JSON. To be perfectly compatible with our Markdown SkillBank, each skill object MUST have these exact keys:
- `yaml_frontmatter`: A dictionary for the YAML metadata block containing:
  - `name`: High-level, problem-oriented.
  - `description`: 1-2 sentences summarizing the skill's functionality.
  - `tags`: List of keywords.
  - `triggers`: List of situations where this skill should be invoked. (Keep it brief!).
  - `category`: STRICTLY matching the 2-level taxonomy hierarchy using the tree above. Example: "民法商法 -> 合同与准合同".
- `objectives_and_background`: Extreme deep dive into the core legal problem, theoretical background, exceptions, and prerequisites. (At least 150-200 words).
- `workflow_steps`: Deep deductive reasoning workflow. DO NOT use a flat 1-10 numbered list! Use structured Markdown (Phases, Decision Trees, Parallel Conditions, Bullet points). You MUST include exhaustive sub-points, exact legal criteria, condition test boundaries, and burden of proof shifts. Make sure this section is extensive, comprehensive, and highly detailed (Aim for at least 500-800 words/50 lines of purely intellectual analysis for the workflow alone).
- `legal_basis`: Precise enumeration of laws and articles (e.g., ["《中华人民共和国民法典》第一千一百六十五条第一款"]). Include any judicial interpretations or minutes if implicitly referenced. Do NOT use generic phrases like "according to relevant laws".
- `example`: A highly detailed, professional legal hypothetical or case study applying the steps. Detail the arguments of both Plaintiff and Defendant, and show how the Court resolves it using the workflow above. (At least 150 words).
- `tools`: A list of associated tools, or [] if none.

5. Output Format
You must output a JSON list of objects EXACTLY like this:
```json
[
    {
        "yaml_frontmatter": {
            "name": "合同编调整范围的识别与适用边界判断",
            "description": "识别争议合同是否受《民法典》合同编调整的通用分析步骤",
            "tags": ["合同性质", "法律适用边界"],
            "triggers": ["当对合同适用民事还是行政程序产生争议时"],
            "category": "民法商法 -> 合同与准合同"
        },
        "objectives_and_background": "Objectives: 识别争议合同...\\nPrerequisites: 确定存在合意...",
        "workflow_steps": "### 1. 前置审查（识别主体与目的）\\n- **核心要素检查**：核实双方是否为平等民事主体，是否存在行政隶属关系...\\n\\n### 2. 并行分类讨论（适用边界）\\n- **情形A（行政合同或指令任务）**：属于《政府采购法》等特别法调整范围...\\n- **情形B（复合型身份协议）**：区分财产部分与身份部分，财产部分参照适用合同编...\\n\\n### 3. 查明与举证责任分配\\n- **举证责任**：主张适用...的一方需证明...",
        "legal_basis": ["《中华人民共和国民法典》第四百六十四条"],
        "example": "在一起新冠疫苗采购案中...",
        "tools": []
    }
]
```
Ensure valid JSON output without any trailing text outside the JSON block.
"""


def sanitize_category(category_str: str) -> str:
    """Ensure the category matches expected L1 -> L2 structure, fallback if invalid."""
    valid_l1 = {
        "宪法相关法", "民法商法", "行政法", "经济法", "社会法",
        "生态环境法", "刑法", "诉讼与非诉讼程序法", "通用法律技能", "其他"
    }
    parts = [p.strip() for p in category_str.split("->") if p.strip()]
    if len(parts) >= 1 and parts[0] in valid_l1:
        if len(parts) == 1:
            return f"{parts[0]} -> 其他"
        return f"{parts[0]} -> {parts[1]}"
    return "其他 -> 其他"


def _normalize_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[\s_\-–—:：,，.。()（）\[\]{}!！?？/\\]+", "", s)
    return s


def _split_category(category: str) -> Tuple[str, str]:
    parts = [p.strip() for p in (category or "").split("->") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], "其他"
    return "其他", "其他"


def _jaccard_chars(a: str, b: str) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def _merge_unique_list(old_items: Any, new_items: Any) -> List[str]:
    merged: List[str] = []
    for source in [old_items, new_items]:
        if not isinstance(source, list):
            continue
        for item in source:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)
    return merged


def _merge_text_block(old_text: str, new_text: str) -> str:
    old_text = (old_text or "").strip()
    new_text = (new_text or "").strip()
    if not old_text:
        return new_text
    if not new_text:
        return old_text
    if new_text in old_text:
        return old_text
    if old_text in new_text:
        return new_text
    return f"{old_text}\n\n---\n\n### 增量更新\n{new_text}"


def _parse_existing_skill_markdown(file_path: str) -> Dict[str, Any]:
    import yaml

    result: Dict[str, Any] = {
        "frontmatter": {},
        "objectives_and_background": "",
        "workflow_steps": "",
        "legal_basis": [],
        "example": "",
        "tools": [],
    }

    if not os.path.exists(file_path):
        return result

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    body = content
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            fm_text = content[3:end_idx].strip()
            try:
                result["frontmatter"] = yaml.safe_load(fm_text) or {}
            except Exception:
                result["frontmatter"] = {}
            body = content[end_idx + 3 :]

    sec_pattern = re.compile(
        r"^##\s*\d+\.\s*(Objectives\s*&\s*Background|Workflow\s*Steps|Legal\s*Basis|Example|Tools)\s*$",
        flags=re.M,
    )
    matches = list(sec_pattern.finditer(body))
    sections: Dict[str, str] = {}
    for idx, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()

    result["objectives_and_background"] = sections.get("objectives & background", "")
    result["workflow_steps"] = sections.get("workflow steps", "")
    result["example"] = sections.get("example", "")

    legal_basis_block = sections.get("legal basis", "")
    if legal_basis_block:
        result["legal_basis"] = [
            line.lstrip("- ").strip()
            for line in legal_basis_block.splitlines()
            if line.strip().startswith("-")
        ]

    tools_block = sections.get("tools", "")
    if tools_block:
        result["tools"] = [
            line.lstrip("- ").strip()
            for line in tools_block.splitlines()
            if line.strip().startswith("-")
        ]

    return result


def _find_similar_existing_skill(skill: Dict[str, Any], registry: Dict[str, Any], threshold: float = 0.82) -> Optional[Dict[str, Any]]:
    fm = skill.get("yaml_frontmatter", {})
    new_name = str(fm.get("name", "")).strip()
    if not new_name:
        return None

    new_norm = _normalize_name(new_name)
    if not new_norm:
        return None

    new_cat = sanitize_category(str(fm.get("category", "其他 -> 其他")))
    new_l1, _ = _split_category(new_cat)
    new_tags = {str(t).strip().lower() for t in fm.get("tags", []) if str(t).strip()}

    best_meta: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for _, meta in registry.items():
        old_name = str(meta.get("name", "")).strip()
        old_norm = _normalize_name(old_name)
        if not old_norm:
            continue

        old_cat = sanitize_category(str(meta.get("category", "其他 -> 其他")))
        old_l1, _ = _split_category(old_cat)
        if old_l1 != new_l1:
            continue

        name_ratio = SequenceMatcher(None, new_norm, old_norm).ratio()
        char_jaccard = _jaccard_chars(new_norm, old_norm)

        if new_norm in old_norm or old_norm in new_norm:
            name_ratio = max(name_ratio, 0.93)

        old_tags = {str(t).strip().lower() for t in meta.get("tags", []) if str(t).strip()}
        tag_score = (len(new_tags & old_tags) / len(new_tags | old_tags)) if (new_tags or old_tags) else 0.0

        cat_bonus = 0.05 if old_cat == new_cat else 0.0
        score = 0.65 * name_ratio + 0.25 * char_jaccard + 0.10 * tag_score + cat_bonus

        if score > best_sc