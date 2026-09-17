from unittest.mock import Mock, patch

from src.ingestion.fingrid import request_with_retry

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
    with patch("src.ingestion.fingrid.requests.get") as mock_get:
        response_429 = Mock()
        response_429.status_code = 429

        mock_get.side_effect = [response_429, response_429, response_429]