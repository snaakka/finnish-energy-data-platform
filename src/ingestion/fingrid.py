# Imports
import json
import logging
import os
import time
from datetime import date, datetime, timedelta

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)


# Data Models
class FingridRecord(BaseModel):
    datasetId: int
    startTime: datetime
    endTime: datetime
    value: float


# HTTP Helpers
def request_with_retry(url, headers, params, max_attempts=3):

    for attempt in range(1, max_attempts + 1):
        response = requests.get(
            url,
            headers=headers,
            params=params
        )

        if response.status_code == 429:
            if attempt < max_attempts:
                wait_time = 2 ** attempt
                logger.warning(
                    "Rate limit exceeded. Retrying in %s seconds... (attempt %s/%s)",
                    wait_time,
                    attempt,
                    max_attempts
                )
                time.sleep(wait_time)
                continue

        break
    return response


# Data Fetching
def fetch_fingrid_data(api_key, dataset_id, start_time, end_time) -> list:

    url = f"https://data.fingrid.fi/api/datasets/{dataset_id}/data"

    headers = {
        "x-api-key": api_key
    }
    
    all_records = []

    params = {
        "startTime": start_time,
        "endTime": end_time,
        "page": 1
    }

    # First page
    response = request_with_retry(
        url,
        headers=headers,
        params=params
    )

    response.raise_for_status()

    x = response.json()

    all_records.extend(x["data"])

    last_page = x["pagination"]["lastPage"]

    logger.info("Fetching page 1/%s", last_page)

    if last_page > 1:
        time.sleep(2)

    for i in range(2, last_page + 1):
        params["page"] = i
        logger.info("Fetching page %s/%s", i, last_page)

        response = request_with_retry(
            url,
            headers=headers,
            params=params
        )

        response.raise_for_status()

        x = response.json()

        all_records.extend(x["data"])

        if i < last_page:
            time.sleep(2)

    logger.info(
        "Fetched %s records",
        len(all_records)
    )

    return all_records


# Data Validation
def validate_records(all_records, dataset_id):
    # empty data validation
    if not all_records:
        raise ValueError("No records returned")
        
    # Pydantic schema validation
    for idx, record in enumerate(all_records, start=1):
        try:
            validated_record = FingridRecord.model_validate(record)

        except ValidationError as e:
            raise ValueError(
                f"Schema validation failed for record {idx}"
            ) from e
        
        # Quality rules
        if validated_record.datasetId != dataset_id:
            raise ValueError(
                f"Unexpected dataset ID: expected {dataset_id}, "
                f"got {validated_record.datasetId}"
            )

        if validated_record.startTime >= validated_record.endTime:
            raise ValueError(
                f"Invalid time interval: startTime {validated_record.startTime} "
                f"must be before endTime {validated_record.endTime}"
            )

    logger.info(
        "Validation completed successfully for %s records",
        len(all_records)
    )
            

# Raw Data Storage
def save_raw_data_to_adls(
        all_records,
        dataset_id, 
        start_date,
        file_system_client
    ):

    year = start_date.year
    month = start_date.month
    day = start_date.day

    json_data = json.dumps(all_records, indent=2)

    directory_path = (
        f"fingrid/dataset_{dataset_id}/"
        f"year={year}/month={month:02d}/day={day:02d}"
    )

    directory_client = file_system_client.get_directory_client(directory_path)

    file_client = directory_client.get_file_client("data.json")
    file_client.upload_data(json_data, overwrite=True)

    logger.info(
        "Raw data uploaded to ADLS: %s/data.json",
        directory_path
    )


# Pipeline Orchestration
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    logging.getLogger("azure").setLevel(logging.WARNING)

    load_dotenv()

    api_key = os.getenv("FINGRID_API_KEY")

    if not api_key:
        raise ValueError("FINGRID_API_KEY environment variable is not set")

    dataset_id = 124

    current_date = date(2026, 9, 1)
    backfill_end_date = date(2026, 9, 3)

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT")

    if not account_name:
        raise ValueError("AZURE_STORAGE_ACCOUNT environment variable is not set")
    
    account_url = f"https://{account_name}.dfs.core.windows.net"

    credential = DefaultAzureCredential()

    service_client = DataLakeServiceClient(account_url, credential)

    file_system_client = service_client.get_file_system_client(file_system="raw")

    while current_date <= backfill_end_date:

        next_date = current_date + timedelta(days=1)

        start_time = current_date.strftime("%Y-%m-%dT00:00:00Z")
        end_time = next_date.strftime("%Y-%m-%dT00:00:00Z")

        logger.info(
            "Starting ingestion for dataset %s, date %s",
            dataset_id,
            current_date
        )

        try:
            all_records = fetch_fingrid_data(api_key, dataset_id, start_time, end_time)

            validate_records(all_records, dataset_id)

            save_raw_data_to_adls(all_records, dataset_id, current_date, file_system_client)

        except Exception:
            logger.exception(
                "Ingestion failed for dataset %s, date %s",
                dataset_id,
                current_date
            )
            raise

        logger.info(
            "Completed ingestion for dataset %s, date %s",
            dataset_id,
            current_date
        )

        current_date = next_date

        if current_date <= backfill_end_date:
            time.sleep(2)


# Entry Point
if __name__ == "__main__":
    main()