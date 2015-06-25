import random

from .com import Communicator
from .deck import Deck


def command(func):
  func.command = True
  return func


def is_command(func):
  return getattr(func, 'command', False)


class GameState(object):
  def __init__(self, com, deck):
    """
    :type com: Communicator
    :type deck: Deck
    """
    self.com = com
    self.deck = deck

  def default_reply(self, nick):
    self.com.notice(nick, 'Unknown command.')

  def process(self, nick, command, args):
    method = getattr(self, command, None)
    if method and callable(method) and is_command(method):
      return method(nick, args)


class NoGame(GameState):
  @command
  def create(self, nick, args):
    self.com.announce('Game is started!')
    return WaitingForPlayers(self.com, self.deck, nick)


class WaitingForPlayers(GameState):
  def __init__(self, com, deck, creator):
    super().__init__(com, deck)
    self.creator = creator
    self.players = [creator]

  @command
  def join(self, nick, args):
    if nick in self.players:
      self.com.notice(nick, 'You are already playing.')
    else:
      self.players.append(nick)
      self.com.announce('{} has joined the game. {} players total.'.format(nick, len(self.players)))

  @command
  def leave(self, nick, args):
    if nick not in self.players:
      self.com.notice(nick, 'You are not playing.')
    else:
      self.players.remove(nick)
      self.com.announce('{} has left the game. {} players remaining.'
                        .format(nick, len(self.players)))

  @command
  def start(self, nick, args):
    if nick != self.creator:
      self.com.notice(nick, 'Only {} can start the game.'.format(self.creator))
    elif len(self.players) < 3:
      self.com.reply(nick, 'Need at least 3 players to start a game.')
    else:
      new_state = PlayingCards(self.com, self.deck, self.players)
      new_state.deal()
      return new_state.play() or new_state


def format_black(card, cards):
  s = str(card)
  if '%s' in card:
    for i in cards:
      s = s.replace('%s', i, 1)
    return s

  return s + ' ' + ' '.join(cards)


class PlayingCards(GameState):
  def __init__(self, com, deck, players, scores=None, hands=None, round=0, czar_index=0):
    super().__init__(com, deck)

    if not hands:
      hands = {}

    if not scores:
      scores = {}
      for i in players:
        scores[i] = 0

    self.czar_index = czar_index
    self.players = players
    self.scores = scores
    self.hands = hands
    self.round = round

    self.czar = self.players[czar_index]

  def deal(self):
    random.shuffle(self.players)
    for player in self.players:
      self.hands[player] = self.deck.draw_white(10)

    self.czar_index = random.randrange(len(self.players))
    self.czar = self.players[self.czar_index]

  def play(self):
    if self.round == 10:
      self.com.announce('The game is over!')
      return NoGame(self.com, self.deck)

    self.black_card, self.gaps = self.deck.draw_black()
    self.com.announce(
      'Round {}. The card czar is {}. This round\'s card is...'
        .format(self.round, self.czar, self.round))
    self.com.announce(self.black_card.replace('%s', '___'))

    for player, hand in self.hands.items():
      if player == self.czar:
        continue

      example = '.pick {}'.format(' '.join(map(str, range(self.gaps))))
      msg = 'You need to play {} {}, like "{}".'.format(self.gaps,
                                                        'card' if self.gaps == 1 else 'cards',
                                                        example)
      self.com.notice(player, msg)

      hand_s = ' '.join(['[{}] {}'.format(i, j) for i, j in enumerate(hand)])
      self.com.notice(player, 'Your hand: {}.'.format(hand_s))

    self.played = {}

  def print_score(self):
    s = []
    for i, j in sorted(self.scores.items(), key=lambda x: -x[1]):
      s.append('{}-{}p'.format(i, j))
    self.com.announce('Scores: {}.'.format(', '.join(s)))

  @command
  def pick(self, nick, args):
    if nick == self.czar:
      self.com.notice(nick, 'You are the card czar. '
                            'You choose the winner after everyone else has played.')
      return

    parts = args.split()
    choice = []
    if len(parts) < self.gaps:
      self.com.notice(nick, 'Not enough cards. {} needed.'.format(self.gaps))
      return
    for i in parts[:self.gaps]:
      if not i.isnumeric():
        self.com.notice(nick, 'Pick a digit.'.format(self.gaps))
        return
      c = int(i)
      if c < 0 or c >= len(self.hands[nick]):
        self.com.notice(nick, 'You don\'t have that card.'.format(self.gaps))
        return
      card = self.hands[nick][c]
      if card in choice:
        self.com.notice(nick, 'You can\'t play the same card twice')
        return

      choice.append(card)

    self.com.notice(nick, 'You chose to play "{}"'.format(format_black(self.black_card, choice)))

    self.played[nick] = choice

    if len(self.played) < len(self.players) - 1:
      return

    for player, cards in self.played.items():
      for card in cards:
        self.hands[player].remove(card)

    new_state = ChoosingWinner(self.com, self.deck, self.players, self.scores, self.hands,
                               self.played,
                               self.black_card, self.gaps, self.round, self.czar_index)

    return new_state.play() or new_state


class ChoosingWinner(GameState):
  def __init__(self, com, deck, players, scores, hands, played, black_card, gaps, round,
      czar_index):
    super().__init__(com, deck)

    self.players = players
    self.hands = hands
    self.played = played
    self.scores = scores
    self.black_card = black_card
    self.gaps = gaps
    self.round = round
    self.czar_index = czar_index

    self.czar = self.players[czar_index]

  def play(self):
    self.com.announce('Everyone has played. Now {} has to choose a winner. '
                      'Candidates are:'.format(self.czar))

    self.player_perm = list(self.players)
    self.player_perm.remove(self.czar)
    random.shuffle(self.player_perm)

    for i, player in enumerate(self.player_perm):
      s = format_black(self.black_card, self.played[player])
      self.com.announce('[{}] {}'.format(i, s))

  @command
  def pick(self, nick, args):
    if nick != self.czar:
      self.com.notice(nick, 'You are not the card czar.')
      return

    parts = args.split()
    if len(parts) < 1 or not parts[0].isnumeric():
      self.com.notice(nick, 'Choose a card.')
      return

    c = int(parts[0])
    if c < 0 or c >= len(self.played):
      self.com.notice(nick, 'Invalid number.')
      return

    winner = self.player_perm[c]
    self.com.announce('{} wins with "{}".'
                      .format(winner, format_black(self.black_card, self.played[winner])))
    self.scores[winner] += 1

    self.print_score()

    self.czar_index = (self.czar_index + 1) % len(self.players)
    self.round += 1

    for player, cards in self.played.items():
      self.hands[player] += self.deck.draw_white(len(cards))

    new_state = PlayingCards(self.com, self.deck, self.players, self.scores, self.hands,
                             self.round, self.czar_index)

    return new_state.play() or new_state

  def print_score(self):
    s = []
    for i, j in sorted(self.scores.items(), key=lambda x: -x[1]):
      s.append('{}-{}p'.format(i, j))
    self.com.announce('Scores: {}.'.format(', '.join(s)))
