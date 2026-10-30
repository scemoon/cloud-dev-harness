# Plan: Block Spawn(build/solo) in Plan Mode

## Problem
Plan agent should not be able to spawn execution-type subagents (build/solo/general).

## Solution
Modify `_check_tool_permission` in `engine.py` to add granular check for Spawn tool.

## Changes

### File: `onecode/agent/engine.py`

**Location**: Around line 1383 (after the `perm == AgentPermission.ASK` check)

**Change**:
Add this block after the existing permission checks for Spawn tool when in plan mode:

```python
if name == "Spawn" and self._is_plan_mode():
    agent_type = inp.get("agent_type", "general")
    if agent_type in ("build", "solo", "general"):
        return json.dumps({
            "success": False,
            "error": f"Spawn({agent_type}) denied in plan mode. Use explore or scout for research.",
        })
```

## Verification
- Plan agent cannot spawn build/solo/general agents
- Plan agent CAN still spawn explore/scout (read-only research agents)
- Edit/Bash tools remain denied (existing behavior)
