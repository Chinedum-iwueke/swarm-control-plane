from pathlib import Path

ROOT = Path(__file__).parents[1]
STATIC = ROOT / "src/hermes_mission_control/static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
SCRIPT = (STATIC / "app.js").read_text(encoding="utf-8")
STYLES = (STATIC / "styles.css").read_text(encoding="utf-8")


def test_library_exposes_paginated_catalog_and_in_page_reader() -> None:
    for identifier in (
        "library-browser",
        "library-pagination",
        "library-reader",
        "library-reader-back",
        "library-outline",
        "library-document",
        "library-provenance",
        "library-load-more",
        "library-load-all",
    ):
        assert f'id="{identifier}"' in HTML
    assert 'role="document"' in HTML
    assert 'aria-label="Library pages"' in HTML


def test_reader_uses_access_separated_content_routes_and_bounded_ranges() -> None:
    assert "/api/knowledge/sources/${reader.kind}/" in SCRIPT
    assert 'parameters.set("unit", reader.unit)' in SCRIPT
    assert 'reader.kind === "canonical"' in SCRIPT
    assert "range.next_start" in SCRIPT
    assert "Source pagination repeated a range boundary." in SCRIPT
    assert "loadAllLibraryRanges" in SCRIPT


def test_reader_supports_outline_find_citations_and_return_context() -> None:
    assert "findInLibraryDocument" in SCRIPT
    assert "highlightLibraryText" in SCRIPT
    assert "jumpToLibraryCitation" in SCRIPT
    assert "updateLibrarySourceUrl" in SCRIPT
    assert 'url.searchParams.set("cite", citation)' in SCRIPT
    assert "state.libraryListScroll" in SCRIPT
    assert "catalog.scrollTop = state.libraryListScroll" in SCRIPT
    assert "data-line-citation" in SCRIPT
    assert "Copy citation" in SCRIPT


def test_reader_distinguishes_extracted_text_and_original_assets() -> None:
    assert "Extracted text. This is not an image of the original page." in SCRIPT
    assert "Original page unavailable" in SCRIPT
    assert "authorizedLibraryAssetUrl" in SCRIPT
    assert '/api/knowledge/assets/' in SCRIPT
    assert "Local-only content remains on this Mission Control host." in SCRIPT
    assert "source_digest" in SCRIPT
    assert "minimum_confidence" in SCRIPT


def test_reader_layout_is_responsive_and_keyboard_visible() -> None:
    assert ".library-reader-layout" in STYLES
    assert ".library-document" in STYLES
    assert ".source-line:target" in STYLES
    assert ".library-outline button:hover" in STYLES
    assert "min-height: 44px" in STYLES
    assert "@media (max-width: 860px)" in STYLES
    assert "@media (max-width: 680px)" in STYLES
