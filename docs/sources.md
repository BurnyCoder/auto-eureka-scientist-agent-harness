# Source and license review

Sources were inspected before implementation. This is a focused engineering/research-process review, not an exhaustive systematic literature review. No external implementation was copied. Standard library and installed-library APIs are linked in the modules that use them.

| Source | Relevant observation and use | Reuse/license decision |
|---|---|---|
| [Anthropic: effective harnesses](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) | Durable progress artifacts, incremental tasks and explicit verification motivate fresh-context phases | Conceptual reference; no article/code reproduction |
| [Ralph](https://github.com/madhavajay/ralph) | Provider process abstraction and iterative harness; inspected provider and harness source | Apache-2.0; architectural comparison only |
| [ralphex](https://github.com/umputun/ralphex) | Repeated CLI execution, logging and review loops | MIT; comparison only |
| [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2) | Automated experiment/research artifact workflow | Its [custom license](https://github.com/SakanaAI/AI-Scientist-v2/blob/main/LICENSE) was inspected; no code copied |
| [autoresearch](https://github.com/karpathy/autoresearch) | Small bounded experiment loops | No applicable license established in this review; no code copied |
| [Neel Nanda series](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL) | Ideation, exploration, understanding, distillation; skepticism and research judgment | Paraphrased process guidance, linked in prompts |
| [Lones: ML pitfalls](https://arxiv.org/abs/2108.02497) | Leakage, evaluation and methodological care | Scientific reference |
| [Lipton and Steinhardt](https://arxiv.org/abs/1807.03341) | Separate evidence from speculation and avoid overclaiming | Scientific reference |
| [NeurIPS checklist](https://neurips.cc/public/guides/PaperChecklist) | Claims, limitations, reproducibility and uncertainty | Checklist guidance |
| [Schulman guide](http://joschu.net/blog/opinionated-guide-ml-research.html) | Concrete empirical questions and simple initial experiments | Process reference |
| [Karpathy PhD guide](https://karpathy.github.io/2016/09/07/phd/) | Iteration, research judgment and communication | Process reference |
| [Claude CLI](https://code.claude.com/docs/en/cli-reference), [headless](https://code.claude.com/docs/en/headless), [model configuration](https://code.claude.com/docs/en/model-config), [environment](https://code.claude.com/docs/en/env-vars) | Print/stream JSON, schema output, sandbox settings, model and helper-model configuration | CLI interface use |
| [Codex CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli), [noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode) | Exec JSONL, schemas, model selection and native unrestricted flag; local installed help cross-checked | CLI interface use |
| [asyncio subprocess](https://docs.python.org/3/library/asyncio-subprocess.html), [SQLite](https://docs.python.org/3/library/sqlite3.html), [psutil](https://psutil.readthedocs.io/) | Concurrent pipe draining, transactions, process ownership | Library API use |
| [scikit-learn digits](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html), [pitfalls](https://scikit-learn.org/stable/common_pitfalls.html), [UCI](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits) | Data shape/pixel range and train/held-out separation | Dataset attribution: UCI CC BY 4.0; sklearn BSD-3-Clause |
| [AdamW](https://docs.pytorch.org/docs/stable/generated/torch.optim.AdamW.html), [safetensors](https://huggingface.co/docs/safetensors/en/api/torch) | Optimizer and checkpoint serialization APIs | Library API use, no copied training implementation |
| [uv PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/) | Explicit CUDA wheel source separate from PyPI | Configuration pattern |
| [Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [HF CLI](https://huggingface.co/docs/huggingface_hub/guides/cli), [Pandoc](https://pandoc.org/MANUAL.html#creating-a-pdf) | Publication and paper generation | Documented tool interfaces |

No Kaggle/Hugging Face implementation was needed for a dataset already bundled with scikit-learn. HF is used for versioned checkpoint publication. Reviews of community discussions did not provide stronger evidence than the maintained primary documentation for the CLI interfaces; changing product behavior is checked against local help and actual trial output.
