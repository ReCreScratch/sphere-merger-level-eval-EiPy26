"""Headless agent-vs-level runner: repeatedly ask an agent for a shot and
play it out until the round is won or lost."""

from __future__ import annotations

from sphere_merger.agents.base import Agent
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState, play_shot, start_round


def play_round(level: LevelDefinition, agent: Agent) -> RoundState:
    """Play `level` from scratch, letting `agent` pick every shot.

    Returns the final `RoundState` once the round is won or the shot queue
    runs out.
    """
    state = start_round(level)
    while not state.is_over:
        angle, speed = agent.choose_shot(state)
        play_shot(state, angle, speed)
    return state
