import re
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup


def parse_test_line(line):
    """Parse a single test line and extract all fields."""
    # Remove HTML tags but keep the href content
    soup = BeautifulSoup(line, "html.parser")

    # Extract date-time (at the beginning)
    datetime_match = re.match(r"^(\d{2}-\d{2} \d{2}:\d{2}:\d{2}):", line)
    datetime = datetime_match.group(1) if datetime_match else None

    # Extract status (FAILED or FLAKED)
    status_span = soup.find("span", string=re.compile(r"(FAILED|FLAKED)"))
    status = status_span.text if status_span else None

    # Extract link
    link_tag = soup.find("a")
    link = (
        link_tag.attrs.get("href") if link_tag and hasattr(link_tag, "attrs") else None  # type: ignore
    )

    # Extract the rest of the line after the link
    # Find the closing </a> tag position
    link_end = line.find("</a></span>)") + len("</a></span>):")
    rest_of_line = (
        line[link_end:].strip() if link_end > len("</a></span>):") - 1 else ""
    )

    # Extract test command (everything before the first parenthesis with duration)
    duration_match = re.search(r"\((\d+s)\)", rest_of_line)
    if duration_match:
        test_command = rest_of_line[: duration_match.start()].strip()
        duration = duration_match.group(1)
    else:
        test_command = None
        duration = None

    # Extract exit code
    code_match = re.search(r"\(code: (\d+)\)", rest_of_line)
    exit_code = int(code_match.group(1)) if code_match else None

    # Extract target
    target_match = re.search(r"\(target: ([^)]+)\)", rest_of_line)
    target = target_match.group(1) if target_match else None

    return {
        "date-time": datetime,
        "status": status,
        "link": link,
        "test_command": test_command,
        "duration": duration,
        "exit_code": exit_code,
        "target": target,
    }


def main():
    # use requests to go get "http://ci.aztec-labs.com/?filter=^next&filter_prop=name&fail_list=failed_tests_next"
    response = requests.get(
        "http://ci.aztec-labs.com/?filter=^next&filter_prop=name&fail_list=failed_tests_next"
    )

    # extract the body of the response
    body = response.text

    # treat the body as a list of lines
    lines = body.split("\n")

    # find the lines that end in (target: next) and parse them
    parsed_data = []
    for line in lines:
        if line.endswith("(target: next)"):
            parsed_data.append(parse_test_line(line))

    # Create DataFrame
    df = pd.DataFrame(parsed_data)

    # Convert date-time to proper datetime
    # The format is MM-DD HH:MM:SS, we need to add the current year
    current_year = datetime.now().year

    def parse_datetime(dt_str):
        if dt_str:
            # Add current year to the date string
            dt_with_year = f"{current_year}-{dt_str}"
            try:
                return pd.to_datetime(dt_with_year, format="%Y-%m-%d %H:%M:%S")
            except:
                return None
        return None

    df["datetime"] = df["date-time"].apply(parse_datetime)

    # Filter for last 48 hours
    now = datetime.now()
    cutoff_time = now - timedelta(hours=48)
    df_recent = df[df["datetime"] >= cutoff_time].copy()

    print(f"Tests from the last 48 hours: {len(df_recent)}")
    print(f"Total tests in dataset: {len(df)}")
    print()

    # Analyze most flakey/failing tests
    if len(df_recent) > 0:
        # Group by test command and count failures
        test_summary = df_recent.groupby("test_command").agg(
            {
                "status": [
                    "count",
                    lambda x: (x == "FAILED").sum(),
                    lambda x: (x == "FLAKED").sum(),
                ],
                "exit_code": lambda x: list(x.unique()),
                "duration": lambda x: list(x),
            }
        )

        # Flatten column names
        test_summary.columns = [
            "total_runs",
            "failed_count",
            "flaked_count",
            "exit_codes",
            "durations",
        ]

        # Sort by total occurrences
        test_summary = test_summary.sort_values("total_runs", ascending=False)

        print("Most frequently failing/flakey tests in the last 48 hours:")
        print("=" * 80)

        for idx, (test_cmd, row) in enumerate(test_summary.head(10).iterrows(), 1):
            print(f"\n{idx}. {test_cmd}")
            print(
                f"   Total runs: {row['total_runs']} (Failed: {row['failed_count']}, Flaked: {row['flaked_count']})"
            )
            print(f"   Exit codes: {row['exit_codes']}")
            print(f"   Durations: {row['durations']}")

        # Also show a summary by status
        print("\n\nSummary by status:")
        print("-" * 40)
        status_counts = df_recent["status"].value_counts()
        for status, count in status_counts.items():
            print(f"{status}: {count}")

        # Save the recent data to CSV
        df_recent.to_csv("failed_tests_48h.csv", index=False)
        print("\n\nRecent test data saved to failed_tests_48h.csv")

        # Save the summary
        test_summary.to_csv("test_summary_48h.csv")
        print("Test summary saved to test_summary_48h.csv")
    else:
        print("No test failures found in the last 48 hours")


if __name__ == "__main__":
    main()
