"""Backward-compatible entrypoint for legal batch extraction.

Implementation moved to `legal/batch.py`.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_parent = os.path.dirname(current_dir)
if project_parent not in sys.path:
    sys.path.insert(0, project_parent)

from SkillX.legal.batch import main


if __name__ == "__main__":
    main()
