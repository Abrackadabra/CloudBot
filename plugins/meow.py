import requests

from cloudbot import hook

API_URL = 'http://thecatapi.com/api/images/get'


@hook.on_start
def on_start(bot):
    """loads the API key"""
    global api_key
    api_key = bot.config.get("api_keys", {}).get("cat_api", None)


@hook.command()
def meow():
    """meow – Returns a random cat. (^ ◕ᴥ◕ ^)"""
    if not api_key:
        return 'This command requires an API key from thecatapi.com.'
    try:
        r = requests.get(API_URL, params={
            'api_key': api_key
        })
        return r.url
    except Exception:
        return 'Couldn\'t get a cat picture for you (;_;)'
