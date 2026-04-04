"""τ²-Bench agent implementation."""

from typing import Dict
from ..base import BaseAgent


class Tau2BenchAgent(BaseAgent):
    """Agent for τ²-Bench benchmark."""

    async def step(self, observation: str) -> str:
        """Execute one agent step."""
        # TODO: Implement τ²-Bench-specific step logic
        raise NotImplementedError

    async def run(self, task: str) -> Dict:
        """Run agent on a task."""
        # TODO: Implement full task execution
        raise NotImplementedError
