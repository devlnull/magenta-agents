"""Read the answer of a PreToolUse hook: a JSON decision on stdout (exit 0), or a block with exit code 2."""
import json


def decision(run):
    """(decision, reason): ("deny" | "ask" | "allow" | None, text). Exit code 2 (fail closed) counts as deny."""
    if run.returncode == 2:
        return "deny", run.stderr
    try:
        out = json.loads(run.stdout or "{}").get("hookSpecificOutput", {})
    except ValueError:
        return None, ""
    return out.get("permissionDecision"), out.get("permissionDecisionReason", "")
