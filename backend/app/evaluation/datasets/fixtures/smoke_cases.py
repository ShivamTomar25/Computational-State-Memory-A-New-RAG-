from __future__ import annotations


SMOKE_DATASET = {
    "name": "sustha_memory_smoke",
    "version": "2026.07.20",
    "split": "development",
    "description": "Small synthetic smoke dataset for evaluation pipeline validation.",
    "cases": [
        {
            "case_key": "smoke_condition_progression",
            "scenario_family": "condition_progression",
            "seed": 101,
            "manifest": {
                "patient_code": "EVAL-SMOKE-001",
                "events": [
                    {
                        "sequence_number": 1,
                        "event_type": "condition",
                        "valid_time": "2026-01-01T09:00:00+00:00",
                        "ingestion_time": "2026-01-01T10:00:00+00:00",
                        "payload": {
                            "name": "Type 2 diabetes mellitus",
                            "clinical_status": "active",
                            "verification_status": "confirmed",
                            "notes": "A1c monitoring required.",
                        },
                    }
                ],
                "questions": [
                    {
                        "turn_number": 1,
                        "question": "What is the current diabetes status?",
                        "question_type": "current_state",
                        "expected_decision_type": "current_state_active",
                        "source_cutoff": "2026-01-01T10:00:00+00:00",
                        "truth": {
                            "answer_summary": "Type 2 diabetes is active.",
                            "claims": [
                                {
                                    "claim_id": "gt-001",
                                    "subject": "type 2 diabetes mellitus",
                                    "predicate": "clinical_status",
                                    "value": "active",
                                    "status": "active",
                                    "relevant_source_ids": ["event-1"],
                                }
                            ],
                            "decision_labels": ["current_state_active"],
                            "relevant_source_ids": ["event-1"],
                        },
                    }
                ],
            },
        },
        {
            "case_key": "smoke_medication_change",
            "scenario_family": "medication_dose_change",
            "seed": 102,
            "manifest": {
                "patient_code": "EVAL-SMOKE-002",
                "events": [
                    {
                        "sequence_number": 1,
                        "event_type": "medication",
                        "valid_time": "2026-02-01T09:00:00+00:00",
                        "ingestion_time": "2026-02-01T10:00:00+00:00",
                        "payload": {
                            "medication_name": "Metformin",
                            "dosage_value": "500",
                            "dosage_unit": "mg",
                            "frequency": "twice daily",
                            "medication_status": "active",
                        },
                    }
                ],
                "questions": [
                    {
                        "turn_number": 1,
                        "question": "What medication plan is currently supported?",
                        "question_type": "current_medication",
                        "expected_decision_type": "evidence_sufficient",
                        "source_cutoff": "2026-02-01T10:00:00+00:00",
                        "truth": {
                            "answer_summary": "Metformin 500 mg twice daily is active.",
                            "claims": [
                                {
                                    "claim_id": "gt-002",
                                    "subject": "metformin",
                                    "predicate": "dose",
                                    "value": "500 mg twice daily",
                                    "status": "active",
                                    "relevant_source_ids": ["event-1"],
                                }
                            ],
                            "decision_labels": ["evidence_sufficient"],
                            "relevant_source_ids": ["event-1"],
                        },
                    }
                ],
            },
        },
        {
            "case_key": "smoke_allergy_discovery",
            "scenario_family": "allergy_discovery",
            "seed": 103,
            "manifest": {
                "patient_code": "EVAL-SMOKE-003",
                "events": [
                    {
                        "sequence_number": 1,
                        "event_type": "allergy",
                        "valid_time": "2026-03-01T09:00:00+00:00",
                        "ingestion_time": "2026-03-01T10:00:00+00:00",
                        "payload": {
                            "substance": "Penicillin",
                            "clinical_status": "active",
                            "verification_status": "confirmed",
                            "reaction": "Rash",
                            "severity": "mild",
                        },
                    }
                ],
                "questions": [
                    {
                        "turn_number": 1,
                        "question": "Does the patient have an active allergy?",
                        "question_type": "current_allergy",
                        "expected_decision_type": "evidence_sufficient",
                        "source_cutoff": "2026-03-01T10:00:00+00:00",
                        "truth": {
                            "answer_summary": "Penicillin allergy is active with rash reaction.",
                            "claims": [
                                {
                                    "claim_id": "gt-003",
                                    "subject": "penicillin",
                                    "predicate": "allergy_status",
                                    "value": "active",
                                    "status": "active",
                                    "relevant_source_ids": ["event-1"],
                                }
                            ],
                            "decision_labels": ["evidence_sufficient"],
                            "relevant_source_ids": ["event-1"],
                        },
                    }
                ],
            },
        },
    ],
}
