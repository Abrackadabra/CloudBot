from os import system

import pytest

from plugins.cah import Communicator, Game
from plugins.cah.deck import BlackCard
from plugins.cah.game import PlayingCards


class FakeCommunicator(Communicator):
  def __init__(self):
    self.log = []
    return

  def reply(self, nick, msg):
    s = '({}) {}'.format(nick, msg)
    self.log.append(s)
    print('>' + s)

  def announce(self, msg):
    s = '{}'.format(msg)
    self.log.append(s)
    print('>' + s)

  def notice(self, nick, msg):
    s = '`{}` {}'.format(nick, msg)
    self.log.append(s)
    print('>' + s)


@pytest.fixture(scope='function')
def com():
  return FakeCommunicator()


@pytest.fixture(scope='function')
def g(com):
  game = Game(com, 'data/cah')

  def d(nick, command, args=''):
    print('<{}: {} {}'.format(nick, command, args))
    game.process(nick, command, args)

  game.d = d
  return game


def test_create(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.d('a', 'create')
  assert com.log[-1] == 'Game is started!'


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
  g.deck.black_pool = []
  for i in range(5):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'create')
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
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'create')
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

    g.d('a', 'pick', '0')

    l = ' '.join(com.log[-8:])
    assert 'b wins with' in l or 'c wins with' in l

  assert 'game is over' in ' '.join(com.log[-3:])


def test_playleave(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'create')
  g.d('b', 'join')
  g.d('c', 'join')
  g.d('d', 'join')
  g.d('a', 'start')

  g.czar_index = g.players.index('a')
  g.czar = 'a'

  assert len(g.players) == 4

  g.d('a', 'leave')

  assert len(g.players) == 3
  assert g.czar != 'a'

  assert 'Restarting the round' in ' '.join(com.log[:-5])


def test_playjoin(com, g):
  """
  :type com: Communicator
  :type g: Game
  """
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'create')
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
  g.deck.black_pool = []
  for i in range(20):
    g.deck.black_pool.append(BlackCard(text='dummy card {} %s.'.format(i), gaps=1))

  g.d('a', 'create')
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

  assert 'Round 0' in ' '.join(com.log[-8:])
  assert 'e' in g.players
