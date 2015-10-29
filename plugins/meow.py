import requests

from cloudbot import hook

API_URL = 'http://thecatapi.com/api/images/get'


@hook.on_start
def on_start(bot):
    """loads the API key"""
    global api_key
    api_key = bot.config.get("api_keys", {}).get("cat_api", None)


@hook.command(autohelp=False)
def meow(text):
    """meow [jpg|png|gif] – Returns a random cat. (^ ◕ᴥ◕ ^)"""
    types = ['jpg', 'png', 'gif']
    type = None
    if text:
        if text not in types:
            return 'Incorrect type. Should be jpg|png|gif.'
        type = text
    if not api_key:
        return 'This command requires an API key from thecatapi.com.'
    try:
        params = {
            'api_key': api_key
        }
        if type:
            params['type'] = type
        r = requests.get(API_URL, params=params)
        return r.url
    except Exception:
        return 'Couldn\'t get a cat picture for you (;_;)'
