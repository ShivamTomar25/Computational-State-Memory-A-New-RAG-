# CSM v2 vs CSM v3 Per-Question Diagnosis

This is an offline forensic analysis. It uses stored CSM v2 artifacts and stored CSM v3 experiment rows only.

## Validation

- New LLM calls: `0`
- Patients: `3`
- Questions: `60`
- CSM v3 completed turns: `60`

## Failure Categories

- `NO_REGRESSION_DETECTED`: 23
- `OVER_PRUNING`: 23
- `INSUFFICIENT_LINEAGE`: 21
- `SERIALIZATION_INFORMATION_LOSS`: 12
- `MISSING_EVIDENCE_FALLBACK`: 9
- `TEMPORAL_ERROR`: 7
- `CORRECTION_ERROR`: 6
- `STATE_UPDATE_ERROR`: 2
- `ROUTE_ERROR`: 1

## Notes

- CSM v3 route/candidate counts come from persisted `activation_audit` events when available.
- CSM v2 route values come from persisted `query_route` events when available, otherwise the deterministic v2 router is replayed over the stored question text.
- CSM v2 selected candidate details are limited to the frozen activation audit rows; discarded candidates were not exported in the v2 offline artifacts.
