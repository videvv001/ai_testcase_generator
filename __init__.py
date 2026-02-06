"""
AI Testcase Generator — internal tool for generating test cases from
requirements and specifications. Flat structure: api/, core/, services/,
schemas/, utils/, providers/, tests/.
"""
from .main import app, create_app

__all__ = ["__version__", "app", "create_app"]
__version__ = "0.1.0"
