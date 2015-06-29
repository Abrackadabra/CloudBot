import random

from .cards import Deck
from .score import Scores


class Game(object):
  RANDO_NICK = 'Rando Cardrissian'

  def __init__(self, com, card_dir, chan):
    """
    :type com: Communicator
    """
    self.com = com
    self.chan = chan

    self.card_dir = card_dir
    self.deck = Deck(card_dir)

    self.phase = NoGame()

    self.reset()

  def process(self, nick, command, args):
    self.phase = self.phase.process(self, nick, command.lower(), args) or self.phase

  def reset(self):
    self.players = []
    self.creator = ''
    self.hands = {}

    self.scores = Scores()

    self.round = 0

    self.black_card = None
    """:type : deck.BlackCard"""

    self.czar_index = -1
    self.czar = ''
    self.played = {}
    self.player_perm = []

    self.joiners = []
    self.limit = 5

    self.deck.reset()

    self.rando = False

    self.blanks = 0

    self.phase = NoGame()

  def list_players(self):
    r = list(self.players)
    if self.rando:
      r.append(self.RANDO_NICK)
    return r

  def count_players(self):
    return len(self.list_players())


class Command(object):
  """
  Decorator for command-handling methods in GamePhases.
  """

  def __init__(self, names=None, player_only=False):
    self.names = names
    self.player_only = player_only

  def __call__(self, f):
    if not self.names:
      self.names = [f.__name__]

    f.names = self.names
    f.command = True
    f.player_only = self.player_only

    return f

  @staticmethod
  def is_command(f):
    return callable(f) and hasattr(f, 'command') and hasattr(f, 'names') \
           and hasattr(f, 'player_only')


class GamePhase(object):
  def copy_command(self, method):
    name = method.__name__
    copy = lambda *args, **kwargs: method(self, *args, **kwargs)
    copy = Command(names=method.names)(copy)
    setattr(self, name, copy)

  def process(self, g: Game, nick, command, args):
    for i in dir(self):
      method = getattr(self, i)
      if Command.is_command(method) and command in method.names:
        if method.player_only and nick not in g.players:
          continue

        return method(g, nick, args)

  def next_czar(self, g: Game):
    g.czar_index = (g.czar_index + 1) % len(g.players)
    g.czar = g.players[g.czar_index]


class NoGame(GamePhase):
  def __init__(self):
    self.copy_command(WaitingForPlayers.list_sets)

  @Command(names=['create', 'c'])
  def create(self, g: Game, nick, args):
    g.com.announce('`{}` has created a game! Type `j` to join.'.format(nick))

    g.reset()

    g.creator = nick
    g.players = [nick]

    return WaitingForPlayers()

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    g.com.announce('No one is playing.')


class WaitingForPlayers(GamePhase):
  @Command(names=['join', 'j'])
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
    else:
      g.players.append(nick)
      g.com.announce('`{}` has joined the game. `{}` players total.'
                     ''.format(nick, g.count_players()))

  @Command(names=['leave'], player_only=True)
  def leave(self, g: Game, nick, args):
    g.players.remove(nick)
    g.com.announce(
      '`{}` has left the game. `{}` players remaining.'.format(nick, g.count_players()))

    if nick == g.creator:
      g.com.announce('Creator has left the game. Game aborted.')
      g.reset()
      return NoGame()

  @Command(names=['start', 'st'], player_only=True)
  def start(self, g: Game, nick, args):
    if nick != g.creator:
      g.com.notice(nick, 'Only `{}` can start the game.'.format(g.creator))
    elif g.count_players() < 3:
      g.com.reply(nick, 'Need at least `3` players to start a game.')
    else:
      new_state = PlayingCards()
      return new_state.deal(g) or new_state.act(g) or new_state

  @Command(names=['limit', 'l'])
  def limit(self, g: Game, nick, args):
    parts = args.split()
    if len(parts) == 0:
      g.com.reply(nick, 'Current point limit is `{}` points.'.format(g.limit))
      return

    if not parts[0].isnumeric():
      g.com.notice(nick, 'Invalid argument.')
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only `{}` can change the point limit.'.format(g.creator))
      return

    c = int(parts[0])
    if 0 < c < 100:
      g.limit = c
      g.com.announce('`{}` changed the point limit to `{}`.'.format(nick, c))
    else:
      g.com.notice(nick, 'Invalid number.')

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    g.com.announce('Waiting for people to join. Creator: `{}`. `{}` players: {}.'
                   ''.format(g.creator, g.count_players(), ', '.join(g.list_players())))

  @Command(names=['list_sets', 'listsets', 'listall', 'list_all', 'la'])
  def list_sets(self, g: Game, nick, args):
    sets = g.deck.list_all_sets()
    g.com.announce(
      'All card sets: ' + ', '.join(['[`{}`] {}'.format(i, j) for i, j in enumerate(sets)]))

  @Command(names=['list_used', 'listused', 'lu'])
  def list_used_sets(self, g: Game, nick, args):
    sets = g.deck.list_used_sets()
    g.com.announce(
      'Used card sets: ' + ', '.join(['[`{}`] {}'.format(i, j) for i, j in enumerate(sets)]))

  @Command(names=['add_set', 'addset', 'add', 'a'])
  def add_set(self, g: Game, nick, args):
    if nick != g.creator:
      g.com.notice(nick, 'Only `{}` can change used card sets.'.format(g.creator))
      return

    parts = args.split()

    if len(parts) == 0 or (any(not i.isnumeric() for i in parts) and parts[0] != 'all'):
      g.com.notice(nick, 'Invalid argument.')
      return

    sets = g.deck.list_all_sets()

    if parts[0] == 'all':
      c = list(range(len(sets)))
    else:
      c = [int(i) for i in parts]
    for i in c:
      if i < 0 or i >= len(sets):
        g.com.notice(nick, 'Invalid index `{}`.'.format(i))
        return

      g.deck.add_set(sets[i])
    self.list_used_sets(g, nick, args)

  @Command(names=['remove_set', 'removeset', 'remove', 'r'])
  def remove_set(self, g: Game, nick, args):
    if nick != g.creator:
      g.com.notice(nick, 'Only `{}` can change used card sets.'.format(g.creator))
      return

    parts = args.split()
    if len(parts) == 0 or not parts[0].isnumeric():
      g.com.notice(nick, 'Invalid argument.')
      return

    sets = g.deck.list_used_sets()
    c = int(parts[0])
    if c < 0 or c >= len(sets):
      g.com.notice(nick, 'Invalid index.')
      return

    if len(sets) == 0:
      g.com.notice(nick, 'You cannot remove all sets.')
      return

    g.deck.remove_set(sets[c])
    self.list_used_sets(g, nick, args)

  @Command()
  def rando(self, g: Game, nick, args):
    if not args:
      g.com.announce('{} is `{}`.'.format(g.RANDO_NICK, 'on' if g.rando else 'off'))
    elif nick != g.creator:
      g.com.notice(nick, 'Only `{}` can control `{}`.'.format(g.creator, g.RANDO_NICK))
    elif args == 'on':
      g.rando = True
      g.com.announce('{} is `on`.'.format(g.RANDO_NICK))
    elif args == 'off':
      g.rando = False
      g.com.announce('{} is `off`.'.format(g.RANDO_NICK))
    else:
      g.com.reply(nick, 'Possible arguments: `on`, `off`.')

  @Command()
  def blank(self, g: Game, nick, args):
    if not args:
      g.com.announce('There are `{}` blank cards in the deck.'.format(g.blanks))
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only `{}` can change the number of blanks in the deck.'.format(g.creator))

    parts = args.split()
    if not parts[0].isnumeric():
      g.com.reply('Specify a number.')
      return

    c = int(parts[0])
    if c < 0 or c > 100:
      g.com.reply('Invalid argument.')
      return

    g.blanks = c
    g.com.announce('There are `{}` blank cards in the deck.'.format(g.blanks))


class PlayingCards(GamePhase):
  def __init__(self):
    self.copy_command(WaitingForPlayers.list_sets)
    self.copy_command(WaitingForPlayers.list_used_sets)

  def deal(self, g: Game):
    if self.is_over(g):
      g.com.announce('The game is over before it even started!')
      g.reset()
      return NoGame()

    g.deck.add_blank(g.blanks)

    for i in g.list_players():
      g.scores.register(i)

    random.shuffle(g.players)
    for player in g.list_players():
      g.hands[player] = g.deck.draw_white(10)
      g.scores.register(player)

    g.czar_index = 0

    self.next_czar(g)

    if self.is_over(g):
      g.com.announce('The game is over before it even started!')
      g.reset()
      return NoGame()

  def is_over(self, g: Game):
    return \
      g.scores.highest() >= g.limit or \
      len(g.deck.black_pool) == 0 or \
      len(g.deck.white_pool) == 0

  def act(self, g: Game):
    if self.is_over(g):
      g.com.announce('The game is over! `{}` won!'.format(', '.join(g.scores.winners())))
      g.reset()
      return NoGame()

    for i in g.joiners:
      g.com.announce('`{}` is joining the game!'.format(i))
      g.players.append(i)
      g.hands[i] = g.deck.draw_white(10)
      g.scores.register(i)

    g.joiners.clear()

    g.black_card = g.deck.draw_black()
    g.com.announce('Round `{}`. The card czar is `{}`. This round\'s card is...'
                   ''.format(g.round, g.czar))
    g.com.announce('    {}'.format(g.black_card))

    example_args = ' '.join(map(str, range(g.black_card.gaps)))
    example = 'pick {}'.format(example_args)
    waiting = list(g.players)
    waiting.remove(g.czar)
    msg = '{}: Play `{}` card{}, like "`{}`" or just "`{}`".' \
          ''.format(', '.join(waiting),
                    g.black_card.gaps,
                    '' if g.black_card.gaps == 1 else 's',
                    example,
                    example_args)
    g.com.announce(msg)

    for player in g.players:
      if player == g.czar:
        continue

      hand = g.hands[player]

      hand_s = ' '.join(['[`{}`] {}'.format(i, j) for i, j in enumerate(hand)])
      g.com.notice(player, 'Your hand: {}'.format(hand_s))

    g.played = {}

    if g.rando:
      hand = g.hands[g.RANDO_NICK]
      blanks_in_hand = 0
      for i in list(hand):
        if i.is_blank:
          blanks_in_hand += 1
          g.deck.return_whites([i])
          hand.remove(i)
          hand.extend(g.deck.draw_white(1))

      if blanks_in_hand == 7:
        g.com.announce('Too many blanks for Rando. Aborting.')
        g.reset()
        return NoGame()

      g.played[g.RANDO_NICK] = list(hand[:g.black_card.gaps])

    if self.is_over(g):
      g.com.announce('The game is over! `{}` won!'.format(', '.join(g.scores.winners())))
      g.reset()
      return NoGame()


  @Command(names=['scores', 'sc'])
  def scores(self, g: Game, nick, args):
    g.com.announce(str(g.scores))

  @Command(names=['join', 'j'])
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
      return

    if nick in g.joiners:
      g.com.notice(nick, 'You are already joining.')
      return

    g.joiners.append(nick)
    g.com.notice(nick, 'You will be dealt into the game when the next round begins.')

  @Command(names=['leave', 'l'], player_only=True)
  def leave(self, g: Game, nick, args):
    if nick in g.joiners:
      g.com.notice(nick, 'You will not join.')
      g.joiners.remove(nick)
      return

    g.com.notice(nick, 'You left the game.')
    g.com.announce('`{}` has left the game!'.format(nick))

    g.players.remove(nick)
    if nick in g.played:
      del g.played[nick]
    g.deck.return_whites(g.hands[nick])
    del g.hands[nick]

    if g.count_players() < 3:
      g.com.announce('There are not enough players to continue. Game stopped.')
      g.reset()
      return NoGame()

    if nick == g.czar:
      g.com.announce('The card czar left. Restarting the round...')
      g.deck.return_black(g.black_card)

      self.next_czar(g)

      new_state = PlayingCards()
      return new_state.act(g) or new_state

    g.czar_index = g.players.index(g.czar)

  @Command(names=['pick', 'p'], player_only=True)
  def pick(self, g: Game, nick, args):
    if nick == g.czar:
      g.com.notice(nick, 'You are the card czar. '
                         'You choose the winner after everyone else has played.')
      return

    parts = args.split()
    choice = []
    if len(parts) != g.black_card.gaps:
      g.com.notice(nick, 'Wrong number of cards. `{}` needed.'.format(g.black_card.gaps))
      return
    for i in parts[:g.black_card.gaps]:
      if not i.isnumeric():
        g.com.notice(nick, 'Pick a digit.'.format(g.black_card.gaps))
        return
      c = int(i)
      if c < 0 or c >= len(g.hands[nick]):
        g.com.notice(nick, 'You don\'t have that card.'.format(g.black_card.gaps))
        return
      card = g.hands[nick][c]
      if card in choice:
        g.com.notice(nick, 'You can\'t play the same card twice')
        return

      if card.is_blank:
        g.com.notice(nick, 'You cannot play a blank card, you have to write something on it first.')
        return

      choice.append(card)

    g.com.notice(nick, 'You chose to play "{}"'.format(g.black_card.insert(choice)))

    g.played[nick] = choice

    if len(g.played) < g.count_players() - 1:
      return

    for player, cards in g.played.items():
      for card in cards:
        g.hands[player].remove(card)

    new_state = ChoosingWinner()

    return new_state.act(g) or new_state

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    waiting = []
    for i in g.players:
      if i not in g.played and i != g.czar:
        waiting.append(i)

    g.com.announce('`{}` players. `{}` is the card czar. Black card: "{}". '
                   'Waiting for `{}` to play.'
                   ''.format(g.count_players(), g.czar, g.black_card, ', '.join(waiting)))

  @Command(names=['cards', 'c'], player_only=True)
  def cards(self, g: Game, nick, args):
    hand = g.hands[nick]
    hand_s = ' '.join(['[`{}`] {}'.format(i, j) for i, j in enumerate(hand)])
    g.com.notice(nick, 'Your hand: {}.'.format(hand_s))

  @Command(names=['limit', 'l'])
  def limit(self, g: Game, nick, args):
    g.com.reply(nick, 'The point limit is `{}` points.'.format(g.limit))


  @Command(player_only=True)
  def write(self, g: Game, nick, args: str):
    parts = args.split(maxsplit=1)

    if not args or len(parts) < 2 or not parts[0].isnumeric():
      g.com.notice(nick, 'Usage: write <card\'s id> <text>')
      return

    id = int(parts[0])

    if id < 0 or id >= len(g.hands[nick]):
      g.com.notice(nick, 'Wrong card id.')
      return

    card = g.hands[nick][id]

    if not card.is_blank:
      g.com.notice(nick, 'Card is not blank.')
      return

    card.text = parts[1]
    card.is_blank = False

    self.cards(g, nick, '')


class ChoosingWinner(GamePhase):
  def __init__(self):
    self.copy_command(PlayingCards.join)
    self.copy_command(PlayingCards.leave)
    self.copy_command(PlayingCards.cards)
    self.copy_command(PlayingCards.scores)

    self.copy_command(WaitingForPlayers.list_sets)
    self.copy_command(WaitingForPlayers.list_used_sets)

  def act(self, g: Game):
    g.com.announce('Everyone has played. Now `{}` has to choose a winner. '
                   'Candidates are:'.format(g.czar))

    g.player_perm = g.list_players()
    g.player_perm.remove(g.czar)
    random.shuffle(g.player_perm)

    for i, player in enumerate(g.player_perm):
      s = g.black_card.insert(g.played[player])
      g.com.announce('[`{}`] {}'.format(i, s))

  @Command(names=['pick', 'p'])
  def pick(self, g: Game, nick, args):
    if nick != g.czar:
      return

    parts = args.split()
    if len(parts) < 1 or not parts[0].isnumeric():
      g.com.notice(nick, 'Choose a card.')
      return

    c = int(parts[0])
    if c < 0 or c >= len(g.played):
      g.com.notice(nick, 'Invalid number.')
      return

    winner = g.player_perm[c]
    g.com.announce('`{}` wins with "{}".'
                   .format(winner, g.black_card.insert(g.played[winner])))
    g.scores.point(winner)

    g.com.announce(str(g.scores))

    self.next_czar(g)

    g.round += 1

    for player, cards in g.played.items():
      g.hands[player] += g.deck.draw_white(len(cards))

    new_state = PlayingCards()

    return new_state.act(g) or new_state

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    g.com.announce(
      '`{}` players. Black card: "{}". Waiting for card czar `{}` to choose the winner.'
      ''.format(g.count_players(), g.black_card, g.czar))
