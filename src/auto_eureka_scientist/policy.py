"""One canonical policy, packaged byte-for-byte, plus explicitly cited research guidance."""
from importlib.resources import files
import hashlib
import re


def policy_bytes() -> bytes:
    return files('auto_eureka_scientist').joinpath('resources/full.txt').read_bytes()


def policy_hash() -> str:
    return hashlib.sha256(policy_bytes()).hexdigest()


def requirements() -> list[dict]:
    text = policy_bytes().decode('utf-8-sig')
    return [{'id':f'policy-{i:02d}', 'heading':heading.strip()} for i, heading in
            enumerate(re.findall(r'^## (.+)$', text, flags=re.MULTILINE), start=1)]


NEEL = '''Research process reference: https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL
Use ideation -> exploration -> understanding -> distillation, with justified returns.
Exploration gains information; do not pretend a mature hypothesis exists. Keep highlights and anomalies.
Seek alternative explanations, including ordinary bugs, leakage, and stronger simple baselines.
Before experiments record predictions that distinguish explanations and what would falsify them.
Choose informative, inexpensive probes; explain learning per unit time and switching costs.
Record project goal, subgoal, immediate objective, predictions, actual observations, and lessons.
Distill early: outline a few precise claims, then abstract, outline, introduction, figures, full draft.
Writing can expose missing evidence and reopen research. Inform, do not overclaim or hide negative results.
Exploratory findings cannot retroactively become confirmatory. Amend protocols prospectively and use
untouched evaluation data for newly developed hypotheses; otherwise label conclusions exploratory.
These are design heuristics, not a guarantee that research is correct.
'''

