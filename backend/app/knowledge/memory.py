"""Four memory layers — the cognitive substrate for every project."""

from __future__ import annotations

MEMORY_LAYERS = (
    "project",       # relatively stable project identity & purpose
    "architecture",  # structure, deps, layers, APIs, UI surfaces
    "decision",      # why choices were made / rejected
    "execution",     # changes, tests, failures, outcomes
    "conversation",  # every retained utterance (project-isolated long-term chat memory)
)

LAYER_DESCRIPTIONS = {
    "project": "Identity, purpose, actors, capabilities, business rules",
    "architecture": "Modules, layers, APIs, coupling, design surfaces",
    "decision": "Past decisions, alternatives considered, rationale",
    "execution": "Applied changes, test results, incidents, rollbacks",
    "conversation": "Every user/agent word kept under this project only — never shared across projects",
}
