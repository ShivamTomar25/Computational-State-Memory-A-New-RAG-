from unittest import TestCase

from app.evaluation.datasets.fixtures.smoke_cases import SMOKE_DATASET
from app.evaluation.datasets.services.dataset_service import dataset_checksum
from app.evaluation.datasets.validators.dataset_validator import validate_dataset_fixture
from app.evaluation.metrics.registry.registry import list_metric_definitions


class EvaluationRegistryAndDatasetTests(TestCase):
    def test_metric_registry_has_twenty_one_metrics(self):
        metrics = list_metric_definitions()

        self.assertEqual(len(metrics), 21)
        self.assertEqual(len({metric.metric_id for metric in metrics}), 21)

    def test_smoke_dataset_is_valid_and_deterministic(self):
        issues = validate_dataset_fixture(SMOKE_DATASET)
        first_checksum = dataset_checksum(SMOKE_DATASET)
        second_checksum = dataset_checksum(SMOKE_DATASET)

        self.assertEqual(issues, [])
        self.assertEqual(first_checksum, second_checksum)
        self.assertEqual(len(SMOKE_DATASET["cases"]), 3)
