import asyncio
from datetime import timedelta
import pytest

from plugins.cah import Communicator, Game
from plugins.cah.cards import BlackCard
from plugins.cah.game import PlayingCards, NoGame, WaitingForPlayers, ChoosingWinner


class FakeCommunicator(Communicator):
  def __init__(self):
    self.log = []
    return

  def reply(self, nick, msg):
    msg = msg.replace(Communicator.BOLD_MARKER, '')
    s = '({}) {}'.format(nick, msg)
    self.log.append(s)
    print('>' + s)

  def announce(self, msg):
    msg = msg.replace(Communicator.BOLD_MARKER, '')
    s = '{}'.format(msg)
    self.log.append(s)
    print('>' + s)

  def notice(self, nick, msg):
    msg = msg.replace(Communicator.BOLD_MARKER, '')
    s = '`{}` {}'.format(nick, msg)
    self.log.append(s)
    print('>' + s)


@pytest.fixture(scope='function')
def com():
  return FakeCommunicator()


@pytest.fixture(scope='function')
def g(com):
  loop = asyncio.get_event_loop()

  game = Game(com, 'data/cah_sets', '', loop)

  def d(nick, command, args='', is_pm=False):
    print('<{}: {} {}'.format(nick, command, args))
    game.process(nick, command, args, is_pm)

  game.d = d
  return game


def test_create(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  assert 'a has created a game' in com.log[-1]


def test_leave(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  assert g.creator == 'a'

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('b', 'leave')
  assert set(g.players) == {'a', 'c'}


def test_game(com, g):
  """
  :type com: Communicator
  :type g: Game
  """

  g.d('a', 'create')

  g.deck.black_pool = []
  for i in range(5):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('a', 'start')
  assert type(g.phase) == PlayingCards

  g.czar = 'a'
  g.czar_index = g.players.index('a')

  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')

  assert 'Everyone has played' in ' '.join(com.log)

  g.d('a', 'pick', '0')

  l = ' '.join(com.log)
  assert 'b wins with' in l or 'c wins with' in l


def test_several_games(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'limit', '10')
  g.d('b', 'join')
  g.d('c', 'join')
  g.d('a', 'start')
  assert type(g.phase) == PlayingCards

  for i in range(10):
    g.czar_index = g.players.index('a')
    g.czar = 'a'

    g.d('b', 'pick', '0')
    g.d('c', 'pick', '0')

    assert 'Everyone has played' in ' '.join(com.log[-3:])

    g.d('a', 'pick', str(g.player_perm.index('b')))

    l = ' '.join(com.log[-8:])
    assert 'b wins with' in l or 'c wins with' in l

  assert 'game is over! b won!' in ' '.join(com.log[-3:])


def test_playleave(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('d', 'join')
  g.d('a', 'start')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  assert len(g.players) == 4

  g.d('a', 'pick', '0')
  g.d('a', 'leave')

  assert len(g.players) == 3
  assert len(g.played) == 0
  assert g.czar != 'a'

  assert 'Restarting the round' in ' '.join(com.log[:-5])


def test_playjoin(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('a', 'start')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('d', 'join')

  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')

  g.d('a', 'pick', '0')

  assert 'd' in g.players


def test_choosejoinleave(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('d', 'join')
  g.d('a', 'start')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')
  g.d('d', 'pick', '0')

  g.d('e', 'join')
  g.d('a', 'leave')

  assert 'Round 0' in ' '.join(com.log)
  assert 'e' in g.players


def test_status(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('b', 'join')
  g.d('c', 'join')
  g.d('d', 'join')
  g.d('a', 'start')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('a', 'status')
  assert '4 players' in com.log[-1]
  assert 'Black card:' in com.log[-1]
  assert 'Waiting for' in com.log[-1]

  g.d('a', 'cards')
  assert 'Your hand:' in com.log[-1]

  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')
  g.d('d', 'pick', '0')

  g.d('a', 'status')
  assert 'Waiting for card czar' in com.log[-1]


def test_sets(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'la')
  assert 'Main Deck' in com.log[-1]

  g.d('a', 'create')

  g.d('a', 'lu')
  assert 'Main Deck' in com.log[-1]

  g.d('a', 'list_sets')
  assert 'Main Deck' in com.log[-1]

  g.d('a', 'list_used_sets')
  assert 'Main Deck' in com.log[-1]

  def_count = len(g.deck.used_sets)

  g.d('a', 'remove_set', '0')
  assert len(g.deck.used_sets) == def_count - 1

  g.d('a', 'leave')
  g.d('a', 'create')
  assert len(g.deck.used_sets) == def_count

  g.d('a', 'add_set', 'all')
  assert len(g.deck.used_sets) > def_count


def test_scores(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'c')

  g.d('b', 'j')
  g.d('c', 'j')

  g.d('a', 'st')

  g.d('a', 'sc')

  for i in 'abc':
    assert i in com.log[-1]


def test_rando(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'c')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'rando', 'on')
  g.d('b', 'j')
  g.d('a', 'st')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('b', 'pick', '0')

  g.d('a', 'pick', str(g.player_perm.index(g.RANDO_NICK)))

  g.d('a', 'sc')
  assert 'Cardrissian-1p' in com.log[-1]


def test_blanks(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'c')
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))
  g.deck.white_pool = []

  g.d('a', 'blank', '100')
  g.d('b', 'j')
  g.d('c', 'j')

  g.d('a', 'st')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('b', 'write', '8 TEST', True)
  g.d('b', 'pick', '8')

  assert 'TEST' in com.log[-1]


def test_help(com: Communicator, g: Game):
  g.d('a', '?')
  assert 'Commands in this phase' in com.log[-1] and 'create' in com.log[-1] and \
         'wtf' in com.log[-1]

  g.d('a', '?', '?')
  assert 'help [<command>]' in com.log[-1]


def test_pucki(com: Communicator, g: Game):
  g.d('a', 'c')

  g.d('b', 'j')
  g.d('c', 'j')
  g.d('d', 'j')

  g.d('a', 'st')
  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')
  g.d('d', 'pick', '0')

  g.d('c', 'leave')
  g.d('c', 'hand')


def test_swap(com: Communicator, g: Game):
  g.d('a', 'c')

  g.d('b', 'j')
  g.d('c', 'j')

  g.d('a', 'st')
  g.czar_index = g.players.index('a')
  g.czar = 'a'

  g.scores.point('b')

  g.d('b', 'c')
  prev_hand = com.log[-1]

  g.d('b', 'swap')
  assert 'traded one point' in ' '.join(com.log[-5:])
  new_hand = com.log[-1]

  assert prev_hand != new_hand


def test_timeouts(com: Communicator, g: Game):
  g.WAITING_FOR_PLAYERS_TIMEOUT = timedelta(seconds=0.5)
  g.PLAYING_CARDS_TIMEOUT = timedelta(seconds=0.5)
  g.CHOOSING_WINNER_TIMEOUT = timedelta(seconds=0.5)

  @asyncio.coroutine
  def checker(g: Game, time, expected_phase):
    yield from asyncio.sleep(time)
    assert type(g.phase) == expected_phase

  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))
  g.deck.white_pool = []

  g.reset()
  g.d('a', 'c')

  assert type(g.phase) == WaitingForPlayers
  g.loop.run_until_complete(asyncio.async(checker(g, 0.75, NoGame)))

  g.reset()
  g.d('a', 'c')
  g.d('b', 'j')
  g.d('c', 'j')
  g.d('a', 'st')

  assert type(g.phase) == PlayingCards
  g.loop.run_until_complete(asyncio.async(checker(g, 0.75, PlayingCards)))

  g.reset()
  g.d('a', 'c')
  g.d('b', 'j')
  g.d('c', 'j')
  g.d('d', 'j')
  g.d('a', 'st')
  g.czar_index = g.players.index('a')
  g.czar = 'a'
  g.d('b', 'pick', '0')
  g.d('c', 'pick', '0')

  assert type(g.phase) == PlayingCards
  g.loop.run_until_complete(asyncio.async(checker(g, 0.75, ChoosingWinner)))

  g.loop.run_until_complete(asyncio.async(checker(g, 0.5, PlayingCards)))
