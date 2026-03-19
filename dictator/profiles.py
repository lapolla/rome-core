"""ROME capability profiles — controls which tool modules load per session."""

CORE_MODULES = ["fs", "ws", "legion"]

PROFILES = {
    "core": CORE_MODULES,
    "drupal": CORE_MODULES + ["git", "drupal"],
    "skyrim": CORE_MODULES + ["skyrim", "desktop"],
    "orchestrate": CORE_MODULES + ["gc", "stats"],
    "full": None,  # None = load everything
}

TOOL_EXCLUDES = {
    "core": ["execute_legion", "execute_campaign", "launch_centurion", "clear_cache", "rome_submit_result"],
    "drupal": ["execute_legion", "launch_centurion", "rome_submit_result"],
    "skyrim": ["execute_legion", "launch_centurion", "rome_submit_result"],
    "orchestrate": [],
    "full": [],
}


def get_profile(name: str) -> list[str] | None:
    """Return module list for a profile, or None for 'full' (all modules).
    Raises ValueError for unknown profiles."""
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {', '.join(PROFILES)}")
    return PROFILES[name]


def get_tool_excludes(name: str) -> set[str]:
    """Return set of tool names to exclude for this profile."""
    return set(TOOL_EXCLUDES.get(name, []))
