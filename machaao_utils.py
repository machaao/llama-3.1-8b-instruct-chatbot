import json
from base64 import b64decode
from datetime import datetime

import requests
from requests.structures import CaseInsensitiveDict

c = 'UTF-8'


def get_recent(
        base_url, api_token,
        server_session_create_time,
        user_id, current_session=True):
    limit = 5

    e = "L3YxL2NvbnZlcnNhdGlvbnMvaGlzdG9yeS8="
    check = b64decode(e).decode(c)

    url = f"{base_url}{check}{user_id}/{limit}"

    headers = CaseInsensitiveDict()
    headers["api_token"] = api_token
    headers["Content-Type"] = "application/json"

    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code == 200:
        messages = resp.json()
        if current_session:
            filtered_messages = list()
            for message in messages:
                create_time_stamp = message.get("_created_at")
                create_time = datetime.strptime(create_time_stamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                if create_time > server_session_create_time:
                    filtered_messages.append(message)

            while len(filtered_messages) > 0 and (filtered_messages[0].get("type") == "outgoing"):
                _ = filtered_messages.pop(0)

            return filtered_messages
        else:
            return messages


def send(url, headers, payload=None):
    if payload:
        print("sending post to platform: " + str(payload))
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        print("response from the platform: " + str(response.text))
    else:
        response = requests.request("GET", url, headers=headers)

    return response


def get_details(api_token, base_url):
    _cache_ts_param = str(datetime.now().timestamp())
    e = "L3YxL2JvdHMvY29uZmlnP3Y9"
    check = b64decode(e).decode(c)
    url = f"{base_url}{check}{_cache_ts_param}"
    headers = {
        "api_token": api_token,
        "Content-Type": "application/json",
    }

    response = send(url, headers)

    if response and response.status_code == 200:
        return response.json()
    else:
        return {}


def check_balance(
        base_url, api_token,
        user_id, DEFAULT_HTTP_TIMEOUT=10):
    balance = 0
    e = 'L3YxL2NvaW5zL2JhbGFuY2UvY2hlY2s='
    check = b64decode(e).decode(c)

    url = f"{base_url}{check}"

    headers = CaseInsensitiveDict()
    headers["api_token"] = api_token
    headers["Content-Type"] = "application/json"

    data = {
        "userId": user_id,
        "coins": 1
    }

    resp = requests.post(
        url, data=json.dumps(data),
        headers=headers, timeout=DEFAULT_HTTP_TIMEOUT
    )

    if resp.status_code == 200:
        out = resp.json()
        if out and out["balance"]:
            balance = out["balance"]

    print(f"balance: {balance}, user_id: {user_id}")

    return balance
