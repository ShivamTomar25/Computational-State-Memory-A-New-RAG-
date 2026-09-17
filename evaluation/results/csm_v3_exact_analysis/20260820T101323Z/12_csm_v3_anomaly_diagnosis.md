# CSM v3 Anomaly Diagnosis

## Finding

The values `answer_accuracy = 0`, `hallucination_rate = 1`, and `evidence_support_rate = 0` are true stored CSM v3 metric outputs from `evaluation_metric_results`, but they are not evidence that the answers had no retrieved support. They are caused by evaluator/output-schema incompatibility in the live aggregate metric path.

Direct evidence:

- CSM v3 stored claim rows: 120.
- Stored `source_support_status` counts in `claims_audit.csv`: `{'blank': 120}`.
- The live claim classifier treats blank `source_support_status` as unsupported unless the normalized generated claim matches a normalized ground-truth claim.
- The stored CSM v3 metric rows have `true_positive = 0` for answer accuracy in every patient, so all generated claims are false positives and all required truth claims are false negatives in that evaluator path.
- The same rows have `unsupported = generated_claims` and `supported = 0`, producing hallucination rate 1 and evidence support rate 0.
- Faithfulness/groundedness are high because they are computed from citation/context intersection, not from `source_support_status` or ground-truth claim matching.
- Citation audit shows `C1`, `C2`, etc. aliases have canonical_source_id in exported answer citations, but the live fabricated-citation metric compares aliases against canonical/context IDs without resolving the alias.

## Stored Aggregate Metric Evidence

```json
{
  "answer_accuracy": {
    "SYN-CSM-001": {
      "denominator": 39.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "precision": 0.0,
        "predicted_count": 43,
        "recall": 0.0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "true_positive": 0,
        "truth_count": 39
      },
      "numerator": 0.0,
      "value": 0.0
    },
    "SYN-CSM-002": {
      "denominator": 32.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "precision": 0.0,
        "predicted_count": 30,
        "recall": 0.0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "true_positive": 0,
        "truth_count": 32
      },
      "numerator": 0.0,
      "value": 0.0
    },
    "SYN-CSM-003": {
      "denominator": 36.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "precision": 0.0,
        "predicted_count": 47,
        "recall": 0.0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "true_positive": 0,
        "truth_count": 36
      },
      "numerator": 0.0,
      "value": 0.0
    }
  },
  "evidence_support_rate": {
    "SYN-CSM-001": {
      "denominator": 43.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "generated_claims": 43,
        "repetition_number": 1,
        "status": "measured",
        "supported": 0,
        "system_type": "csm_v3"
      },
      "numerator": 0.0,
      "value": 0.0
    },
    "SYN-CSM-002": {
      "denominator": 30.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "generated_claims": 30,
        "repetition_number": 1,
        "status": "measured",
        "supported": 0,
        "system_type": "csm_v3"
      },
      "numerator": 0.0,
      "value": 0.0
    },
    "SYN-CSM-003": {
      "denominator": 47.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "generated_claims": 47,
        "repetition_number": 1,
        "status": "measured",
        "supported": 0,
        "system_type": "csm_v3"
      },
      "numerator": 0.0,
      "value": 0.0
    }
  },
  "fabricated_citation_rate": {
    "SYN-CSM-001": {
      "denominator": 24.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "fabricated_citation_ids": [
          "C2",
          "C9",
          "C4",
          "C6",
          "C5",
          "C3",
          "C8",
          "C7",
          "C10",
          "C1",
          "C11"
        ],
        "generated_citation_ids": [
          "100e6bd9-2555-45d8-975a-227392273059",
          "2714340b-357b-40da-8320-ca5d49b38825",
          "4c1c91bf-529c-4286-84ca-8cdfbb165ef3",
          "4ccc7534-0c71-4918-a30a-3425d55a636c",
          "54fd1427-29f4-4118-a5b1-2ba777c3a0c6",
          "775bdc39-a4a1-480c-a6f2-ea6317756358",
          "7c216ab9-482a-45e1-b674-ccae87dc3241",
          "82436317-3f6d-48a5-98a1-fc7112135ff0",
          "879dce5d-3179-4280-b610-7bd2d3320872",
          "8e514baf-cccd-4501-b2ce-ed6c9aed08c6",
          "93741d05-d8a8-40c9-b965-87774b495ce1",
          "C1",
          "C10",
          "C11",
          "C2",
          "C3",
          "C4",
          "C5",
          "C6",
          "C7",
          "C8",
          "C9",
          "b36fe256-a9f3-4d54-8414-ff7324791817",
          "f4c29954-0dee-482e-a023-4b0bb58eefbe"
        ],
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "valid_context_ids": [
          "01179013-122d-467c-ba84-2f1f8debc427",
          "100e6bd9-2555-45d8-975a-227392273059",
          "144815ec-2457-4f70-906b-db11c7129c10",
          "2714340b-357b-40da-8320-ca5d49b38825",
          "3d44a964-a34f-402a-a0d4-46e9f8fe08f2",
          "4c1c91bf-529c-4286-84ca-8cdfbb165ef3",
          "4ccc7534-0c71-4918-a30a-3425d55a636c",
          "4f3333db-3165-4eda-92c3-3a26228909e8",
          "501fafdf-88fe-400c-b8fe-d49b391cc246",
          "54fd1427-29f4-4118-a5b1-2ba777c3a0c6",
          "6783c222-88d0-4316-9e5d-ef17041965b6",
          "775bdc39-a4a1-480c-a6f2-ea6317756358",
          "782865e0-919b-4ccf-8e67-6b54d03bb0e8",
          "7c216ab9-482a-45e1-b674-ccae87dc3241",
          "82436317-3f6d-48a5-98a1-fc7112135ff0",
          "879dce5d-3179-4280-b610-7bd2d3320872",
          "8e514baf-cccd-4501-b2ce-ed6c9aed08c6",
          "93741d05-d8a8-40c9-b965-87774b495ce1",
          "CHAT-P1-003",
          "CHAT-P1-004",
          "b36fe256-a9f3-4d54-8414-ff7324791817",
          "c23d39e1-9286-46a3-a956-39ee6c42831f",
          "c3d6015f-74fc-43b3-bd0f-980791933814",
          "ccb0ce3a-a3c5-46e7-89f0-8eb60ef5a5e3",
          "f1883cf3-d2d5-4728-9eca-486d26f44798",
          "f4c29954-0dee-482e-a023-4b0bb58eefbe"
        ]
      },
      "numerator": 11.0,
      "value": 0.4583333333333333
    },
    "SYN-CSM-002": {
      "denominator": 17.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "fabricated_citation_ids": [
          "C5",
          "C1",
          "C2",
          "C8",
          "C7",
          "C4",
          "C3",
          "C6"
        ],
        "generated_citation_ids": [
          "66a24697-9176-49ad-a3c7-71d68813d9e1",
          "66e57bbe-fb68-43c7-810c-23a150eaae26",
          "8bb866c4-e823-4913-b09f-0eec883daa68",
          "8dccc08a-484a-438f-ac5c-ac156ef18e9c",
          "9fe1621d-2a1f-4690-96ba-cae5df236aec",
          "C1",
          "C2",
          "C3",
          "C4",
          "C5",
          "C6",
          "C7",
          "C8",
          "bf6612ab-30cb-473d-90fc-f63f72980a9c",
          "c0565441-cb26-4c90-ac56-6ae55e7d4dac",
          "df43e673-2678-44ab-86ee-2016f737e9cd",
          "ea22f61d-c434-4ab6-a7c3-2b6b6925ebd2"
        ],
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "valid_context_ids": [
          "160cd306-2715-4bc0-bb66-168979a922e5",
          "2c986fe9-ee7f-41b2-b1fd-edbbef8edf2f",
          "3342ad74-fe44-4aee-a72e-81ce2b8a979a",
          "6380a473-ff27-48a6-88fb-507eab7c0870",
          "66a24697-9176-49ad-a3c7-71d68813d9e1",
          "66e57bbe-fb68-43c7-810c-23a150eaae26",
          "8bb866c4-e823-4913-b09f-0eec883daa68",
          "8dccc08a-484a-438f-ac5c-ac156ef18e9c",
          "91dfb1e3-dff7-4b57-92d0-c42302361948",
          "9311b153-e6bf-4875-9eb2-edeec723d1b1",
          "98402931-401e-44e9-8d6e-0fbde7f989fc",
          "9fe1621d-2a1f-4690-96ba-cae5df236aec",
          "CHAT-P2-003",
          "CHAT-P2-004",
          "a39c5e57-70b4-4767-bbb9-3dbb713993eb",
          "aa836cec-1a9e-4c3b-a670-d260c01136a5",
          "b29a2bb5-7d1d-4731-b714-6203d0d4b3b1",
          "bf6612ab-30cb-473d-90fc-f63f72980a9c",
          "c0565441-cb26-4c90-ac56-6ae55e7d4dac",
          "d986c6c9-ebaa-4304-a4c3-a1d9d8577b5a",
          "df43e673-2678-44ab-86ee-2016f737e9cd",
          "ea22f61d-c434-4ab6-a7c3-2b6b6925ebd2"
        ]
      },
      "numerator": 8.0,
      "value": 0.47058823529411764
    },
    "SYN-CSM-003": {
      "denominator": 29.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "fabricated_citation_ids": [
          "C9",
          "C2",
          "A2",
          "C4",
          "A5",
          "C6",
          "C5",
          "C3",
          "C8",
          "C7",
          "A3",
          "A1",
          "C10",
          "C1"
        ],
        "generated_citation_ids": [
          "125c4ac3-3e2a-4a60-8b87-d8ca4359bf17",
          "145a1a47-3231-43a9-8d23-24880122e956",
          "2eb49637-d46b-497e-9788-29ddb867d3bc",
          "2fb589b0-57c2-4fe2-8a67-45b2971965b0",
          "3b2423e5-90d3-4fd0-8c34-b3ce66384bfc",
          "4e13f76b-deab-47b5-94a0-d13b01eea584",
          "52f1e0d3-7b1e-4fdb-97d7-386d643d0c99",
          "5a6b266b-39ea-4979-9d99-067d4a79eadc",
          "5b4c72f3-f09c-4378-b805-423a7fb2fed7",
          "5c05a6f5-73c3-40ce-b489-9e78826d7e30",
          "78d14e72-cdd1-4822-8b6c-e3300c0baf2b",
          "9ed89967-8788-465f-bd08-3dfeb36c7f7b",
          "A1",
          "A2",
          "A3",
          "A5",
          "C1",
          "C10",
          "C2",
          "C3",
          "C4",
          "C5",
          "C6",
          "C7",
          "C8",
          "C9",
          "a3b3e29c-c9d4-400e-ad81-3062d9c90bda",
          "b85ded5f-dc7a-4ddc-93b1-2ae4b51ccd78",
          "c841df57-92ee-483d-9468-72d67a2bb245"
        ],
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "valid_context_ids": [
          "1168f26a-2c89-4a9b-b0cb-df66c398b14c",
          "125c4ac3-3e2a-4a60-8b87-d8ca4359bf17",
          "145a1a47-3231-43a9-8d23-24880122e956",
          "1f1d0a8d-f37f-4c47-bd63-cec1051ff516",
          "2eb49637-d46b-497e-9788-29ddb867d3bc",
          "2fb589b0-57c2-4fe2-8a67-45b2971965b0",
          "33ae8597-1f13-4a6a-a6f8-57cefd522827",
          "3b2423e5-90d3-4fd0-8c34-b3ce66384bfc",
          "4e13f76b-deab-47b5-94a0-d13b01eea584",
          "52f1e0d3-7b1e-4fdb-97d7-386d643d0c99",
          "5a6b266b-39ea-4979-9d99-067d4a79eadc",
          "5b4c72f3-f09c-4378-b805-423a7fb2fed7",
          "5c05a6f5-73c3-40ce-b489-9e78826d7e30",
          "7150c3ef-7db1-4ff9-8b4b-2916508588db",
          "78d14e72-cdd1-4822-8b6c-e3300c0baf2b",
          "794e0df8-a91c-4368-91ca-26302a4693e7",
          "9ed89967-8788-465f-bd08-3dfeb36c7f7b",
          "CHAT-P3-003",
          "CHAT-P3-004",
          "a3b3e29c-c9d4-400e-ad81-3062d9c90bda",
          "b0d44139-ad1c-4e92-9234-77dcd2670020",
          "b85ded5f-dc7a-4ddc-93b1-2ae4b51ccd78",
          "bd52d72e-42e5-4bc0-8fc4-f2ab9ba3d838",
          "c10d6a57-20c0-4d09-bd1e-2b8903378f4c",
          "c841df57-92ee-483d-9468-72d67a2bb245",
          "dde77447-7e75-4eed-96b6-133e1d7bcc76",
          "ea919ae5-2472-4ef6-85a9-e626199b7157"
        ]
      },
      "numerator": 14.0,
      "value": 0.4827586206896552
    }
  },
  "faithfulness": {
    "SYN-CSM-001": {
      "denominator": 43.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "claims_supported_by_supplied_context": 41,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 41.0,
      "value": 0.9534883720930233
    },
    "SYN-CSM-002": {
      "denominator": 30.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "claims_supported_by_supplied_context": 23,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 23.0,
      "value": 0.7666666666666667
    },
    "SYN-CSM-003": {
      "denominator": 47.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "claims_supported_by_supplied_context": 43,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 43.0,
      "value": 0.9148936170212766
    }
  },
  "groundedness": {
    "SYN-CSM-001": {
      "denominator": 43.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "lineage_checked": true,
        "repetition_number": 1,
        "source_validity_checked": true,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 41.0,
      "value": 0.9534883720930233
    },
    "SYN-CSM-002": {
      "denominator": 30.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "lineage_checked": true,
        "repetition_number": 1,
        "source_validity_checked": true,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 23.0,
      "value": 0.7666666666666667
    },
    "SYN-CSM-003": {
      "denominator": 47.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "lineage_checked": true,
        "repetition_number": 1,
        "source_validity_checked": true,
        "status": "measured",
        "system_type": "csm_v3"
      },
      "numerator": 43.0,
      "value": 0.9148936170212766
    }
  },
  "hallucination_rate": {
    "SYN-CSM-001": {
      "denominator": 43.0,
      "details": {
        "case_id": "a37b16e4-aece-444f-9b81-69f1108f17c2",
        "contradicted": 0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "unsupported": 43
      },
      "numerator": 43.0,
      "value": 1.0
    },
    "SYN-CSM-002": {
      "denominator": 30.0,
      "details": {
        "case_id": "7759a683-adb7-4e2a-932e-185cdeabc93b",
        "contradicted": 0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "unsupported": 30
      },
      "numerator": 30.0,
      "value": 1.0
    },
    "SYN-CSM-003": {
      "denominator": 47.0,
      "details": {
        "case_id": "8e262a8f-3296-42f8-8ce0-cd6637098f9c",
        "contradicted": 0,
        "repetition_number": 1,
        "status": "measured",
        "system_type": "csm_v3",
        "unsupported": 47
      },
      "numerator": 47.0,
      "value": 1.0
    }
  }
}
```

## Representative Questions

## SYN-CSM-001
### Turn 1: What active chronic conditions are recorded for this patient?

**Stored Answer**

The patient has two recorded active chronic conditions: essential hypertension and type 2 diabetes mellitus.

**Parsed Atomic Claims**

- A1: Essential hypertension is an active chronic condition for the patient. | source_support_status=None | citations=["4c1c91bf-529c-4286-84ca-8cdfbb165ef3", "4c1c91bf-529c-4286-84ca-8cdfbb165ef3"]
- A2: Type 2 diabetes mellitus is an active chronic condition for the patient. | source_support_status=None | citations=["82436317-3f6d-48a5-98a1-fc7112135ff0", "82436317-3f6d-48a5-98a1-fc7112135ff0"]

**Ground Truth Claims**

- P1-Q01-required-1 Type 2 diabetes mellitus is active
- P1-Q01-required-2 Essential hypertension is active

**Claim Match / Support Output**

- A1: matched=False; score=0.25; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q01-required-2
- A2: matched=False; score=0.3; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q01-required-1

**Retrieved Evidence IDs**

4c1c91bf-529c-4286-84ca-8cdfbb165ef3, 82436317-3f6d-48a5-98a1-fc7112135ff0, 82436317-3f6d-48a5-98a1-fc7112135ff0, 4c1c91bf-529c-4286-84ca-8cdfbb165ef3, f1883cf3-d2d5-4728-9eca-486d26f44798, 93741d05-d8a8-40c9-b965-87774b495ce1, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 7c216ab9-482a-45e1-b674-ccae87dc3241

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=4c1c91bf-529c-4286-84ca-8cdfbb165ef3; source_type=state
- citation_id=C2; canonical_source_id=82436317-3f6d-48a5-98a1-fc7112135ff0; source_type=state
- citation_id=C3; canonical_source_id=82436317-3f6d-48a5-98a1-fc7112135ff0; source_type=patient_information
- citation_id=C4; canonical_source_id=4c1c91bf-529c-4286-84ca-8cdfbb165ef3; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=2; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 2: What was the baseline creatinine and eGFR on 10 January 2026?

**Stored Answer**

Baseline serum creatinine on 10 January 2026 was 1.0 mg/dL; eGFR was not recorded in the available data.

**Parsed Atomic Claims**

- claim-1: Serum creatinine measured on 10 January 2026 was 1.0 mg/dL. | source_support_status=None | citations=["7c216ab9-482a-45e1-b674-ccae87dc3241"]

**Ground Truth Claims**

- P1-Q02-required-1 Creatinine 1.0 mg/dL
- P1-Q02-required-2 eGFR 86 mL/min/1.73m2

**Claim Match / Support Output**

- claim-1: matched=False; score=0.275; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q02-required-1

**Retrieved Evidence IDs**

7c216ab9-482a-45e1-b674-ccae87dc3241, 82436317-3f6d-48a5-98a1-fc7112135ff0, 4c1c91bf-529c-4286-84ca-8cdfbb165ef3, f1883cf3-d2d5-4728-9eca-486d26f44798, 7c216ab9-482a-45e1-b674-ccae87dc3241, 82436317-3f6d-48a5-98a1-fc7112135ff0, 4c1c91bf-529c-4286-84ca-8cdfbb165ef3, f1883cf3-d2d5-4728-9eca-486d26f44798

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 3: Using only evidence available by 8 March, did renal function appear to worsen?

**Stored Answer**

Based on the available measurements, serum creatinine rose from 1.0 mg/dL on 2026-01-10 to 1.8 mg/dL on 2026-03-05, indicating a worsening of renal function.

**Parsed Atomic Claims**

- claim-1: Renal function appeared to worsen, as evidenced by an increase in serum creatinine from 1.0 mg/dL to 1.8 mg/dL. | source_support_status=None | citations=["7c216ab9-482a-45e1-b674-ccae87dc3241", "7c216ab9-482a-45e1-b674-ccae87dc3241"]

**Ground Truth Claims**

- P1-Q03-required-1 Initial report suggested worsening
- P1-Q03-required-2 Conclusion was provisional

**Claim Match / Support Output**

- claim-1: matched=False; score=0.1; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q03-required-1

**Retrieved Evidence IDs**

82436317-3f6d-48a5-98a1-fc7112135ff0, 7c216ab9-482a-45e1-b674-ccae87dc3241, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 93741d05-d8a8-40c9-b965-87774b495ce1, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 7c216ab9-482a-45e1-b674-ccae87dc3241, 82436317-3f6d-48a5-98a1-fc7112135ff0, 93741d05-d8a8-40c9-b965-87774b495ce1

**Answer Citation IDs and Resolver Evidence**

- citation_id=C2; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=patient_information
- citation_id=C6; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=state

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 4: Which event occurred in the patient before the 5 March renal specimen but was recorded later?

**Stored Answer**

Based on the retrieved patient information, there is no documented event that occurred before the 5 March 2026 renal specimen (serum creatinine measurement) and was recorded after the specimen's recording date of 8 March 2026.

**Parsed Atomic Claims**

- A1: No event prior to 2026-03-05 has a recorded_time after 2026-03-08 in the provided data. | source_support_status=None | citations=["4c1c91bf-529c-4286-84ca-8cdfbb165ef3", "7c216ab9-482a-45e1-b674-ccae87dc3241", "93741d05-d8a8-40c9-b965-87774b495ce1", "8e514baf-cccd-4501-b2ce-ed6c9aed08c6", "7c216ab9-482a-45e1-b674-ccae87dc3241", "4c1c91bf-529c-4286-84ca-8cdfbb165ef3", "8e514baf-cccd-4501-b2ce-ed6c9aed08c6", "93741d05-d8a8-40c9-b965-87774b495ce1"]

**Ground Truth Claims**

- P1-Q04-required-1 Dehydration occurred 4 March
- P1-Q04-required-2 It was recorded 10 March

**Claim Match / Support Output**

- A1: matched=False; score=0.3315789473684211; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q04-required-2

**Retrieved Evidence IDs**

4c1c91bf-529c-4286-84ca-8cdfbb165ef3, 7c216ab9-482a-45e1-b674-ccae87dc3241, 93741d05-d8a8-40c9-b965-87774b495ce1, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 7c216ab9-482a-45e1-b674-ccae87dc3241, 4c1c91bf-529c-4286-84ca-8cdfbb165ef3, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 93741d05-d8a8-40c9-b965-87774b495ce1

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=4c1c91bf-529c-4286-84ca-8cdfbb165ef3; source_type=patient_information
- citation_id=C2; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=patient_information
- citation_id=C3; canonical_source_id=93741d05-d8a8-40c9-b965-87774b495ce1; source_type=patient_information
- citation_id=C4; canonical_source_id=8e514baf-cccd-4501-b2ce-ed6c9aed08c6; source_type=patient_information
- citation_id=C5; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=state
- citation_id=C6; canonical_source_id=4c1c91bf-529c-4286-84ca-8cdfbb165ef3; source_type=state
- citation_id=C7; canonical_source_id=8e514baf-cccd-4501-b2ce-ed6c9aed08c6; source_type=state
- citation_id=C8; canonical_source_id=93741d05-d8a8-40c9-b965-87774b495ce1; source_type=state

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 5: How should the dehydration note change interpretation of the abnormal renal result?

**Stored Answer**

The dehydration note (C5) indicates that the patient’s poor oral intake and gastroenteritis likely contributed to the elevated serum creatinine measured on 5 March (C7). Therefore, the abnormal renal result should be interpreted as a possible transient, pre‑renal change due to dehydration rather than as evidence of new intrinsic kidney disease; re‑assessment after rehydration is warranted.

**Parsed Atomic Claims**

- A1: The elevated serum creatinine on 2026-03-05 may be due to dehydration rather than intrinsic renal pathology. | source_support_status=None | citations=["f4c29954-0dee-482e-a023-4b0bb58eefbe", "7c216ab9-482a-45e1-b674-ccae87dc3241"]
- A2: Serum creatinine was within normal limits on 2026-01-10, indicating a change from baseline. | source_support_status=None | citations=["7c216ab9-482a-45e1-b674-ccae87dc3241"]

**Ground Truth Claims**

- P1-Q05-required-1 Dehydration may have influenced result
- P1-Q05-required-2 Evidence should not be erased

**Claim Match / Support Output**

- A1: matched=False; score=0.3631578947368421; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q05-required-1
- A2: matched=False; score=0.30000000000000004; reason=no_ground_truth_match; support=unsupported; matched_truth=P1-Q05-required-1

**Retrieved Evidence IDs**

7c216ab9-482a-45e1-b674-ccae87dc3241, 4c1c91bf-529c-4286-84ca-8cdfbb165ef3, 93741d05-d8a8-40c9-b965-87774b495ce1, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, f4c29954-0dee-482e-a023-4b0bb58eefbe, 8e514baf-cccd-4501-b2ce-ed6c9aed08c6, 7c216ab9-482a-45e1-b674-ccae87dc3241, 93741d05-d8a8-40c9-b965-87774b495ce1

**Answer Citation IDs and Resolver Evidence**

- citation_id=C5; canonical_source_id=f4c29954-0dee-482e-a023-4b0bb58eefbe; source_type=patient_information
- citation_id=C7; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=state
- citation_id=C1; canonical_source_id=7c216ab9-482a-45e1-b674-ccae87dc3241; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=2; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

## SYN-CSM-002
### Turn 1: What antibiotic allergy is currently recorded?

**Stored Answer**

The patient has a recorded active allergy to amoxicillin (penicillin‑class antibiotic) manifested by generalized hives of moderate severity.

**Parsed Atomic Claims**

- A1: Patient has an active allergy to amoxicillin/penicillin-class antibiotic. | source_support_status=None | citations=["66a24697-9176-49ad-a3c7-71d68813d9e1", "66a24697-9176-49ad-a3c7-71d68813d9e1"]

**Ground Truth Claims**

- P2-Q01-required-1 Amoxicillin allergy
- P2-Q01-required-2 Generalized hives

**Claim Match / Support Output**

- A1: matched=False; score=0.25; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q01-required-1

**Retrieved Evidence IDs**

66a24697-9176-49ad-a3c7-71d68813d9e1, 66a24697-9176-49ad-a3c7-71d68813d9e1, 8dccc08a-484a-438f-ac5c-ac156ef18e9c, 8bb866c4-e823-4913-b09f-0eec883daa68, c0565441-cb26-4c90-ac56-6ae55e7d4dac, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8bb866c4-e823-4913-b09f-0eec883daa68, 8dccc08a-484a-438f-ac5c-ac156ef18e9c

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=state
- citation_id=C2; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 2: Was anaphylaxis documented in the initial allergy history?

**Stored Answer**

The initial allergy history records a reaction of generalized hives without airway compromise and does not document anaphylaxis.

**Parsed Atomic Claims**

- A1: Anaphylaxis was not documented in the initial allergy history. | source_support_status=None | citations=["66a24697-9176-49ad-a3c7-71d68813d9e1"]

**Ground Truth Claims**

- P2-Q02-required-1 No documented anaphylaxis

**Claim Match / Support Output**

- A1: matched=False; score=0.42000000000000004; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q02-required-1

**Retrieved Evidence IDs**

66a24697-9176-49ad-a3c7-71d68813d9e1, 8bb866c4-e823-4913-b09f-0eec883daa68, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 66a24697-9176-49ad-a3c7-71d68813d9e1, 8bb866c4-e823-4913-b09f-0eec883daa68, 66a24697-9176-49ad-a3c7-71d68813d9e1, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8dccc08a-484a-438f-ac5c-ac156ef18e9c

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=1; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 3: What contradiction entered the record on 10 February?

**Stored Answer**

The retrieved records do not contain any entry labeled as a contradiction on 10 February; therefore the specific contradiction entered on that date cannot be identified from the available data.

**Parsed Atomic Claims**

- A1: No contradiction entry is present for 10 February in the provided context. | source_support_status=None | citations=[]

**Ground Truth Claims**

- P2-Q03-required-1 Imported NKDA conflicts with allergy history

**Claim Match / Support Output**

- A1: matched=False; score=0.30000000000000004; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q03-required-1

**Retrieved Evidence IDs**

8dccc08a-484a-438f-ac5c-ac156ef18e9c, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8bb866c4-e823-4913-b09f-0eec883daa68, 66a24697-9176-49ad-a3c7-71d68813d9e1, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8dccc08a-484a-438f-ac5c-ac156ef18e9c, 8bb866c4-e823-4913-b09f-0eec883daa68, 66a24697-9176-49ad-a3c7-71d68813d9e1

**Answer Citation IDs and Resolver Evidence**

No answer citations stored.

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=1; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 4: Should the two hospital summaries count as two independent confirmations of no allergy?

**Stored Answer**

The available records show a documented, active amoxicillin/penicillin-class allergy (C1, C4); there is no evidence of any hospital summary indicating the absence of an allergy, so the two summaries cannot be counted as independent confirmations of no allergy.

**Parsed Atomic Claims**

- A1: Patient has a documented active amoxicillin/penicillin-class allergy. | source_support_status=None | citations=["66a24697-9176-49ad-a3c7-71d68813d9e1", "66a24697-9176-49ad-a3c7-71d68813d9e1"]
- A2: No evidence in the provided context confirms the absence of an allergy. | source_support_status=None | citations=[]

**Ground Truth Claims**

- P2-Q04-required-1 Do not double-count duplicate family

**Claim Match / Support Output**

- A1: matched=False; score=0.30000000000000004; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q04-required-1
- A2: matched=False; score=0.30000000000000004; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q04-required-1

**Retrieved Evidence IDs**

66a24697-9176-49ad-a3c7-71d68813d9e1, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8bb866c4-e823-4913-b09f-0eec883daa68, 66a24697-9176-49ad-a3c7-71d68813d9e1, 8bb866c4-e823-4913-b09f-0eec883daa68, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8dccc08a-484a-438f-ac5c-ac156ef18e9c, 9fe1621d-2a1f-4690-96ba-cae5df236aec

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=state
- citation_id=C4; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=2; ground_truth_claims=1; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 5: What should the allergy-state status be after the duplicate hospital record is added?

**Stored Answer**

The allergy-state for amoxicillin/penicillin-class antibiotic is recorded as 'active' (see C1). The provided data contain no information indicating that adding a duplicate hospital record would change this status, so it should remain 'active'.

**Parsed Atomic Claims**

- A1: Allergy-state status for amoxicillin/penicillin-class antibiotic is active. | source_support_status=None | citations=["66a24697-9176-49ad-a3c7-71d68813d9e1"]
- A2: No evidence that adding a duplicate hospital record changes the allergy-state status. | source_support_status=None | citations=[]

**Ground Truth Claims**

- P2-Q05-required-1 State is contested

**Claim Match / Support Output**

- A1: matched=False; score=0.1; reason=no_ground_truth_match; support=unsupported; matched_truth=P2-Q05-required-1
- A2: matched=False; score=0.0; reason=no_ground_truth_match; support=unsupported; matched_truth=None

**Retrieved Evidence IDs**

66a24697-9176-49ad-a3c7-71d68813d9e1, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8bb866c4-e823-4913-b09f-0eec883daa68, 66a24697-9176-49ad-a3c7-71d68813d9e1, 8bb866c4-e823-4913-b09f-0eec883daa68, c0565441-cb26-4c90-ac56-6ae55e7d4dac, 8dccc08a-484a-438f-ac5c-ac156ef18e9c, 8dccc08a-484a-438f-ac5c-ac156ef18e9c

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=66a24697-9176-49ad-a3c7-71d68813d9e1; source_type=state

**Diagnostic Metric Contribution**

- generated_claims=2; ground_truth_claims=1; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

## SYN-CSM-003
### Turn 1: What cardiovascular condition and medicines are active at baseline?

**Stored Answer**

At baseline (2026-04-01), the patient has an active, confirmed atrial fibrillation and is actively taking Apixaban (5 mg twice daily) for anticoagulation. No other cardiovascular medications are active; Metoprolol succinate is recorded as superseded.

**Parsed Atomic Claims**

- A1: The patient has an active, confirmed atrial fibrillation at baseline. | source_support_status=None | citations=["5c05a6f5-73c3-40ce-b489-9e78826d7e30", "5c05a6f5-73c3-40ce-b489-9e78826d7e30"]
- A2: Apixaban 5 mg twice daily is active at baseline for anticoagulation. | source_support_status=None | citations=["52f1e0d3-7b1e-4fdb-97d7-386d643d0c99"]
- A3: Metoprolol succinate is not active at baseline (recorded as superseded). | source_support_status=None | citations=["9ed89967-8788-465f-bd08-3dfeb36c7f7b"]

**Ground Truth Claims**

- P3-Q01-required-1 AF active
- P3-Q01-required-2 Metoprolol 25 active
- P3-Q01-required-3 Apixaban 5 mg twice daily active

**Claim Match / Support Output**

- A1: matched=False; score=0.25; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q01-required-1
- A2: matched=False; score=0.25; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q01-required-1
- A3: matched=False; score=0.175; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q01-required-2

**Retrieved Evidence IDs**

5c05a6f5-73c3-40ce-b489-9e78826d7e30, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 78d14e72-cdd1-4822-8b6c-e3300c0baf2b, 4e13f76b-deab-47b5-94a0-d13b01eea584, 52f1e0d3-7b1e-4fdb-97d7-386d643d0c99, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 78d14e72-cdd1-4822-8b6c-e3300c0baf2b, 4e13f76b-deab-47b5-94a0-d13b01eea584

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=5c05a6f5-73c3-40ce-b489-9e78826d7e30; source_type=state
- citation_id=C2; canonical_source_id=5c05a6f5-73c3-40ce-b489-9e78826d7e30; source_type=patient_information
- citation_id=C5; canonical_source_id=52f1e0d3-7b1e-4fdb-97d7-386d643d0c99; source_type=patient_information
- citation_id=C6; canonical_source_id=9ed89967-8788-465f-bd08-3dfeb36c7f7b; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=3; ground_truth_claims=3; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 2: What was the baseline resting heart rate?

**Stored Answer**

The baseline resting heart rate was 82 beats per minute.

**Parsed Atomic Claims**

- A1: Baseline resting heart rate = 82 beats/min | source_support_status=None | citations=["78d14e72-cdd1-4822-8b6c-e3300c0baf2b", "78d14e72-cdd1-4822-8b6c-e3300c0baf2b"]

**Ground Truth Claims**

- P3-Q02-required-1 Heart rate 82

**Claim Match / Support Output**

- A1: matched=False; score=0.31999999999999995; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q02-required-1

**Retrieved Evidence IDs**

78d14e72-cdd1-4822-8b6c-e3300c0baf2b, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 4e13f76b-deab-47b5-94a0-d13b01eea584, 78d14e72-cdd1-4822-8b6c-e3300c0baf2b, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 4e13f76b-deab-47b5-94a0-d13b01eea584

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=78d14e72-cdd1-4822-8b6c-e3300c0baf2b; source_type=patient_information
- citation_id=C5; canonical_source_id=78d14e72-cdd1-4822-8b6c-e3300c0baf2b; source_type=state

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=1; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 3: What changed on 8 April compared with baseline?

**Stored Answer**

On 8 April the patient’s resting heart rate was measured at 112 beats/min, which is interpreted as elevated compared with the baseline value.

**Parsed Atomic Claims**

- A1: Resting heart rate was 112 beats/min on 8 April and is elevated compared with baseline. | source_support_status=None | citations=["5a6b266b-39ea-4979-9d99-067d4a79eadc"]

**Ground Truth Claims**

- P3-Q03-required-1 Heart rate increased 82 to 112
- P3-Q03-required-2 Symptoms worsened

**Claim Match / Support Output**

- A1: matched=False; score=0.2357142857142857; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q03-required-1

**Retrieved Evidence IDs**

5a6b266b-39ea-4979-9d99-067d4a79eadc, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 4e13f76b-deab-47b5-94a0-d13b01eea584, 5a6b266b-39ea-4979-9d99-067d4a79eadc, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 4e13f76b-deab-47b5-94a0-d13b01eea584

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=5a6b266b-39ea-4979-9d99-067d4a79eadc; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 4: What clinician-directed treatment change was recorded on 9 April?

**Stored Answer**

On 9 April 2026 a clinician‑directed rate‑control adjustment was recorded, initiating Metoprolol succinate 50 mg taken orally once daily.

**Parsed Atomic Claims**

- A1: A clinician‑directed rate‑control adjustment was made on 9 April 2026, prescribing Metoprolol succinate 50 mg once daily. | source_support_status=None | citations=["2fb589b0-57c2-4fe2-8a67-45b2971965b0"]

**Ground Truth Claims**

- P3-Q04-required-1 Metoprolol 25 to 50
- P3-Q04-required-2 Apixaban remained active

**Claim Match / Support Output**

- A1: matched=False; score=0.3571428571428572; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q04-required-1

**Retrieved Evidence IDs**

2fb589b0-57c2-4fe2-8a67-45b2971965b0, 4e13f76b-deab-47b5-94a0-d13b01eea584, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 52f1e0d3-7b1e-4fdb-97d7-386d643d0c99, 2fb589b0-57c2-4fe2-8a67-45b2971965b0, 4e13f76b-deab-47b5-94a0-d13b01eea584, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 52f1e0d3-7b1e-4fdb-97d7-386d643d0c99

**Answer Citation IDs and Resolver Evidence**

- citation_id=C1; canonical_source_id=2fb589b0-57c2-4fe2-8a67-45b2971965b0; source_type=patient_information

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0

### Turn 5: Before follow-up data existed, what should the treatment-response state be?

**Stored Answer**

There is no documented treatment-response state before any follow‑up data; therefore the appropriate state is that the response is not yet determined (unknown).

**Parsed Atomic Claims**

- A1: No treatment-response state is documented prior to follow‑up data, so the response is unknown. | source_support_status=None | citations=[]

**Ground Truth Claims**

- P3-Q05-required-1 Response not yet known
- P3-Q05-required-2 State candidate

**Claim Match / Support Output**

- A1: matched=False; score=0.33999999999999997; reason=no_ground_truth_match; support=unsupported; matched_truth=P3-Q05-required-2

**Retrieved Evidence IDs**

9ed89967-8788-465f-bd08-3dfeb36c7f7b, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 4e13f76b-deab-47b5-94a0-d13b01eea584, 52f1e0d3-7b1e-4fdb-97d7-386d643d0c99, 5c05a6f5-73c3-40ce-b489-9e78826d7e30, 4e13f76b-deab-47b5-94a0-d13b01eea584, 9ed89967-8788-465f-bd08-3dfeb36c7f7b, 52f1e0d3-7b1e-4fdb-97d7-386d643d0c99, 78d14e72-cdd1-4822-8b6c-e3300c0baf2b, c841df57-92ee-483d-9468-72d67a2bb245

**Answer Citation IDs and Resolver Evidence**

No answer citations stored.

**Diagnostic Metric Contribution**

- generated_claims=1; ground_truth_claims=2; matched_claims=0
- answer_accuracy_single_turn_f1=0.0
- hallucination_rate_single_turn=1.0
- evidence_support_rate_single_turn=0.0
