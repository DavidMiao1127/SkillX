"""Skill extraction from trajectories.

Supports two extraction modes:
1. FunctionalSkillExtractor: Step-based extraction (AppWorld/BFCL style)
2. AtomicSkillExtractor: Tool-based extraction with omission detection (τ²-Bench style)
"""

import re
import json
import logging
from typing import Dict, Optional, List, Any, Set
from collections import defaultdict

from .base import BaseSkillExtractor
from ..prompts.registry import PromptRegistry
from ..core.skill import Skill, SkillMetadata

logger = logging.getLogger(__name__)


class FunctionalSkillExtractor(BaseSkillExtractor):
    """
    Extract functional skills based on plan steps.

    For each step in the plan, extracts a modular, reusable skill
    with Python-like implementation code.
    """

    def __init__(
        self,
        llm,
        benchmark: str = "appworld",
        max_retries: int = 5,
        verbose: bool = True
    ):
        super().__init__(llm, benchmark, verbose=verbose)
        self.max_retries = max_retries

    def get_skill_type(self) -> str:
        return "functional"

    def get_prompt(self) -> str:
        return PromptRegistry.get("skill_extraction", self.benchmark)

    def _extract_skills_from_response(self, text: str) -> Optional[List[Dict]]:
        """Extract skills JSON from response."""
        match = re.search(r"```json(.*?)```", text, flags=re.S)
        if match:
            try:
                skills = json.loads(match.group(1).strip())
                return skills
            except json.JSONDecodeError:
                pass
        if self.verbose:
            logger.warning("No valid skills JSON found in response")
        return None

    async def extract(
        self,
        item: Dict,
        **kwargs
    ) -> Optional[Dict]:
        """
        Extract functional skills from a trajectory item.

        Args:
            item: Dictionary with trajectory and plan information

        Returns:
            Item with added skills metadata
        """
        user_task = item.get("user_task", "")
        trajectory = item.get("successful_trajectory", item.get("trajectory", []))
        plan = item.get("plan", "")
        skill_library = item.get("exp_metadata", {}).get("skills", [])

        # Parse plan steps
        plan_steps = [
            line.strip() for line in plan.split("\n")
            if line.strip().startswith("# step")
        ]

        if not plan_steps:
            logger.warning("No plan steps found")
            return None

        plan_step_metadata = {}

        for step in plan_steps:
            if self.verbose:
                logger.info(f"Extracting skill for step: {step[:50]}...")

            messages = [
                ("system", self.get_prompt()),
                ("human", (
                    f"# User task: {user_task}\n\n"
                    f"# Trajectory: {trajectory}\n\n"
                    f"# Skill Library: {skill_library}\n\n"
                    f"# Specific-step: {step}"
                ))
            ]

            retry = 0
            while retry < self.max_retries:
                try:
                    response = await self.llm.ainvoke(
                        messages=messages,
                        regex_extractor=self._extract_skills_from_response,
                        **kwargs
                    )

                    skills = self._extract_skills_from_response(response)

                    if skills:
                        plan_step_metadata[step] = skills
                        # Update skill library for next iterations
                        for skill_item in skills:
                            if skill_item.get("option") in ["add", "modify"]:
                                if "skill" in skill_item:
                                    skill_library.append(skill_item["skill"])
                        break

                except Exception as e:
                    retry += 1
                    logger.error(
                        f"Error extracting skill: {e}; retry {retry}/{self.max_retries}"
                    )

        result = item.copy()
        result["plan_step_metadata"] = plan_step_metadata
        return result


class AtomicSkillExtractor(BaseSkillExtractor):
    """
    Extract atomic skills based on tool omissions.

    For each tool used in the trajectory, checks if it exists in the skill library.
    If missing (omission), extracts a new atomic skill for that tool.
    """

    def __init__(
        self,
        llm,
        benchmark: str = "tau2bench",
        domain: str = "airline",
        existing_skills: Optional[Dict[str, Dict]] = None,
        max_retries: int = 5,
        verbose: bool = True
    ):
        super().__init__(llm, benchmark, verbose=verbose)
        self.domain = domain
        self.existing_skills = existing_skills or {}
        self.max_retries = max_retries

    def get_skill_type(self) -> str:
        return "atomic"

    def get_prompt(self) -> str:
        return PromptRegistry.get("skill_extraction", "atomic")

    def _extract_skills_from_response(self, text: str) -> Optional[List[Dict]]:
        """Extract skills JSON from response."""
        match = re.search(r"```json(.*?)```", text, flags=re.S)
        if match:
            try:
                skills = json.loads(match.group(1).strip())
                return skills
            except json.JSONDecodeError:
                pass
        if self.verbose:
            logger.warning("No valid skills JSON found in response")
        return None

    def _collect_tools_from_trajectory(self, trajectory: List[Dict]) -> Set[str]:
        """Collect all tools used in a trajectory."""
        tools = set()
        for step in trajectory:
            if step.get("role") == "assistant" and step.get("tool_calls"):
                for tool_call in step["tool_calls"]:
                    tools.add(tool_call["name"])
        return tools

    def _get_missing_tools(self, used_tools: Set[str]) -> Set[str]:
        """
        Identify tools that are missing from the existing skill library.

        This is the core of omission-based extraction.
        """
        existing_tool_names = set(self.existing_skills.keys())
        return used_tools - existing_tool_names

    async def extract(
        self,
        item: Dict,
        **kwargs
    ) -> Optional[Dict]:
        """
        Extract atomic skills from a trajectory item.

        For each tool used in the trajectory:
        1. Check if it exists in skill library
        2. If missing, extract new skill (add)
        3. If exists, consider modify or keep

        Args:
            item: Dictionary with trajectory information

        Returns:
            Item with added skill extraction metadata
        """
        user_task = item.get("user_task", "")
        successful_trajectory = item.get(
            "successful_trajectory",
            item.get("trajectory", [])
        )
        failed_trajectory = item.get("failed_trajectory")

        # Get skill library context
        temp_skill_library = item.get("exp_metadata", {}).get("skills", [])

        # Collect all tools used in successful trajectory
        all_tools = self._collect_tools_from_trajectory(successful_trajectory)

        if self.verbose:
            logger.info(f"Found {len(all_tools)} tools in trajectory")

        # Identify missing tools (omissions)
        missing_tools = self._get_missing_tools(all_tools)

        if self.verbose and missing_tools:
            logger.info(f"Missing tools (omissions): {missing_tools}")

        plan_step_metadata = {}

        # Extract skill for each tool
        for tool in all_tools:
            # Build skill library context for this tool
            skill_library = []
            if tool in self.existing_skills:
                skill_library.append(self.existing_skills[tool])

            if self.verbose:
                logger.info(f"Extracting skill for tool: {tool}")

            # Build messages
            if failed_trajectory:
                messages = [
                    ("system", self.get_prompt()),
                    ("human", (
                        f"# User task: {user_task}\n\n"
                        f"# A Successful Trajectory: {successful_trajectory}\n\n"
                        f"# A Failed Trajectory: {failed_trajectory}\n\n"
                        f"# Skill Library: {skill_library}\n\n"
                        f"# Specific Tool: {tool}"
                    ))
                ]
            else:
                messages = [
                    ("system", self.get_prompt()),
                    ("human", (
                        f"# User task: {user_task}\n\n"
                        f"# A Successful Trajectory: {successful_trajectory}\n\n"
                        f"# Skill Library: {skill_library}\n\n"
                        f"# Specific Tool: {tool}"
                    ))
                ]

            retry = 0
            while retry < self.max_retries:
                try:
                    response = await self.llm.ainvoke(
                        messages=messages,
                        regex_extractor=self._extract_skills_from_response,
                        **kwargs
                    )

                    skills = self._extract_skills_from_response(response)

                    if skills:
                        plan_step_metadata[tool] = skills
                        # Update existing skills for subsequent extractions
                        for skill_item in skills:
                            if skill_item.get("option") in ["add", "modify"]:
                                if "skill" in skill_item:
                                    skill_data = skill_item["skill"]
                                    self.existing_skills[skill_data["name"]] = skill_data
                        break

                except Exception as e:
                    retry += 1
                    logger.error(
                        f"Error extracting skill for {tool}: {e}; "
                        f"retry {retry}/{self.max_retries}"
                    )

        result = item.copy()
        result["plan_step_metadata"] = plan_step_metadata
        result["all_tools_used"] = list(all_tools)
        result["missing_tools"] = list(missing_tools)
        return result


def collect_skills_from_results(
    extraction_results: List[Dict],
    skill_type: str = "functional"
) -> List[Dict]:
    """
    Collect all extracted skills from extraction results.

    Args:
        extraction_results: List of extraction result dictionaries
        skill_type: Type of skills ('functional' or 'atomic')

    Returns:
        List of skill dictionaries with option and skill data
    """
    all_skills = []

    for result in extraction_results:
        if not result or "plan_step_metadata" not in result:
            continue

        for key, skill_items in result["plan_step_metadata"].items():
            for item in skill_items:
                try:
                    if item.get("option") == "add":
                        all_skills.append(item)
                    elif item.get("option") == "modify":
                        # Remove original skill and add modified version
                        all_skills = [
                            s for s in all_skills
                            if s.get("skill", {}).get("name") != item.get("modified_from")
                        ]
                        all_skills.append(item)
                except Exception as e:
                    logger.error(f"Error processing skill item: {e}")

    return all_skills


def prepare_skills_for_clustering(
    skills: List[Dict]
) -> List[Dict]:
    """
    Prepare skills for clustering by adding embedding text.

    Args:
        skills: List of skill dictionaries

    Returns:
        List of skills with embedding_text added
    """
    prepared = []
    for item in skills:
        if "skill" not in item:
            continue

        skill = item["skill"]
        prepared_item = item.copy()
        prepared_item["embedding_text"] = (
            f"{skill.get('name', '')}\n"
            f"{skill.get('document', '')}\n"
            f"{skill.get('content', '')}"
        )

        # Clean content - remove return statements for functional skills
        if "return" in skill.get("content", ""):
            skill["content"] = skill["content"].split("return")[0].strip()

        prepared.append(prepared_item)

    return prepared
