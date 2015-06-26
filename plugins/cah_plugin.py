from pprint import pprint
import re

from cloudbot import hook
from .cah import Game, Communicator

CHAN = '#yacah'

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
  com.announce('Reloaded.')

  global game
  game = Game(com, 'data/cah_sets')


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

  if re.match(r'\d+[ \d+]*', text):
    game.process(nick, 'pick', text)


@hook.command('testing')
def command_testing(nick, conn, chan, reply, notice):
  conn.message(chan, '\x030\x03 \x021\x02 \x042\x04')
  notice(nick, '\x030\x03 \x021\x02 \x042\x04')
  reply('\x030\x03 \x021\x02 \x042\x04')

