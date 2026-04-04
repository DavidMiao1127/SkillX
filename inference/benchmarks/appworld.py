"""AppWorld agent implementation."""

from typing import Dict, Optional
from ..base import BaseAgent


class AppWorldAgent(BaseAgent):
    """Agent for AppWorld benchmark."""

    async def step(self, observation: str) -> str:
        """Execute one agent step."""
        # TODO: Implement AppWorld-specific step logic
        raise NotImplementedError

    async def run(self, task: str) -> Dict:
        """Run agent on a task."""
        # TODO: Implement full task execution
        raise NotImplementedError
