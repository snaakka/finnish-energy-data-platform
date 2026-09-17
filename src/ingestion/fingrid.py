import json
import os
import requests
import time

from datetime import date, timedelta
from dotenv import load_dotenv
from pathlib import Path


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
                print(
                    f"Rate limit exceeded. Retrying in {wait_time} seconds... (attempt {attempt}/{max_attempts})"
                )
                time.sleep(wait_time)
                continue

        break
    return response


def fetch_fingrid_data(api_key, variable_id, start_time, end_time) -> list:

    url = f"https://data.fingrid.fi/api/datasets/{variable_id}/data"

    headers = {
        "x-api-key": api_key
    }
    
    all_records = []
    page_num = 1

    params = {
        "startTime": start_time,
        "endTime": end_time,
        "page": page_num
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

    print(f"Fetching page 1/{last_page}")
    
    time.sleep(2)

    for i in range(2, last_page+1):
        params["page"] = i
        print(f"Fetching page {i}/{last_page}")

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

    print(len(all_records))

    return all_records


def save_raw_data(all_records, variable_id, start_date):
    year = start_date.year
    month = start_date.month
    day = start_date.day

    path = Path(
        f"data/raw/fingrid/dataset_{variable_id}/year={year}/month={month:02d}/day={day:02d}/"
    )

    path.mkdir(parents=True, exist_ok=True)

    file_path = path / "data.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2)



def main():

    load_dotenv()

    api_key = os.getenv("FINGRID_API_KEY")

    if not api_key:
        raise ValueError("FINGRID_API_KEY environment variable is not set")

    variable_id = 124

    current_date = date(2026, 9, 1)
    backfill_end_date = date(2026, 9, 3)

    while current_date <= backfill_end_date:

        next_date = current_date + timedelta(days=1)

        start_time = current_date.strftime("%Y-%m-%dT00:00:00Z")
        end_time = next_date.strftime("%Y-%m-%dT00:00:00Z")

        all_records = fetch_fingrid_data(api_key, variable_id, start_time, end_time)

        save_raw_data(all_records, variable_id, current_date)

        current_date = next_date

        if current_date <= backfill_end_date:
            time.sleep(2)


if __name__ == "__main__":
    main()