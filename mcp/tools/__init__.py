"""
EROS MCP Server Tools Package

This package contains all MCP tool implementations organized by domain.
Tools are registered via the @mcp_tool decorator from base.py.

Version: 3.0.0 (Pipeline Supercharge)
Total Tools: 33
"""

from mcp.tools.base import mcp_tool, TOOL_REGISTRY, get_all_tools, dispatch_tool

# Import all tool modules to trigger registration
from mcp.tools import creator
from mcp.tools import caption
from mcp.tools import schedule
from mcp.tools import send_types
from mcp.tools import performance
from mcp.tools import targeting
from mcp.tools import query
from mcp.tools import volume_triggers

# Pipeline Supercharge v3.0.0 - New tool modules
from mcp.tools import prediction    # 5 tools: get_caption_predictions, save_caption_prediction, record_prediction_outcome, get_prediction_weights, update_prediction_weights
from mcp.tools import churn         # 2 tools: get_churn_risk_scores, get_win_back_candidates
from mcp.tools import experiments   # 3 tools: get_active_experiments, save_experiment_results, update_experiment_allocation

__all__ = [
    "mcp_tool",
    "TOOL_REGISTRY",
    "get_all_tools",
    "dispatch_tool",
]
