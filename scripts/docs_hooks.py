"""Embed canonical reports without maintaining duplicate documentation."""

from pathlib import Path


def on_page_markdown(markdown, page, config, files):
    root = Path(config.config_file_path).parent
    if page.file.src_uri == "results.md":
        return markdown.replace(
            "<!-- sample-coverage -->",
            (root / "docs/sample-coverage.md").read_text(encoding="utf-8"),
        )
    if page.file.src_uri == "validation.md":
        report = (root / "VALIDATION.md").read_text(encoding="utf-8")
        # The source report's links are relative to the repository root.
        report = report.replace("](docs/", "](")
        for target in ("uv.lock", ".github/workflows/linux.yml", "LICENSE", "README.md"):
            report = report.replace(
                f"]({target})", f"]({config.repo_url}/blob/main/{target})"
            )
        return report
    return markdown
