"""BFCL agent implementation."""

from typing import Dict
from ..base import BaseAgent


class BFCLAgent(BaseAgent):
    """Agent for BFCL benchmark."""

    async def step(self, observation: str) -> str:
        """Execute one agent step."""
        # TODO: Implement BFCL-specific step logic
        raise NotImplementedError

    async def run(self, task: str) -> Dict:
        """Run agent on a task."""
        # TODO: Implement full task execution
        raise NotImplementedError
