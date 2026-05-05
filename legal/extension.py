import json
import logging
import re
import os
import sys
from typing import Dict, List, Optional

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


def dump_skills_to_markdown(skills_json: List[Dict], base_path: str = "./SkillBank") -> str:
    import os
    import yaml

    for skill in skills_json:
        fm = skill.get("yaml_frontmatter", {})
        name = fm.get("name", "Unnamed_Skill").replace(" ", "_").replace("/", "_")
        category = sanitize_category(fm.get("category", "其他 -> 其他"))
        fm["category"] = category

        cat_path = category.replace(" -> ", "/")
        skill_dir = os.path.join(base_path, cat_path, name)
        os.makedirs(skill_dir, exist_ok=True)
        file_path = os.path.join(skill_dir, "SKILL.md")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(fm, f, allow_unicode=True, sort_keys=False)
            f.write("---\n\n")

            f.write("## 1. Objectives & Background\n")
            f.write(str(skill.get("objectives_and_background", "")).replace("\\n", "\n") + "\n\n")

            f.write("## 2. Workflow Steps\n")
            f.write(str(skill.get("workflow_steps", "")).replace("\\n", "\n") + "\n\n")

            f.write("## 3. Legal Basis\n")
            for basis in skill.get("legal_basis", []):
                f.write(f"- {basis}\n")
            f.write("\n")

            f.write("## 4. Example\n")
            f.write(str(skill.get("example", "")).replace("\\n", "\n") + "\n\n")

            if skill.get("tools"):
                f.write("## 5. Tools\n")
                for tool in skill.get("tools", []):
                    f.write(f"- {tool}\n")
                f.write("\n")

    return f"Successfully dumped {len(skills_json)} skills into {base_path}"


class LegalTextSkillExtractor(BaseSkillExtractor):
    def __init__(self, llm, max_retries: int = 3, verbose: bool = True):
        super().__init__(llm, "legal_domain", verbose=verbose)
        self.max_retries = max_retries

    def get_skill_type(self) -> str:
        return "legal_functional"

    def get_prompt(self) -> str:
        return LEGAL_SKILL_PROMPT

    def _extract_skills_from_response(self, text: str) -> Optional[List[Dict]]:
        match = re.search(r"```json(.*?)```", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass

        match = re.search(r"\[\s*\{.*?\}\s*\]", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return None

    async def extract(self, item: Dict, **kwargs) -> Optional[Dict]:
        doc_text = item.get("content", "")
        skill_library = item.get("skill_library", [])

        messages = [
            ("system", self.get_prompt()),
            (
                "human",
                f"# Document Text:\\n{doc_text}\\n\\n# Existing Skills:\\n{skill_library}\\n\\n"
                "Extract highly professional and specific legal skills."
            ),
        ]

        retry = 0
        plan_step_metadata = {}
        while retry < self.max_retries:
            try:
                response = await self.llm.ainvoke(input=messages, **kwargs)
                response_text = response.content if hasattr(response, "content") else str(response)
                skills = self._extract_skills_from_response(response_text)
                if skills:
                    plan_step_metadata["doc_extraction"] = skills
                    break
            except Exception as e:
                retry += 1
                logger.error(f"Error extracting legal skill: {e}")

        result = item.copy()
        result["plan_step_metadata"] = plan_step_metadata
        return result