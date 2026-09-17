# CSM v4 Evaluator-Compatible Export

- Exports stored CSM v4 live answers through the existing offline evaluator path.
- Reuses frozen CSM v2/baseline artifacts and stored CSM v3 answers.
- Refuses to export unless every patient has 20 completed CSM v4 turns.
- Performs no provider calls and does not modify stored answers, ground truth, baselines, CSM v2, or CSM v3.
