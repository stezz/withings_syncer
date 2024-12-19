import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import configparser
import argparse
import logging

loglevel = logging.INFO
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("withings_syncer.log"), logging.StreamHandler()],
)

SYNCED_LOG = "synced_weights.json"


# Load configuration from a config file
def load_config(config_file):
    if not os.path.exists(config_file):
        logging.error(f"Configuration file {config_file} not found!")
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(config_file)
    logging.debug(f"Configuration loaded from {config_file}")
    return config


# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Sync Withings data to Intervals.icu")
    parser.add_argument(
        "--config",
        type=str,
        default="./config.ini",
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--auth-code", type=str, help="Authorization code for initial authentication"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date for sync in YYYY-MM-DD format (defaults to yesterday)",
    )
    parser.add_argument(
        "--force-resync",
        action="store_true",
        help="Force resync of all dates even if already synced",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="debug logging",
    )

    return parser.parse_args()


def load_synced_days():
    if os.path.isfile(SYNCED_LOG):
        with open(SYNCED_LOG, "r") as file:
            return json.load(file)
    return set()


def save_synced_days(synced_days):
    with open(SYNCED_LOG, "w") as file:
        json.dump(list(synced_days), file, indent=4)


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    config = load_config(args.config)

    # Load API credentials and configuration
    client_id = config["Withings"]["client_id"]
    client_secret = config["Withings"]["client_secret"]
    redirect_uri = config["Withings"]["redirect_uri"]
    icu_api_key = config["Intervals"]["icu_api_key"]
    icu_athlete_id = config["Intervals"]["icu_athlete_id"]
    cfg = config["General"]["withings_config"]
    logging.debug(f"Configuration file for tokens: {cfg}")

    # Load fields
    weight_field = config["Fields"].get("weight_field", None)
    bodyfat_field = config["Fields"].get("bodyfat_field", None)
    diastolic_field = config["Fields"].get("diastolic_field", None)
    systolic_field = config["Fields"].get("systolic_field", None)
    muscle_field = config["Fields"].get("muscle_field", None)
    temp_field = config["Fields"].get("temp_field", None)

    api_withings = "https://wbsapi.withings.net/v2"
    api_intervals = f"https://intervals.icu/api/v1/athlete/{icu_athlete_id}"

    # Authenticate or refresh token
    if os.path.isfile(cfg):
        with open(cfg, "r") as file:
            token_data = json.load(file)
            logging.debug("Token data loaded from file.")
            access_token = refresh(token_data, client_id, client_secret)
    else:
        if args.auth_code:
            access_token = authenticate(
                client_id, client_secret, redirect_uri, cfg, args.auth_code
            )
        else:
            logging.error("Authorization code is required for initial authentication.")
            sys.exit(1)

    # Determine the start date for syncing
    if args.start:
        try:
            start_date = datetime.strptime(args.start, "%Y-%m-%d")
        except ValueError:
            logging.error("Invalid start date format. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        start_date = datetime.today() - timedelta(1)

    logging.info(f"Starting sync from: {start_date.date()}")

    # Load already synced days
    synced_days = set(load_synced_days())

    # Fetch and process data
    wellness = {}
    data = get_measurements(access_token, api_withings, start_date)
    logging.debug("Measurements fetched successfully.")
    for group in data["measuregrps"]:
        day = datetime.fromtimestamp(group["date"]).date()
        if day not in wellness:
            wellness[day] = {}
        for m in group["measures"]:
            if weight_field and m["type"] == 1:
                wellness[day][weight_field] = float(m["value"] * (10 ** m["unit"]))
            if bodyfat_field and m["type"] == 6:
                wellness[day][bodyfat_field] = float(m["value"] * (10 ** m["unit"]))
            if muscle_field and m["type"] == 76:
                wellness[day][muscle_field] = float(m["value"] * (10 ** m["unit"]))
            if diastolic_field and m["type"] == 9:
                wellness[day][diastolic_field] = float(m["value"] * (10 ** m["unit"]))
            if systolic_field and m["type"] == 10:
                wellness[day][systolic_field] = float(m["value"] * (10 ** m["unit"]))
            if temp_field and m["type"] in [71, 73]:
                wellness[day][temp_field] = float(m["value"] * (10 ** m["unit"]))
        logging.debug("Day: %s - Measures: %s" % (day, wellness[day]))
    skipped_days = False
    for day, data in sorted(wellness.items()):
        if str(day) in synced_days and not args.force_resync:
            logging.debug(f"Skipping already synced day: {day}")
            skipped_days = True
            continue
        data["id"] = day.strftime("%Y-%m-%d")
        logging.info(f"Processing wellness data for {data['id']}: {data}")
        set_wellness(data, api_intervals, icu_api_key)
        synced_days.add(str(day))
    if skipped_days and not args.verbose and not args.force_resync:
        logging.info("Note that some days were skipped because already synced (you can use --force-resync if you want to sync everything)")

    save_synced_days(synced_days)
    logging.info("Sync completed successfully.")


def set_wellness(event, api_intervals, icu_api_key):
    try:
        requests.packages.urllib3.disable_warnings()
        res = requests.put(
            f'{api_intervals}/wellness/{event["id"]}',
            auth=HTTPBasicAuth("API_KEY", icu_api_key),
            json=event,
            verify=False,
        )
        if res.status_code != 200:
            logging.error(
                f"Failed to upload wellness data. Status code: {res.status_code}. Response: {res.json()}"
            )
        else:
            logging.info(f"Successfully uploaded wellness data for {event['id']}")
    except Exception as e:
        logging.exception(f"Error uploading wellness data for {event['id']}: {e}")


def authenticate(client_id, client_secret, redirect_uri, cfg, auth_code):
    try:
        res = requests.post(
            f"https://wbsapi.withings.net/v2/oauth2",
            params={
                "action": "requesttoken",
                "code": auth_code,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        out = res.json()
        if out["status"] == 0:
            with open(cfg, "w") as file:
                json.dump(out["body"], file)
            logging.info("Authentication successful. Access token saved.")
            return out["body"]["access_token"]
        else:
            logging.error(f"Authentication failed: {out}")
            sys.exit(1)
    except Exception as e:
        logging.exception(f"Error during authentication: {e}")
        sys.exit(1)


def refresh(token_data, client_id, client_secret):
    try:
        url = "https://wbsapi.withings.net/v2/oauth2"
        res = requests.post(
            url,
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "refresh_token": token_data["refresh_token"],
            },
        )
        out = res.json()
        if out["status"] == 0:
            with open("./withings.json", "w") as file:
                json.dump(out["body"], file)
            logging.info("Token refreshed successfully.")
            return out["body"]["access_token"]
        else:
            logging.error(f"Token refresh failed: {out}")
            sys.exit(1)
    except Exception as e:
        logging.exception(f"Error during token refresh: {e}")
        sys.exit(1)


def get_measurements(token, api_withings, start_date):
    try:
        url = f"{api_withings}/measure"
        res = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "action": "getmeas",
                "meastypes": "1,6,9,10,71,73,76",  # All measurement types
                "category": 1,
                "lastupdate": int(start_date.timestamp()),
            },
        )
        logging.debug("Fetched measurements from Withings API.")
        return res.json()["body"]
    except Exception as e:
        logging.exception("Error fetching measurements from Withings API.")
        sys.exit(1)


if __name__ == "__main__":
    main()
