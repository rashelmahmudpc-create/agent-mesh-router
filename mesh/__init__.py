"""agent-mesh-router — একগুচ্ছ AI এজেন্টকে কাজ ভাগ করে দেওয়ার ম্যানেজার।"""

from .config import AgentSpec, MeshConfig, Settings
from .router import Router

__all__ = ["AgentSpec", "MeshConfig", "Settings", "Router"]
__version__ = "0.1.0"
