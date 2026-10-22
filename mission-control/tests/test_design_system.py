import re
from pathlib import Path

STATIC = Path(__file__).parents[1] / "src/hermes_mission_control/static"
STYLES = (STATIC / "styles.css").read_text(encoding="utf-8")


def _root_tokens() -> dict[str, str]:
    root = re.search(r":root\s*\{(?P<body>.*?)\n\}", STYLES, re.DOTALL)
    assert root is not None
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", root.group("body")))


def _luminance(color: str) -> float:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_luminance(foreground), _luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_design_tokens_cover_documented_visual_foundation() -> None:
    tokens = _root_tokens()
    assert tokens["--canvas"] == "#fbfaf7"
    assert tokens["--nav"] == "#ffffff"
    assert tokens["--accent"] == "#b00020"
    assert tokens["--danger"] == "var(--red)"
    assert tokens["--blue"] == "var(--accent)"
    assert tokens["--display"].startswith('"Instrument Serif"')
    for token in (
        "--space-1",
        "--space-2",
        "--space-3",
        "--space-4",
        "--space-6",
        "--space-8",
        "--radius-control",
        "--radius-panel",
        "--motion-fast",
        "--motion-standard",
    ):
        assert token in tokens


def test_semantic_text_and_status_pairs_meet_wcag_aa() -> None:
    tokens = _root_tokens()
    pairs = (
        ("--ink", "--canvas"),
        ("--muted", "--canvas"),
        ("--quiet", "--canvas"),
        ("--accent", "--surface"),
        ("--green", "--green-soft"),
        ("--amber", "--amber-soft"),
        ("--red", "--red-soft"),
        ("--cyan", "--cyan-soft"),
    )
    for foreground, background in pairs:
        assert _contrast(tokens[foreground], tokens[background]) >= 4.5, (
            f"{foreground} on {background} fails 4.5:1"
        )


def test_keyboard_motion_and_responsive_rules_are_present() -> None:
    assert "button:focus-visible" in STYLES
    assert "input:focus-visible" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    for width in ("1180px", "960px", "680px", "620px"):
        assert f"@media (max-width: {width})" in STYLES
    assert "letter-spacing: 0" in STYLES


def test_local_brand_assets_are_bundled() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "/static/brand/logo-primary.svg" in html
    assert (STATIC / "fonts/ibm-plex-sans.woff2").is_file()
    assert (STATIC / "fonts/ibm-plex-mono.woff2").is_file()
    assert (STATIC / "fonts/instrument-serif.woff2").is_file()
