import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from pprint import pprint
import configparser
import argparse

# Load configuration from a config file
def load_config(config_file):
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        print(f"Configuration file {config_file} not found!")
        sys.exit(1)
    config.read(config_file)
    return config

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Sync Withings data to Intervals.icu")
    parser.add_argument("--config", type=str, default="./config.ini", help="Path to the configuration file")
    parser.add_argument("--auth-code", type=str, help="Authorization code for initial authentication")
    return parser.parse_args()

def main():
    args = parse_args()
    config = load_config(args.config)

    # Load API credentials and configuration
    client_id = config['Withings']['client_id']
    client_secret = config['Withings']['client_secret']
    redirect_uri = config['Withings']['redirect_uri']
    icu_api_key = config['Intervals']['icu_api_key']
    icu_athlete_id = config['Intervals']['icu_athlete_id']
    cfg = config['General']['withings_config']
    print(cfg)

    # Load optional fields
    weight_field = config['Fields'].get('weight_field', None)
    bodyfat_field = config['Fields'].get('bodyfat_field', None)
    diastolic_field = config['Fields'].get('diastolic_field', None)
    systolic_field = config['Fields'].get('systolic_field', None)
    muscle_field = config['Fields'].get('muscle_field', None)
    temp_field = config['Fields'].get('temp_field', None)

    api_withings = 'https://wbsapi.withings.net/v2'
    api_intervals = f'https://intervals.icu/api/v1/athlete/{icu_athlete_id}'

    # Authenticate or refresh token
    if os.path.isfile(cfg):
        with open(cfg, 'r') as file:
            token_data = json.load(file)
            access_token = refresh(token_data, client_id, client_secret)
    else:
        if args.auth_code:
            access_token = authenticate(client_id, client_secret, redirect_uri, cfg, args.auth_code)
        else:
            print("Authorization code is required for initial authentication.")
            sys.exit(1)

    # Fetch and process data
    wellness = {}
    data = get_measurements(access_token, api_withings)
    for group in data['measuregrps']:
        day = datetime.fromtimestamp(group['date']).date()
        if day not in wellness:
            wellness[day] = {}
        for m in group['measures']:
            if weight_field and m['type'] == 1:
                wellness[day][weight_field] = float(m['value'] * (10 ** m['unit']))
            if bodyfat_field and m['type'] == 6:
                wellness[day][bodyfat_field] = float(m['value'] * (10 ** m['unit']))
            if muscle_field and m['type'] == 76:
                wellness[day][muscle_field] = float(m['value'] * (10 ** m['unit']))
            if diastolic_field and m['type'] == 9:
                wellness[day][diastolic_field] = float(m['value'] * (10 ** m['unit']))
            if systolic_field and m['type'] == 10:
                wellness[day][systolic_field] = float(m['value'] * (10 ** m['unit']))
            if temp_field and m['type'] in [71, 73]:
                wellness[day][temp_field] = float(m['value'] * (10 ** m['unit']))
    for day, data in sorted(wellness.items()):
        data['id'] = day.strftime('%Y-%m-%d')
        print(data)
        set_wellness(data, api_intervals, icu_api_key)

def set_wellness(event, api_intervals, icu_api_key):
    requests.packages.urllib3.disable_warnings()
    res = requests.put(f'{api_intervals}/wellness/{event["id"]}',
                       auth=HTTPBasicAuth('API_KEY', icu_api_key), json=event, verify=False)
    if res.status_code != 200:
        print('Upload wellness data failed with status code:', res.status_code)
        print(res.json())

def authenticate(client_id, client_secret, redirect_uri, cfg, auth_code):
    if auth_code:
        res = requests.post(f'https://wbsapi.withings.net/v2/oauth2', params={
            'action': 'requesttoken', 'code': auth_code,
            'client_id': client_id, 'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        })
        out = res.json()
        if out['status'] == 0:
            json.dump(out['body'], open(cfg, 'w'))
            return out['body']['access_token']
        else:
            print('Authentication failed:')
            print(out)
            exit()
    else:
        print('Provide the authorization code using --auth-code argument')
        exit()

def refresh(token_data, client_id, client_secret):
    url = 'https://wbsapi.withings.net/v2/oauth2'
    res = requests.post(url, params={
        'client_id': client_id,
        'client_secret': client_secret,
        'action': 'requesttoken',
        'grant_type': 'refresh_token',
        'refresh_token': token_data['refresh_token'],
    })
    out = res.json()
    if out['status'] == 0:
        with open('./withings.json', 'w') as file:
            json.dump(out['body'], file)
        return out['body']['access_token']
    else:
        print("Token refresh failed:", out)
        sys.exit(1)

def get_measurements(token, api_withings):
    start = datetime(2023, 11, 1)
    url = f'{api_withings}/measure'
    res = requests.get(url, headers={'Authorization': f'Bearer {token}'}, params={
        'action': 'getmeas', 'meastypes': '1,6,9,10,71,73,76',
        'category': 1,
        'lastupdate': start.strftime('%s'),
        'startdate': start.strftime('%s'),
    })
    pprint(res.json()['body'], width=4)
    return res.json()['body']

if __name__ == '__main__':
    main()