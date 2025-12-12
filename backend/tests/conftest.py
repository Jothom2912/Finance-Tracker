"""
Pytest configuration file.
This file ensures that the backend module can be imported correctly.
"""
import sys
from pathlib import Path

# Add the parent directory (project root) to Python path
# This allows imports like "from backend.shared.schemas.account import ..."
# When running from backend/ directory, we need to add parent (project root)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
