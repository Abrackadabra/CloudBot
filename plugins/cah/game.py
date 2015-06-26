import random

from .deck import Deck
from .score import Scores


class Game(object):
  def __init__(self, com, card_dir):
    """
    :type com: Communicator
    """
    self.com = com

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


class GamePhase(object):
  @staticmethod
  def command(func):
    func.command = True
    return func

  @staticmethod
  def is_command(func):
    return getattr(func, 'command', False)

  def process(self, g, nick, command, args):
    method = getattr(self, command, None)
    if method and callable(method) and GamePhase.is_command(method):
      return method(g, nick, args)


class NoGame(GamePhase):
  @GamePhase.command
  def create(self, g: Game, nick, args):
    g.com.announce('Game is created.')

    g.reset()

    g.creator = nick
    g.players = [nick]

    return WaitingForPlayers()

  @GamePhase.command
  def status(self, g: Game, nick, args):
    g.com.announce('No one is playing.')


class WaitingForPlayers(GamePhase):
  @GamePhase.command
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
    else:
      g.players.append(nick)
      g.com.announce('{} has joined the game. {} players total.'.format(nick, len(g.players)))

  @GamePhase.command
  def leave(self, g: Game, nick, args):
    if nick not in g.players:
      g.com.notice(nick, 'You are not playing.')
    else:
      g.players.remove(nick)
      g.com.announce('{} has left the game. {} players remaining.'.format(nick, len(g.players)))

      if nick == g.creator:
        g.com.announce('Creator has left the game. Game aborted.')
        g.reset()
        return NoGame()

  @GamePhase.command
  def start(self, g: Game, nick, args):
    if nick != g.creator:
      g.com.notice(nick, 'Only {} can start the game.'.format(g.creator))
    elif len(g.players) < 3:
      g.com.reply(nick, 'Need at least 3 players to start a game.')
    else:
      new_state = PlayingCards()
      new_state.deal(g)
      return new_state.act(g) or new_state

  @GamePhase.command
  def limit(self, g: Game, nick, args):
    parts = args.split()
    if len(parts) == 0:
      g.com.reply(nick, 'Current point limit is {} points.'.format(g.limit))
      return

    if not parts[0].isnumeric():
      g.com.notice(nick, 'Invalid argument.')
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only {} can change the point limit.'.format(g.creator))
      return

    c = int(parts[0])
    if 0 < c < 100:
      g.limit = c
      g.com.notice(nick, 'You changed the point limit to {}.'.format(c))
    else:
      g.com.notice(nick, 'Invalid number.')

  @GamePhase.command
  def status(self, g: Game, nick, args):
    g.com.announce('Waiting for people to join. Creator: {}. {} players: {}.'
                   ''.format(g.creator, len(g.players), ', '.join(g.players)))

  @GamePhase.command
  def list_sets(self, g: Game, nick, args):
    sets = g.deck.list_all_sets()
    g.com.announce('All card sets: ' + ', '.join(['[{}] {}'.format(i, j) for i, j in enumerate(sets)]))

  @GamePhase.command
  def list_used_sets(self, g: Game, nick, args):
    sets = g.deck.list_used_sets()
    g.com.announce('Used card sets: ' + ', '.join(['[{}] {}'.format(i, j) for i, j in enumerate(sets)]))

  @GamePhase.command
  def add_set(self, g: Game, nick, args):
    parts = args.split()

    if len(parts) == 0 or (any(not i.isnumeric() for i in parts) and parts[0] != 'all'):
      g.com.notice(nick, 'Invalid argument.')
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only {} can change used card sets.'.format(g.creator))
      return

    sets = g.deck.list_all_sets()

    if parts[0] == 'all':
      c = list(range(len(sets)))
    else:
      c = [int(i) for i in parts]
    for i in c:
      if i < 0 or i >= len(sets):
        g.com.notice(nick, 'Invalid index {}.'.format(i))
        return

      g.deck.add_set(sets[i])
    self.list_used_sets(g, nick, args)

  @GamePhase.command
  def remove_set(self, g: Game, nick, args):
    parts = args.split()
    if len(parts) == 0 or not parts[0].isnumeric():
      g.com.notice(nick, 'Invalid argument.')
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only {} can change used card sets.'.format(g.creator))
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


class PlayingCards(GamePhase):
  def deal(self, g: Game):
    for i in g.players:
      g.scores.register(i)

    random.shuffle(g.players)
    for player in g.players:
      g.hands[player] = g.deck.draw_white(10)
      g.scores.register(player)

    g.czar_index = random.randrange(len(g.players))
    g.czar = g.players[g.czar_index]

  def act(self, g: Game):
    if g.scores.highest() >= g.limit:
      g.com.announce('The game is over! {} won!'.format(', '.join(g.scores.winners())))
      g.reset()
      return NoGame()

    for i in g.joiners:
      g.com.announce('{} is joining the game!'.format(i))
      g.players.append(i)
      g.hands[i] = g.deck.draw_white(10)
      g.scores.register(i)

      random.shuffle(g.players)
      g.czar_index = random.randrange(len(g.players))
      g.czar = g.players[g.czar_index]
    g.joiners.clear()

    g.black_card = g.deck.draw_black()
    g.com.announce('Round {}. The card czar is {}. This round\'s card is...'
                   ''.format(g.round, g.czar))
    g.com.announce('{}'.format(g.black_card))

    example_args = ' '.join(map(str, range(g.black_card.gaps)))
    example = 'pick {}'.format(example_args)
    waiting = list(g.players)
    waiting.remove(g.czar)
    msg = '{}: Play {} card{}, like "{}" or just "{}".' \
          ''.format(', '.join(waiting),
                    g.black_card.gaps,
                    '' if g.black_card.gaps == 1 else 's',
                    example,
                    example_args)
    g.com.announce(msg)

    for player, hand in g.hands.items():
      if player == g.czar:
        continue

      hand_s = ' '.join(['[{}] {}'.format(i, j) for i, j in enumerate(hand)])
      g.com.notice(player, 'Your hand: {}'.format(hand_s))

    g.played = {}

  @GamePhase.command
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
      return

    if nick in g.joiners:
      g.com.notice(nick, 'You are already joining.')
      return

    g.joiners.append(nick)
    g.com.notice(nick, 'You will be dealt into the game when the next round begins.')

  @GamePhase.command
  def leave(self, g: Game, nick, args):
    if nick in g.joiners:
      g.com.notice(nick, 'You will not join.')
      g.joiners.remove(nick)
      return

    if nick not in g.players:
      g.com.notice(nick, 'You are not playing.')
      return

    g.com.notice(nick, 'You left the game.')
    g.com.announce('{} has left the game!'.format(nick))

    g.players.remove(nick)
    if nick in g.played:
      del g.played[nick]
    g.deck.return_whites(g.hands[nick])
    del g.hands[nick]

    if len(g.players) < 3:
      g.com.announce('There are not enough players to continue. Game stopped.')
      g.reset()
      return NoGame()

    if nick == g.czar:
      g.com.announce('The card czar left. Restarting the round...')
      g.deck.return_black(g.black_card)

      g.czar_index %= len(g.players)
      g.czar = g.players[g.czar_index]

      new_state = PlayingCards()
      return new_state.act(g) or new_state

    g.czar_index = g.players.index(g.czar)


  @GamePhase.command
  def pick(self, g: Game, nick, args):
    if nick == g.czar:
      g.com.notice(nick, 'You are the card czar. '
                         'You choose the winner after everyone else has played.')
      return

    parts = args.split()
    choice = []
    if len(parts) != g.black_card.gaps:
      g.com.notice(nick, 'Wrong number of cards. {} needed.'.format(g.black_card.gaps))
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

      choice.append(card)

    g.com.notice(nick, 'You chose to play "{}"'.format(g.black_card.insert(choice)))

    g.played[nick] = choice

    if len(g.played) < len(g.players) - 1:
      return

    for player, cards in g.played.items():
      for card in cards:
        g.hands[player].remove(card)

    new_state = ChoosingWinner()

    return new_state.act(g) or new_state

  @GamePhase.command
  def status(self, g: Game, nick, args):
    waiting = []
    for i in g.players:
      if i not in g.played and i != g.czar:
        waiting.append(i)

    g.com.announce('{} players. {} is the card czar. Black card: "{}". Waiting for {} to play.'
                   ''.format(len(g.players), g.czar, g.black_card, ', '.join(waiting)))

  @GamePhase.command
  def cards(self, g: Game, nick, args):
    if nick not in g.players:
      g.com.notice(nick, 'You are not playing.')
      return

    hand = g.hands[nick]
    hand_s = ' '.join(['[{}] {}'.format(i, j) for i, j in enumerate(hand)])
    g.com.notice(nick, 'Your hand: {}.'.format(hand_s))

  @GamePhase.command
  def limit(self, g: Game, nick, args):
    g.com.reply(nick, 'The point limit is {} points.'.format(g.limit))


class ChoosingWinner(GamePhase):
  def act(self, g: Game):
    g.com.announce('Everyone has played. Now {} has to choose a winner. '
                   'Candidates are:'.format(g.czar))

    g.player_perm = list(g.players)
    g.player_perm.remove(g.czar)
    random.shuffle(g.player_perm)

    for i, player in enumerate(g.player_perm):
      s = g.black_card.insert(g.played[player])
      g.com.announce('[{}] {}'.format(i, s))

  @GamePhase.command
  def pick(self, g: Game, nick, args):
    if nick != g.czar:
      g.com.notice(nick, 'You are not the card czar.')
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
    g.com.announce('{} wins with "{}".'
                   .format(winner, g.black_card.insert(g.played[winner])))
    g.scores.point(winner)

    g.com.announce(str(g.scores))

    g.czar_index = (g.czar_index + 1) % len(g.players)
    g.czar = g.players[g.czar_index]

    g.round += 1

    for player, cards in g.played.items():
      g.hands[player] += g.deck.draw_white(len(cards))

    new_state = PlayingCards()

    return new_state.act(g) or new_state

  join = PlayingCards.join
  leave = PlayingCards.leave
  cards = PlayingCards.cards

  @GamePhase.command
  def status(self, g: Game, nick, args):
    g.com.announce(
      '{} players. Black card: "{}". Waiting for card czar {} to choose the winner.'
      ''.format(len(g.players), g.black_card, g.czar))
