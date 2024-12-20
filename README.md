
# Withings2Intervals

A Python script to sync wellness data from Withings to [Intervals.icu](https://intervals.icu).

This script is a fork of [this Gist](https://gist.github.com/fruitloop/7e79eeab9fd4ba7d2be5cdf8175d2267) and has been enhanced with features such as:
- Configurable start dates for syncing.
- Prevention of duplicate syncing using a log file.
- Added debugging support via a `-v` flag.
- Refactored for better maintainability and extensibility.

## Features
- Fetches data from Withings using their API.
- Uploads wellness data (weight, body fat, blood pressure, etc.) to Intervals.icu.
- Tracks synced days to avoid duplicate uploads.
- Supports a `--force-resync` option to re-upload data.
- Debugging support with `-v`.

## Installation from pip
You can simply install the package from PyPi
```bash
pip install withings2intervals
```

## Installation from repository

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/withings_syncer.git
   cd withings_syncer
   ```

2. **Install Dependencies with Poetry**:
   Make sure you have [Poetry](https://python-poetry.org/docs/#installation) installed.
   ```bash
   poetry install
   ```

3. **Enter poetry virtual env**
   ```bash
   poetry shell
   ```

## Setup

### 1. Create a Withings Developer App
1. Go to the [Withings Developer Portal](https://developer.withings.com/).
2. Sign in and create a new app:
   - **App Name**: Choose a name (e.g., "Withings Syncer").
   - **Callback URL**: Use `http://localhost:80`.
   - Save the app and copy the **Client ID** and **Client Secret** to the `config.ini`

### 2. Get your intervals.icu keys
1. Go to the [Intervals.icu settings page](https://intervals.icu/settings)
2. Scroll until you see **Developer Settings**
3. Click on "API Key (view)"
4. Click on "Generate"
5. Copy the generated API key to the `config.ini`
6. Copy also the "Athlete ID" to `config.ini`

## 3. Run initial authentication
1. Run `python withings2intervals.py`
2. Follow on screen instructions

Once the initial authentication is successfully completed your OAuth2 token will be saved locally and you will be able to run subsequent synchronizations.

## Usage

Run the script with the following options:

- **Sync Today's Data**:
  ```bash
  python withings2intervals.py
  ```

- **Sync Data from a Specific Date**:
  ```bash
  python withings2intervals.py --start 2024-12-01
  ```

- **Force Resync**:
  ```bash
  python withings2intervals.py --start 2024-12-01 --force-resync
  ```

- **Verbose Debugging**:
  ```bash
  python withings2intervals.py -v
  ```

## Acknowledgments
- [Fruitloop's Original Gist](https://gist.github.com/fruitloop/7e79eeab9fd4ba7d2be5cdf8175d2267)
