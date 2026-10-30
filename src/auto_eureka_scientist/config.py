"""Serializable run options; .env is configuration, CLI login owns credentials."""
from dataclasses import asdict, dataclass
from pathlib import Path
import os

from dotenv import dotenv_values
from .settings import setting as s, validate


@dataclass
class RunConfig:
    project: str = s(description='Research project directory; all artifacts belong to this project.')
    backend: str = s(description='Authenticated coding CLI used for every invocation.',choices=['claude','codex'])
    model: str = s('',description='Model identifier. An empty value selects the backend default.')
    mode: str = s('cycle',description='One cycle, repeating cycles, or budget-bounded execution.',choices=['cycle','continuous','budget'],apply='immediate')
    max_minutes: float | None = s(None,kind=['number','null'],minimum=0.001,description='Total active minutes, including chat and retries; null means no general-profile limit.',apply='immediate')
    max_calls: int | None = s(None,kind=['integer','null'],minimum=1,description='Total charged CLI calls across all cycles and chat.',apply='immediate')
    max_cycles: int | None = s(None,kind=['integer','null'],minimum=1,description='Maximum started cycles, including abandoned revisions.',apply='immediate',advanced=True)
    max_loops: int | None = s(None,kind=['integer','null'],minimum=1,description='Maximum completed eight-phase loops; independent of started cycles.',apply='immediate')
    profile: str = s('research',description='Research verification profile.',choices=['research','digits','digits-replication'])
    publish: bool = s(True,description='Publish through authenticated GitHub and Hugging Face CLIs; false keeps local checkpoints.',category='Publication')
    owner: str = s('',description='GitHub/Hugging Face owner; empty uses the authenticated account.',category='Publication')
    repository: str = s('',description='GitHub repository name; empty uses the project name.',category='Publication')
    executable: str = s('',description='CLI executable path; empty discovers the selected backend on PATH.',advanced=True)
    reasoning: str = s('high',description='Codex reasoning or Claude effort for future calls.',choices=['low','medium','high','xhigh','max'],apply='next invocation')
    hf_collection: str = s('',description='Existing Hugging Face collection slug for model uploads.',category='Publication')
    model_pin: str = s('',description='Resolved Claude model identifier, including background helpers. Codex uses its exact model field.',backends=['claude'])
    invocation_timeout: float | None = s(None,kind=['number','null'],minimum=.1,description='Seconds allowed for one CLI call; bounded by remaining run time.',category='Execution',scope='cycle',apply='next invocation')
    no_output_timeout: float | None = s(None,kind=['number','null'],minimum=.1,description='Seconds without CLI stdout/stderr before interrupting; disabled by default.',category='Execution',scope='cycle',apply='next invocation',advanced=True)
    queue_order: str = s('ordered',description='Choose specs in listed order or a recorded seeded shuffle.',choices=['ordered','shuffle'],category='Queue',apply='next cycle')
    queue_seed: int = s(0,description='Seed for queue ordering, not a model training seed.',category='Queue',apply='next cycle')
    queue_start: int = s(0,minimum=0,description='Zero-based starting enabled spec for a new queue.',category='Queue')
    cycle_delay: float = s(0.0,minimum=0,description='Active seconds to wait between completed loops.',category='Queue',apply='next cycle')
    failure_policy: str = s('pause',description='After bounded repairs, pause or skip the incomplete spec.',choices=['pause','skip'],category='Recovery',apply='immediate')
    repair_retries: int = s(2,minimum=0,description='Additional artifact-repair attempts per phase invocation.',category='Recovery',scope='cycle',apply='next invocation')
    transport_retries: int = s(2,minimum=0,description='Additional transient transport retries.',category='Recovery',scope='cycle',apply='next invocation')
    retry_delay: float = s(2.0,minimum=0,description='Initial retry delay in active seconds.',category='Recovery',scope='cycle',apply='next invocation')
    retry_multiplier: float = s(2.0,minimum=1,description='Exponential retry-delay multiplier.',category='Recovery',scope='cycle',apply='next invocation',advanced=True)
    retry_max: float = s(30.0,minimum=0,description='Maximum retry delay in seconds.',category='Recovery',scope='cycle',apply='next invocation',advanced=True)
    no_progress_passes: int = s(1,minimum=1,description='Queue passes without a completed loop before pausing.',category='Recovery',apply='immediate')
    termination_grace: float = s(2.0,minimum=0,maximum=30,description='Seconds between owned-process termination and forced kill.',category='Recovery',apply='next invocation',advanced=True)
    pause_before: list[str] = s([],description='Pause before these phases; resume crosses the current pause once.',items={'enum':['research','preregister','core','pilot','experiments','analysis','review','publish']},category='Intervention',scope='cycle',apply='next invocation')
    pause_before_publication: bool = s(False,description='Pause before core, pilot or final publication.',category='Intervention',scope='cycle',apply='next invocation')
    stop_after: str = s('',choices=['','phase','cycle'],description='Stop resumably at the next selected boundary.',category='Intervention',apply='immediate')
    message_mode: str = s('steer',choices=['ask','steer'],description='Default chat composer mode.',category='Intervention',apply='immediate')
    delivery: str = s('next_turn',choices=['next_turn','interrupt_now'],description='Default message delivery timing.',category='Intervention',apply='immediate')
    message_scope: str = s('next_invocation',choices=['next_invocation','cycle','run'],description='Default steering lifetime.',category='Intervention',apply='immediate')
    history_cycles: int = s(5,minimum=0,description='Recent cycle summaries included in each prompt; full history stays on disk.',category='Context',scope='cycle',apply='next invocation')
    history_chars: int = s(24000,minimum=0,description='Maximum characters of prior-cycle summaries in prompts.',category='Context',scope='cycle',apply='next invocation')
    chat_history_chars: int = s(12000,minimum=0,description='Maximum recent chat-context characters; full messages remain stored.',category='Context',scope='cycle',apply='next invocation')
    pinned_instructions: str = s('',description='Persistent operator instructions, appended without changing canonical policy.',category='Context',scope='cycle',apply='next invocation')
    artifact_references: list[str] = s([],description='Project-relative artifact paths to reference in future prompts.',category='Context',scope='cycle',apply='next invocation')
    command_timeout: float = s(120.0,minimum=.1,description='Seconds allowed for core verification commands.',category='Execution',scope='cycle',apply='next invocation')
    publication_timeout: float = s(180.0,minimum=.1,description='Seconds allowed per publication command.',category='Publication',apply='next invocation',advanced=True)
    render_timeout: float = s(180.0,minimum=.1,description='Seconds allowed for paper rendering.',category='Publication',apply='next invocation')
    ci_timeout: float = s(180.0,minimum=.1,description='Maximum seconds waiting for published CI checks.',category='Publication',apply='next invocation',advanced=True)
    ci_poll_seconds: float = s(5.0,minimum=.1,description='Interval between remote CI status checks.',category='Publication',apply='next invocation',advanced=True)
    preview_format: str = s('png',choices=['png','svg'],description='Format for additional exported research figures; required PNG artifacts remain.',category='Publication',apply='next invocation')
    figure_dpi: int = s(160,minimum=72,maximum=600,description='Resolution of rendered research figures.',category='Publication',apply='next invocation')
    heartbeat_seconds: float = s(1.0,minimum=.1,maximum=30,description='Interval persisting active time; bounds crash-time accounting loss.',category='Observability',apply='immediate',advanced=True)
    telemetry_seconds: float = s(2.0,minimum=.5,description='Interval sampling process and machine telemetry.',category='Observability',apply='immediate')
    cpu_monitor: bool = s(True,description='Sample owned-process CPU and RAM.',category='Observability',apply='immediate')
    gpu_monitor: bool = s(True,description='Sample machine GPU utilization and VRAM when nvidia-smi is available.',category='Observability',apply='immediate')
    stream_batch_ms: int = s(100,minimum=20,maximum=5000,description='Event-stream polling/batching interval in milliseconds.',category='Observability',apply='immediate',advanced=True)
    log_filter: str = s('all',choices=['all','agent','stderr','control','publication'],description='Default activity-stream category filter.',category='Observability',apply='immediate')
    history_page_size: int = s(200,minimum=20,maximum=2000,description='Events per history page and maximum visible activity entries.',category='Observability',apply='immediate')
    timezone: str = s('local',description='IANA display timezone or local; stored timestamps always use UTC.',category='Observability',apply='immediate')
    show_timestamps: bool = s(True,description='Show event and message timestamps.',category='Interface',apply='immediate')
    notification_events: list[str] = s(['blocked','complete','budget_exhausted'],description='Run statuses that trigger enabled notifications.',items={'enum':['blocked','complete','budget_exhausted','paused','stopped','interrupted']},category='Observability',apply='immediate')
    cost_warning_usd: float | None = s(None,kind=['number','null'],minimum=0,description='Warning threshold for reported provider cost, not a billing guarantee or hard cap.',category='Observability',apply='immediate')
    theme: str = s('system',choices=['system','dark','light'],description='Console color theme.',category='Interface',apply='immediate')
    density: str = s('comfortable',choices=['comfortable','compact'],description='Console spacing.',category='Interface',apply='immediate')
    font_size: int = s(14,minimum=11,maximum=24,description='Base console font size in pixels.',category='Interface',apply='immediate')
    panels: list[str] = s(['queue','details'],description='Visible side panels.',items={'enum':['queue','details']},category='Interface',apply='immediate')
    queue_width: int = s(240,minimum=180,maximum=480,description='Queue panel width in pixels.',category='Interface',apply='immediate')
    details_width: int = s(360,minimum=240,maximum=700,description='Details panel width in pixels.',category='Interface',apply='immediate')
    detail_tab: str = s('activity',choices=['activity','artifacts','diff','settings'],description='Default details tab.',category='Interface',apply='immediate')
    auto_scroll: bool = s(True,description='Follow new chat and activity entries.',category='Interface',apply='immediate')
    send_key: str = s('ctrl_enter',choices=['ctrl_enter','enter'],description='Keyboard shortcut for sending chat.',category='Interface',apply='immediate')
    sound: bool = s(False,description='Play a short tone for selected status notifications.',category='Interface',apply='immediate')
    browser_notifications: bool = s(False,description='Use browser notifications after the user grants browser permission.',category='Interface',apply='immediate')
    port: int = s(8765,minimum=1024,maximum=65535,description='Local console HTTP port.',category='Interface',apply='server restart')
    open_browser: bool = s(True,description='Open the local console automatically on server launch.',category='Interface',apply='server restart')

    def __post_init__(self):
        self.project = str(Path(self.project).resolve())
        validate(self.to_dict())
        if self.backend not in ('claude', 'codex'):
            raise ValueError('backend must be claude or codex')
        self.model = self.model or {'claude':'haiku', 'codex':'gpt-6-luna'}[self.backend]
        if self.backend=='codex' and self.model_pin:
            raise ValueError('Codex uses an exact model identifier; model_pin is only supported by Claude')
        if self.model_pin and self.model_pin!=self.model:
            if not (self.backend=='claude' and self.model in ('haiku','sonnet','opus') and
                    self.model_pin.startswith(f'claude-{self.model}-')):
                raise ValueError('model pin must identify the selected model or its Claude alias family')
        if self.mode not in ('cycle', 'continuous', 'budget'):
            raise ValueError('mode must be cycle, continuous, or budget')
        for key in ('max_minutes', 'max_calls', 'max_cycles'):
            if (value := getattr(self, key)) is not None and value <= 0:
                raise ValueError(f'{key} must be positive')
        if self.mode == 'budget' and self.max_minutes is None and self.max_calls is None:
            raise ValueError('budget mode requires max_minutes or max_calls')
        if self.profile not in ('research', 'digits', 'digits-replication'):
            raise ValueError('unknown profile')
        if self.profile.startswith('digits'):
            allowed = self.model in ('gpt-6-luna','gpt-6.1-sol') if self.backend == 'codex' else (
                self.model in ('haiku','sonnet') or self.model.startswith(('claude-haiku-','claude-sonnet-')))
            if not allowed:
                raise ValueError('digits validation permits Haiku, Sonnet, Luna or the authorized GPT-6.1 Sol')
            self.max_minutes = 60 if self.max_minutes is None else self.max_minutes
            self.max_calls = 20 if self.max_calls is None else self.max_calls
            # Defaults retain the historical trial protocol; explicit user limits may extend it.

    def to_dict(self):
        return asdict(self)


def environment(project: Path) -> dict:
    """Read project .env without changing the parent process environment.

    python-dotenv: https://bbc2.github.io/python-dotenv/#load-configuration-without-altering-the-environment
    """
    return {**dotenv_values(project / '.env'), **os.environ}

