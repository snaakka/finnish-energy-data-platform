import pytest

from unittest.mock import Mock, patch, call
from src.ingestion.fingrid import request_with_retry, validate_records


def test_request_with_retry_retries_on_429():
    with patch("src.ingestion.fingrid.requests.get") as mock_get, \
        patch("src.ingestion.fingrid.time.sleep") as mock_sleep:

        response_429 = Mock()
        response_429.status_code = 429

        response_200 = Mock()
        response_200.status_code = 200

        mock_get.side_effect = [response_429, response_200]

        url = "https://example.com"
        headers = {"x-api-key": "test-key"}
        params = {"page": 1}

        response = request_with_retry(
            url, 
            headers=headers, 
            params=params
        )

        assert response.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(2)


def test_request_with_retry_stops_after_max_attempts():
    with patch("src.ingestion.fingrid.requests.get") as mock_get, \
        patch("src.ingestion.fingrid.time.sleep") as mock_sleep:

        response_429 = Mock()
        response_429.status_code = 429

        mock_get.side_effect = [response_429, response_429, response_429]

        url = "https://example.com"
        headers = {"x-api-key": "test-key"}
        params = {"page": 1}

        response = request_with_retry(
            url,
            headers=headers,
            params=params
        )

        assert response.status_code == 429
        assert mock_get.call_count == 3
        assert mock_sleep.call_args_list == [
            call(2),
            call(4)
        ]


def test_validate_records_empty_data():
    data = []

    with pytest.raises(ValueError):
        validate_records(data, 124)


def test_validate_records_rejects_invalid_schema():
    data = [
        {
            "datasetId": 124,
            "startTime": "not-a-datetime",
            "endTime": "2026-09-02T00:00:00Z",
            "value": 1234.29
        }
    ]

    with pytest.raises(ValueError):
        validate_records(data, 124)


def test_validate_records_accepts_valid_input():
    data = [
        {
            "datasetId": 124,
            "startTime": "2026-09-01T23:45:00Z",
            "endTime": "2026-09-02T00:00:00Z",
            "value": 1234.29
        }
    ]

    result = validate_records(data, 124)

    assert result is None


def test_validate_records_rejects_wrong_dataset():
    expected_dataset_id = 124

    data = [
        {
            "datasetId": 999,
            "startTime": "2026-09-01T23:45:00Z",
            "endTime": "2026-09-02T00:00:00Z",
            "value": 1234.29
        }
    ]

    with pytest.raises(ValueError):
        validate_records(data, expected_dataset_id)


def test_validate_records_rejects_invalid_time_interval():
    data = [
        {
            "datasetId": 124,
            "startTime": "2026-09-01T00:15:00Z",
            "endTime": "2026-09-01T00:00:00Z",
            "value": 1234.29
        }
    ]

    with pytest.raises(ValueError):
        validate_records(data, 124)
