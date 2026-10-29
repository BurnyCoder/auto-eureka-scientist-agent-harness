# Research contracts

Each cycle contains `research/`, `results/`, `reports/`, `models/`, `figures/`, and `docs/`. Handoff paths are project-relative; checklist paths may be cycle-relative. The phase prompt lists required files and required ledger fields. `eureka verify` rechecks accepted phase outputs against current files.

The strict handoff records status, summary, artifacts, evidence, issues, research stage, exploratory/confirmatory classification, objective, predictions, competing alternatives, observations, learning, rationale, continuation/backedge, and explained inapplicability. These fields implement reflection inside an existing phase call. A structurally valid handoff alone is not accepted completion.

Protocols have a question, analysis plan, data boundaries, and budget. Exploratory protocols add an objective and measurements. Confirmatory protocols require hypotheses with alternatives and distinguishing predictions, a primary metric, methods, seeds, and falsification criteria. The controller commits and records the protocol hash before results. It never rewrites the prior registration; protocol-history copies remain.

Experiment JSON includes ID, method, analysis kind, start time, protocol hash, and the applicable measurements. Accuracy requires aligned saved true labels and predictions; it is recomputed. Split IDs must be disjoint. The supplied study also records code/data/checkpoint hashes, seed, device and hardware, package versions, trajectory, configuration, checkpoint reload checks, expected observations and limitations.

The loader treats JSON objects declaring `id` or `method` as experiment records and validates their remaining fields. Auxiliary aggregate JSON is retained but never becomes another sample in the primary calculation. The digits profile separately requires every registered arm/seed record. Put derived analyses under `research/` or `reports/` for clarity. A zero-width bootstrap interval with no observed discordances is explicitly flagged; it does not establish equivalence on unseen examples.

Public clones can run `eureka render --project <clone>` without private SQLite state. `verify` uses the public decision history when no local run exists; it still reports missing checkpoint artifacts until those are downloaded from the model bundle. `run`, `resume`, `status`, and `stop` operate on local run state.

Claims cite source/experiment IDs and disclose limitations. A confirmatory claim cannot use an exploratory experiment as confirmation. Prior source evidence is distinguishable from current measurements by ledger membership. Mathematical validity, causal attribution, implementation semantics, and source support still need substantive review. Checks detect specific contradictions and omissions; they do not make arbitrary agent text scientifically true.

Local code and audit artifacts can be cited through `research/evidence.json`: an array of `{id,path,sha256,analysis_kind}` with project-relative paths. The verifier checks file existence, content hashes, unique IDs and exploratory/confirmatory compatibility. Post-hoc derived analyses and audits remain exploratory. This ledger does not infer scientific support from file existence.

The source ledger records title, URL, summary, license, and access time. Independent HTTP retrieval records timestamps and content-prefix hashes. A blocked source needs an explicit access limitation; at least one source must be independently retrievable. Do not treat URL existence as proof that a citation supports the claim.

The requirement checklist covers every original policy section. Satisfied entries cite existing evidence. Not-applicable entries explain why, including no trained model, no reward objective, or an unavailable causal intervention. Generated numerical sections come only from result files; authored interpretation should reference evidence IDs without manually copying scores.

## Neel Nanda integration

[The research-process series](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL) is guidance, not empirical validation of this harness.

- [Stages](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL/p/hjMy4ZxS5ogA9cTYK): exploratory questions, anomalies and highlights can precede mature hypotheses; return to earlier stages when needed.
- [Mindsets](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL/p/cbBwwm4jW6AZctymL): actively test bugs, leakage, confounders and simpler explanations; prioritize informative cheap experiments and review switching costs.
- [Research taste](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL/p/Ldrss6o3tiKT6NdMm): compare prior predictions with observations, learn from decisions, inspect pivotal experiments in earlier work.
- [Writing](https://www.alignmentforum.org/s/5GT3yoYM9gRmMEKqL/p/eJGptPbbFPZGLpjsp): distill a few precise claims early, develop an outline and figures, and let missing support reopen research.
