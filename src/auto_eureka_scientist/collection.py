"""Discover the tracked Hub destination across nested research repositories.

Collection slugs and item identities: https://huggingface.co/docs/huggingface_hub/guides/collections
"""
from pathlib import Path
import re
from tempfile import TemporaryDirectory


MARKER = '.eureka-collection'


def project_collection(project: Path) -> str:
    """Read the project and its ancestors so a child Git repository inherits its parent's slug."""
    project = project.resolve()
    slug = ''
    for directory in (project, *project.parents):
        marker = directory / MARKER
        try:
            value = marker.read_text(encoding='utf-8-sig').strip()
        except FileNotFoundError:
            continue
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', value, flags=re.ASCII):
            raise ValueError(f'{marker} must contain one Hugging Face collection slug (owner/name)')
        if slug and value != slug:
            raise ValueError(f'Project collection {slug} conflicts with {value} in {marker}')
        slug = value
    return slug


def resolve_collection(project: Path, requested: str) -> str:
    """An explicit setting can confirm a tracked destination or select one in an independent project."""
    pinned = project_collection(project)
    if pinned and requested and requested != pinned:
        raise ValueError(f'Hugging Face collection {requested} conflicts with the project collection {pinned}')
    return pinned or requested


def inherit_collection(project: Path):
    """Make an inherited slug portable on clone, publishing the file with an atomic rename."""
    slug = project_collection(project)
    marker = project / MARKER
    if slug and not marker.exists():
        # Stage on the same filesystem under the ignored runtime directory.
        with TemporaryDirectory(dir=project / '.eureka') as staging:
            pending = Path(staging) / MARKER
            pending.write_text(slug + '\n', encoding='utf-8', newline='\n')
            pending.replace(marker)
