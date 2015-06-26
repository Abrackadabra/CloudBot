import random
from .deck import Deck, BlackCard
from .score import Scores


class Game(object):
  def __init__(self, com, card_dir):
    """
    :type com: Communicator
    """
    self.com = com

    self.deck = Deck.read(card_dir + '/official_deck.json')

    self.phase = NoGame()

    self.players = []
    self.creator = ''
    self.hands = {}

    self.scores = None
    """:type : score.Scores"""

    self.round = -1

    self.black_card = None
    """:type : deck.BlackCard"""

    self.czar_index = -1
    self.czar = ''
    self.played = {}
    self.player_perm = []

    self.joiners = []

  def process(self, nick, command, args):
    self.phase = self.phase.process(self, nick, command, args) or self.phase


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
    g.com.announce('Game is started!')

    g.creator = nick
    g.players.append(nick)

    return WaitingForPlayers()


class WaitingForPlayers(GamePhase):
  @GamePhase.command
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
    else:
      g.players.append(nick)
      g.com.announce(
        '{} has joined the game. {} players total.'.format(nick, len(g.players)))

  @GamePhase.command
  def leave(self, g: Game, nick, args):
    if nick not in g.players:
      g.com.notice(nick, 'You are not playing.')
    else:
      g.players.remove(nick)
      g.com.announce('{} has left the game. {} players remaining.'.format(nick, len(g.players)))

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


class PlayingCards(GamePhase):
  def deal(self, g: Game):
    g.scores = Scores()
    for i in g.players:
      g.scores.register(i)

    g.round = 0

    random.shuffle(g.players)
    for player in g.players:
      g.hands[player] = g.deck.draw_white(10)
      g.scores.register(player)

    g.czar_index = random.randrange(len(g.players))
    g.czar = g.players[g.czar_index]

  def act(self, g: Game):
    if g.round == 10:
      g.com.announce('The game is over!')
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
    g.com.announce(
      'Round {}. The card czar is {}. This round\'s card is...'.format(g.round, g.czar))
    g.com.announce(str(g.black_card))

    for player, hand in g.hands.items():
      if player == g.czar:
        continue

      example = '.pick {}'.format(' '.join(map(str, range(g.black_card.gaps))))
      msg = 'You need to play {} card{}, like "{}".'.format(g.black_card.gaps,
                                                            '' if g.black_card.gaps == 1 else 's',
                                                            example)
      g.com.notice(player, msg)

      hand_s = ' '.join(['[{}] {}'.format(i, j) for i, j in enumerate(hand)])
      g.com.notice(player, 'Your hand: {}.'.format(hand_s))

    g.played = {}

  @GamePhase.command
  def join(self, g: Game, nick, args):
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')

    if nick in g.joiners:
      g.com.notice(nick, 'You are already joining.')

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
    g.deck.return_whites(g.hands[nick])
    del g.hands[nick]

    if len(g.players) < 3:
      g.com.announce('There are not enough players to continue. Game stopped.')
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
    if len(parts) < g.black_card.gaps:
      g.com.notice(nick, 'Not enough cards. {} needed.'.format(g.black_card.gaps))
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
