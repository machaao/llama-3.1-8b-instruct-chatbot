import base64
import json
import os
import random
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from requests.structures import CaseInsensitiveDict
from snips_nlu import SnipsNLUEngine
from transformers import AutoTokenizer

from machaao_utils import check_balance

ban_words = ["nigger", "negro", "nazi", "faggot", "murder", "suicide"]

# list of banned input words
c = 'UTF-8'
load_dotenv()
hf_token = os.environ["HUGGINGFACEHUB_API_TOKEN"]


def intent_classifier(text):
    parent = Path(__file__).parent.parent.absolute()
    path_to_engine = os.path.join(parent, "nlu", "engine", "base")
    # text = self.session.user_message
    loaded_engine = SnipsNLUEngine.from_path(path_to_engine)
    nlu_obj = loaded_engine.parse(text)
    intent = nlu_obj.get("intent")
    intent_name = intent.get("intentName")
    return intent_name


COST_PER_CREDIT_IN_MILLI_CENTS = os.environ.get('COST_PER_CREDIT_IN_MILLI_CENTS', 334)  # 1/299 -> 299 credits for $1
MIN_CREDITS_AWARD = os.environ.get("MIN_REWARD", 9)
MAX_CREDITS_AWARD = os.environ.get("MAX_REWARD", 15)


def send(url, headers, payload=None):
    if payload:
        print("sending post to platform: " + str(payload))
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        print("response from the platform: " + str(response.text))
    else:
        response = requests.request("GET", url, headers=headers)

    return response


# don't change for sanity purposes
def get_details(api_token, base_url):
    _cache_ts_param = str(datetime.now().timestamp())
    e = "L3YxL2JvdHMvY29uZmlnP3Y9"
    check = base64.b64decode(e).decode(c)
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


class BotLogic:
    def __init__(self, server_session_create_time):
        # Initializing Config Variables

        self.api_token = os.environ.get("API_TOKEN")
        self.base_url = os.environ.get("BASE_URL", "https://ganglia.machaao.com")
        self.name = os.environ.get("NAME")
        self.limit = os.environ.get("LIMIT", 'True')
        self.server_session_create_time = server_session_create_time
        self.model = os.environ.get("MODEL_NAME")
        self.client = InferenceClient(self.model, token=hf_token)
        self.tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct", token=hf_token)

    @staticmethod
    def read_prompt(name):
        file_name = "./logic/prompt.txt"
        with open(file_name) as f:
            prompt = f.read()

        return prompt.replace("[name]", f"{name}")

    def get_recent(self, user_id: str, current_session=True):
        limit = 5
        url = f"{self.base_url}/v1/conversations/history/{user_id}/{limit}"

        headers = CaseInsensitiveDict()
        headers["api_token"] = self.api_token
        headers["Content-Type"] = "application/json"

        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            messages = resp.json()
            if current_session:
                filtered_messages = list()
                for message in messages:
                    create_time_stamp = message.get("_created_at")
                    create_time = datetime.strptime(create_time_stamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if create_time > self.server_session_create_time:
                        filtered_messages.append(message)

                while len(filtered_messages) > 0 and (filtered_messages[0].get("type") == "outgoing"):
                    _ = filtered_messages.pop(0)

                return filtered_messages
            else:
                return messages

    @staticmethod
    def parse(data):
        msg_type = data.get('type')
        if msg_type == "outgoing":
            msg_data = json.loads(data['message'])
            msg_data_2 = json.loads(msg_data['message']['data']['message'])

            if msg_data_2 and msg_data_2.get('text', ''):
                text_data = msg_data_2['text']
            elif msg_data_2 and msg_data_2['attachment'] and msg_data_2['attachment'].get('payload', '') and \
                    msg_data_2['attachment']['payload'].get('text', ''):
                text_data = msg_data_2['attachment']['payload']['text']
            else:
                text_data = ""
        else:
            msg_data = json.loads(data['incoming'])
            if msg_data['message_data']['text']:
                text_data = msg_data['message_data']['text']
            else:
                text_data = ""

        return msg_type, text_data

    def core(self, req: str, label: str, user_id: str, client: str, sdk: str, action_type: str, api_token: str):
        intent_name = intent_classifier(text=req)
        balance = check_balance(self.base_url, api_token, user_id)

        if intent_name == "balance":
            resp = f"Your current balance is {balance} Credits"
            resp_type = "balance"
            if client != "web":
                credit_reward = random.randint(MIN_CREDITS_AWARD, MAX_CREDITS_AWARD)
                resp_type = resp_type + "_" + credit_reward
            return False, resp, resp_type

        if balance <= 0:
            reply = "Oops, your credits are exhausted. Please top up your balance and try again."
            return False, reply, "text"

        print(
            "input text: " + req + ", label: " + label + ", user_id: " + user_id + ", client: " + client + ", sdk: " + sdk
            + ", action_type: " + action_type + ", api_token: " + api_token)

        bot = get_details(api_token, self.base_url)
        name = self.name

        if not bot:
            return False, "Oops, the chat bot doesn't exist or is not active at the moment"
        else:
            name = bot.get("displayName", name)

        valid = True

        recent_text_data = self.get_recent(user_id)
        recent_convo_length = len(recent_text_data)

        print(f"len of history: {recent_convo_length}")

        banned = any(ele in req for ele in ban_words)

        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": f"assistant", "content": "I'm doing great. How can I help you today?"}
        ]

        if banned:
            print(f"banned input:" + str(req) + ", id: " + user_id)
            return False, "Oops, please refrain from such words", "text"

        for text in recent_text_data[::-1]:
            msg_type, text_data = self.parse(text)

            if text_data:
                e_message = "Oops," in text_data and "connect@machaao.com" in text_data

                if msg_type is not None and not e_message:
                    # outgoing msg - bot msg
                    messages.append({
                        "role": f"assistant",
                        "content": text_data
                    })
                else:
                    # incoming msg - user msg
                    messages.append({
                        "role": "user",
                        "content": text_data
                    })

        try:
            reply = self.process_via_huggingface(name, messages)
            return valid, reply, "text"
        except Exception as e:
            print(f"error - {e}, for {user_id}")
            return False, "Oops, I am feeling a little overwhelmed with messages\nPlease message me later", "text"

    def process_via_huggingface(self, name, messages):

        _prompt = self.read_prompt(name)
        system = [{"role": "system", "content": f"{_prompt}"}]
        messages[:0] = system

        print(f"processing for {self.model}")

        message = self.client.chat_completion(
            messages=messages,
            max_tokens=500,
            stream=False,
        )

        resp = message.choices[0].message.content
        print(resp)

        return resp
