import json
import os
import requests
import time

from dotenv import load_dotenv
from pathlib import Path


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
    print(f"pagenum: {page_num}")
    response = requests.get(
        url,
        headers=headers,
        params=params,
    )

    response.raise_for_status()

    x = response.json()

    all_records.extend(x["data"])

    last_page = x["pagination"]["lastPage"]
    
    time.sleep(2)

    for i in range(2, last_page+1):
        params["page"] = i
        print(f"pagenum: {i}")
        response = requests.get(
            url,
            headers=headers,
            params=params,
        )

        response.raise_for_status()

        x = response.json()

        all_records.extend(x["data"])

        if i < last_page:
            time.sleep(2)

    print(len(all_records))

    return all_records


def save_raw_data(all_records, variable_id, start_time):
    year = start_time[:4]
    month = start_time[5:7]
    day = start_time[8:10]

    path = Path(
        f"data/raw/fingrid/dataset_{variable_id}/year={year}/month={month}/day={day}/"
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

    start_time = "2026-09-01T00:00:00Z"
    end_time = "2026-09-02T00:00:00Z"
    variable_id = 124

    all_records = fetch_fingrid_data(api_key, variable_id, start_time, end_time)

    save_raw_data(all_records, variable_id, start_time)


if __name__ == "__main__":
    main()