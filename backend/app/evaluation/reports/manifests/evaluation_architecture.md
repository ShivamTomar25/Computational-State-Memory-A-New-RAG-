# Sustha Evaluation Architecture

The evaluation code is isolated under `app/evaluation`.

Implemented domains:

- `datasets`: versioned synthetic fixtures, dataset tables, validation, and seeding.
- `ground_truth`: isolated ground-truth persistence that is not inserted into memory-system sources.
- `experiments`: experiment lifecycle tables, services, and progress/results APIs.
- `metrics`: 21 metric definitions in separate folders, plus pending/measured result persistence.
- `judges`: judge-run and human-review persistence.
- `statistics`: statistical result persistence.
- `exports`: export persistence and inline API export generation.
- `api`: authenticated routers split by task.

Fairness rules enforced in this phase:

- exactly seven systems are required;
- all rankings are per metric;
- pending values are not ranked;
- missing values are not converted to zero;
- scores are not fabricated before live experiment turns complete;
- ground truth remains separate from memory-system sources.

Current live-run status:

- the API prepares experiment scopes and pending metric rows;
- measured scoring requires the opt-in live runner to execute system turns and write outputs;
- full profile is blocked unless `--confirm-cost` is supplied.

Commands:

```bash
python -m app.evaluation.scripts.run_evaluation --profile smoke
python -m app.evaluation.scripts.run_evaluation --profile pilot
python -m app.evaluation.scripts.run_evaluation --profile full --confirm-cost
```

Cost source:

- Groq pricing source: `https://groq.com/pricing`
- Pricing verification date: `2026-07-20`
