from __future__ import annotations


def validate_dataset_fixture(dataset: dict) -> list[str]:
    issues = []

    if not dataset.get("cases"):
        issues.append("Dataset has no cases.")

    for case in dataset.get("cases", []):
        manifest = case.get("manifest", {})

        if not manifest.get("events"):
            issues.append(f"{case.get('case_key')} has no timeline events.")

        if not manifest.get("questions"):
            issues.append(f"{case.get('case_key')} has no questions.")

        for question in manifest.get("questions", []):
            truth = question.get("truth")

            if not truth:
                issues.append(f"{case.get('case_key')} turn {question.get('turn_number')} has no ground truth.")

    return issues
