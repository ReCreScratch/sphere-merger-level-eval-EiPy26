"""Manual demo: watch random/greedy/lookahead play all three baseline
levels side by side. Each cell replays a precomputed shot sequence -- Reset
restarts every cell from the top.
"""

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.random_agent import RandomAgent
from sphere_merger.agents.runner import record_shots
from sphere_merger.game.baseline_levels import BASELINE_LEVELS
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

AGENTS = {
    "random": RandomAgent(seed=0),
    "greedy": GreedyAgent(),
    "lookahead": LookaheadAgent(),
}

CELLS = {
    f"{level_name} / {agent_name}": (level, record_shots(level, agent))
    for level_name, level in BASELINE_LEVELS.items()
    for agent_name, agent in AGENTS.items()
}

if __name__ == "__main__":
    run_agent_grid(
        CELLS,
        columns=len(AGENTS),
        render_config=RenderConfig(window_size=(1200, 900)),
    )
