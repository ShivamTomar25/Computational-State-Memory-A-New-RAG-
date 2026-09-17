# CSM v3 Evaluation Compatibility Changes

- Added deterministic citation alias resolution for CSM v3 presentation IDs such as C1/C2 to canonical source IDs.
- Reused the existing offline observation evaluator for claim matching, support classification, temporal/correction/state metrics, activation metrics, cost, tokens, and latency.
- Preserved frozen baseline artifacts and live CSM v3 metric rows as historical data.
- Created only derived offline evaluator-compatible result artifacts.
- No answer text, patient data, benchmark question, ground truth, retrieval behavior, or metric formula is modified.
