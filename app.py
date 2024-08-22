import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import jwt
import pytz
import requests
from dotenv import load_dotenv
from flask import Flask, request
from machaao import Machaao

from logic.bot_logic import BotLogic

app = Flask(__name__)

load_dotenv()

api_token = os.environ.get("API_TOKEN")
base_url = os.environ.get("BASE_URL", "https://ganglia.machaao.com")
name = os.environ.get("NAME", "")
text_credit = int(os.environ.get("CREDIT", 5))
error_message = "invalid configuration detected, check your .env file for missing parameters"
params = [api_token, base_url, name]

error = False
for param in params:
    if not param:
        error = True
        break

# error = not name or not base_url or not api_token or not nlp_token

if not error:
    machaao = Machaao(api_token, base_url)
else:
    print(error)


# noinspection PyProtectedMember
def exception_handler(exception):
    caller = sys._getframe(1).f_code.co_name
    print(f"{caller} function failed")
    if hasattr(exception, 'message'):
        print(exception.message)
    else:
        print("Unexpected error: ", sys.exc_info()[0])


def extract_sender(req):
    try:
        return req.headers["machaao-user-id"]
    except Exception as e:
        exception_handler(e)


def send_reply(valid: bool, text: str, resp_type: str, user_id: str, client: str, sdk: float, _api_token: str):
    try:
        if client == "web":
            msg = {
                "users": [user_id],
                "message": {
                    "text": text,
                    "quick_replies": [],
                    "attachment": {
                        "payload": {
                            "template_type": "button",
                            "buttons": []
                        }
                    }
                },
                "credit": text_credit,
                "ad": True
            }
        else:
            msg = {
                "users": [user_id],
                "message": {
                    "text": text,
                    "quick_replies": [],
                    "attachment": {
                        "payload": {
                            "buttons": []
                        }
                    }

                },
                "credit": text_credit,
                "ad": True
            }

        if "balance" in resp_type:
            msg = {
                "users": [user_id],
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "button",
                            "text": text,
                            "buttons": []
                        }
                    }
                },
                "credit": 0,
                "ad": True
            }

            buttons = [
                {
                    "type": "buy",
                    "title": "Buy 299 Credits",
                    "payload": 299
                }, {
                    "type": "earn",
                    "title": "Earn Credits",
                    "payload": "pf"
                },
            ]
            if "_" in resp_type:
                reward = resp_type.split("_")[1]
                payload = jwt.encode({
                    "sub": user_id + "_" + str(reward) + "_e_" + api_token,
                    "exp": datetime.now(tz=timezone.utc) + timedelta(days=2)
                }, api_token, algorithm="HS512")
                buttons.append({
                    "type": "earn",
                    "title": f"Get {reward} credits for FREE",
                    "payload": payload
                })
            msg["message"]["attachment"]["payload"]["buttons"] = buttons
            msg["credit"] = 0

        if valid and msg and msg["message"]:
            msg["message"]["quick_replies"] = [{
                "content_type": "text",
                "payload": "👍",
                "title": "👍"
            }, {
                "content_type": "text",
                "payload": "👎",
                "title": "👎"
            }, {
                "content_type": "text",
                "payload": "continue",
                "title": "➡️ Continue"
            }]

        else:
            msg["message"]["quick_replies"] = [{
                "content_type": "text",
                "payload": "balance",
                "title": "Balance 🏦"
            }]

        machaao.send_message(payload=msg)

    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        exception_handler(e)


def extract_message(req):
    """
    Decrypts the request body, and parses the incoming message
    """
    decoded_jwt = None
    body = req.json
    if body and body["raw"]:
        decoded_jwt = jwt.decode(body["raw"], api_token, algorithms=['HS512'])
    text = decoded_jwt["sub"]
    if type(text) == str:
        text = json.loads(decoded_jwt["sub"])

    sdk = text["messaging"][0]["version"]
    sdk = sdk.replace('v', '')
    client = text["messaging"][0]["client"]

    try:
        action_type = text["messaging"][0]["message_data"]["action_type"]
    except Exception as e:
        action_type = "text"
        traceback.print_exc(file=sys.stdout)
        exception_handler(e)

    return text["messaging"][0]["message_data"]["text"], text["messaging"][0]["message_data"][
        "label"], client, sdk, action_type


@app.route('/', methods=['GET'])
def root():
    return "ok"


@app.route('/machaao/hook', methods=['GET', 'POST'])
def receive():
    return process_response(request)


def process_response(request):
    _api_token = request.headers["bot-token"]
    sender_id = extract_sender(request)
    recv_text, label, client, sdk, action_type = extract_message(request)

    valid_request, reply, resp_type = logic.core(recv_text, label, sender_id, client, sdk, action_type, _api_token)

    send_reply(valid_request, reply, resp_type, sender_id, client, eval(sdk), _api_token)

    return "ok"


if __name__ == '__main__':
    if not error:
        server_session_create_time = datetime.now(tz=pytz.utc).replace(tzinfo=None)
        logic = BotLogic(server_session_create_time)
        app.run(debug=False, port=5000)
    else:
        print(f"{error_message}")
