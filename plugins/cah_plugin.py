import re
import asyncio

from cloudbot import hook
from .cah import Game, Communicator, Set


@asyncio.coroutine
@hook.irc_raw("NICK")
def on_nick(irc_raw):
  global game
  old_nick, new_nick = re.findall(r':([^!]+)', irc_raw)

  if old_nick in game.players + game.joiners:
    game.process(old_nick, 'leave', '')


@asyncio.coroutine
@hook.irc_raw("PART")
def on_part(chan, nick):
  if chan == game.chan and nick in game.players + game.joiners:
    game.process(nick, 'leave', '')


@asyncio.coroutine
@hook.irc_raw("QUIT")
def on_quit(nick):
  if nick in game.players + game.joiners:
    game.process(nick, 'leave', '')


@hook.irc_raw("004")
def on_ready(conn, chan, bot):
  global game
  game_chan = conn.config \
    .get('plugins', {}) \
    .get('yacah', {}) \
    .get('yacahb_chan', None)

  com = Communicator(conn, game_chan)

  game = Game(com, 'data/cah_sets', game_chan)

  com.announce('Reloaded.')


@hook.regex('^.+$')
def catch_all(nick, chan, match):
  if chan != game.chan:
    return

  text = match.group(0)
  parts = text.split(maxsplit=1)

  if len(parts) == 0:
    return

  command = parts[0]

  args = parts[1] if len(parts) > 1 else ''

  game.process(nick, command, args)

  if re.match(r'^\d+[ \d+]*$', text):
    game.process(nick, 'pick', text)


@asyncio.coroutine
@hook.command('load_set', permissions=['botcontrol'])
def command_load_set(text):
  try:
    set = Set.load(text)
    set.to_file(game.card_dir)
    game.deck.read_dir(game.card_dir)
    return 'Successfully loaded {}.'.format(set.name)
  except Exception as e:
    return 'Error: {}'.format(e.args)

