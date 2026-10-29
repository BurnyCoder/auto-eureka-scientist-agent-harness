"""Serializable run options; .env is configuration, CLI login owns credentials."""
from dataclasses import asdict, dataclass
from pathlib import Path
import os

from dotenv import dotenv_values


@dataclass
class RunConfig:
    project: str
    backend: str
    model: str = ''
    mode: str = 'cycle'
    max_minutes: float | None = None
    max_calls: int | None = None
    max_cycles: int | None = None
    profile: str = 'research'
    publish: bool = True
    owner: str = ''
    repository: str = ''
    executable: str = ''
    reasoning: str = 'high'

    def __post_init__(self):
        self.project = str(Path(self.project).resolve())
        if self.backend not in ('claude', 'codex'):
            raise ValueError('backend must be claude or codex')
        self.model = self.model or {'claude':'haiku', 'codex':'gpt-6-luna'}[self.backend]
        if self.mode not in ('cycle', 'continuous', 'budget'):
            raise ValueError('mode must be cycle, continuous, or budget')
        for key in ('max_minutes', 'max_calls', 'max_cycles'):
            if (value := getattr(self, key)) is not None and value <= 0:
                raise ValueError(f'{key} must be positive')
        if self.mode == 'budget' and self.max_minutes is None and self.max_calls is None:
            raise ValueError('budget mode requires max_minutes or max_calls')
        if self.profile not in ('research', 'digits'):
            raise ValueError('unknown profile')
        if self.profile == 'digits':
            allowed = self.model == 'gpt-6-luna' if self.backend == 'codex' else (
                self.model == 'haiku' or self.model.startswith('claude-haiku-'))
            if not allowed:
                raise ValueError('digits validation permits only Haiku or Luna')
            self.max_minutes = 60 if self.max_minutes is None else self.max_minutes
            self.max_calls = 20 if self.max_calls is None else self.max_calls
            if self.max_minutes > 60 or self.max_calls > 20:
                raise ValueError('digits validation is capped at 60 minutes and 20 calls')

    def to_dict(self):
        return asdict(self)


def environment(project: Path) -> dict:
    """Read project .env without changing the parent process environment.

    python-dotenv: https://bbc2.github.io/python-dotenv/#load-configuration-without-altering-the-environment
    """
    return {**dotenv_values(project / '.env'), **os.environ}

