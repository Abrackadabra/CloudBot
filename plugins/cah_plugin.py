from pprint import pprint

from cloudbot import hook
from .cah import Game, Communicator

CHAN = '#abratest3'

# @hook.on_start
# def on_start(conn):
#   com = Communicator(conn, '#abratest3')
#   print('IMPORTANT', conn, type(conn))
#
#   global game
#   game = Game(com, 'data/cah')

@hook.irc_raw("004")
def on_ready(conn):
  com = Communicator(conn, CHAN)
  print('IMPORTANT', conn, type(conn))

  global game
  game = Game(com, 'data/cah')


@hook.regex('^.+$')
def command_create(nick, chan, match):
  if chan != CHAN:
    return

  text = match.group(0)
  parts = text.split(maxsplit=1)

  if len(parts) == 0:
    return

  command = parts[0]

  args = parts[1] if len(parts) > 1 else ''

  game.process(nick, command, args)


@hook.command('testing')
def command_testing(conn):
  pprint(dir(conn))
  return 'whaaa'

