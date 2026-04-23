from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PathExists = Callable[[str], bool]

EXECUTABLE_ENV_VARS = (
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
    "CHROME_EXECUTABLE",
    "CHROMIUM_PATH",
)

SYSTEM_BROWSER_CANDIDATES = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
)


@dataclass(frozen=True)
class BrowserStatus:
    available: bool
    executable_path: str | None
    source: str
    message: str


def _first_existing_path(candidates: Iterable[str], path_exists: PathExists) -> str | None:
    for candidate in candidates:
        if candidate and path_exists(candidate):
            return candidate
    return None


def _playwright_cache_candidates(home: str) -> tuple[str, ...]:
    normalized_home = home.rstrip("/\\")
    return (
        f"{normalized_home}/.cache/ms-playwright",
        f"{normalized_home}/AppData/Local/ms-playwright",
    )


def detect_browser_status(
    env: dict[str, str] | None = None,
    path_exists: PathExists | None = None,
    home: str | None = None,
) -> BrowserStatus:
    env = env or dict(os.environ)
    path_exists = path_exists or (lambda path: Path(path).exists())
    home = home or str(Path.home())

    configured_paths = [env.get(name, "") for name in EXECUTABLE_ENV_VARS]
    executable_path = _first_existing_path(configured_paths, path_exists)
    if executable_path:
        return BrowserStatus(
            available=True,
            executable_path=executable_path,
            source="env",
            message=f"Using configured Chromium executable: {executable_path}",
        )

    executable_path = _first_existing_path(SYSTEM_BROWSER_CANDIDATES, path_exists)
    if executable_path:
        return BrowserStatus(
            available=True,
            executable_path=executable_path,
            source="system",
            message=f"Using system Chromium executable: {executable_path}",
        )

    cache_path = _first_existing_path(_playwright_cache_candidates(home), path_exists)
    if cache_path:
        return BrowserStatus(
            available=True,
            executable_path=None,
            source="playwright-cache",
            message=f"Using Playwright browser cache: {cache_path}",
        )

    return BrowserStatus(
        available=False,
        executable_path=None,
        source="missing",
        message=(
            "No Chromium runtime detected. Install a browser before launch or "
            "configure PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH."
        ),
    )


def get_launch_kwargs(status: BrowserStatus) -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True}
    if status.executable_path:
        kwargs["executable_path"] = status.executable_path
    return kwargs
