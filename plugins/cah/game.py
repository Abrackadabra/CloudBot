from datetime import datetime, timedelta
import random
import re
import asyncio

from .cards import Deck
from .score import Scores


class Game(object):
  RANDO_NICK = 'Rando Cardrissian'
  HAND_SIZE = 10
  DEFAULT_POINT_LIMIT = 10
  MAX_POINT_LIMIT = 100
  DEFAULT_BLANK_COUNT = 50
  DEFAULT_RANDO_STATE = True

  WAITING_FOR_PLAYERS_TIMEOUT_SOON = timedelta(minutes=4)
  WAITING_FOR_PLAYERS_TIMEOUT = timedelta(minutes=5)

  MIN_PLAYERS = 3

  PLAYING_CARDS_TIMEOUT_SOON = timedelta(minutes=1)
  PLAYING_CARDS_TIMEOUT = timedelta(minutes=2)

  CHOOSING_WINNER_TIMEOUT_SOON = timedelta(minutes=1)
  CHOOSING_WINNER_TIMEOUT = timedelta(minutes=2)

  @staticmethod
  def inject_zwsp(nick):
    return nick[:1] + '\u200b' + nick[1:]

  def __init__(self, com, card_dir, chan, loop: asyncio.AbstractEventLoop):
    """
    :type com: Communicator
    """
    self.com = com
    self.chan = chan
    self.loop = loop

    self.card_dir = card_dir
    self.deck = Deck(card_dir)

    self.phase = NoGame()
    """:type : GamePhase"""

    self.reset()

  def process(self, nick, command, args, is_pm=False):
    self.phase.process(self, nick, command.lower(), args, is_pm)

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
    self.limit = self.DEFAULT_POINT_LIMIT

    self.deck.reset()

    self.rando = self.DEFAULT_RANDO_STATE

    self.blanks = self.DEFAULT_BLANK_COUNT

    self.phase = NoGame()

    self.cancel_timeouts()

    self.timeout_handles = []

    self.timeout_time = datetime.now()

  def list_players(self):
    r = list(self.players)
    if self.rando:
      r.append(self.RANDO_NICK)
    return r

  def count_players(self):
    return len(self.list_players())

  def cancel_timeouts(self):
    if hasattr(self, 'timeout_handles'):
      for i in self.timeout_handles:
        i.cancel()


class Command(object):
  """
  Decorator for command-handling methods in GamePhases.
  """

  def __init__(self, names=None, player_only=False, iff_pm=False):
    self.names = names
    self.player_only = player_only
    self.iff_pm = iff_pm

  @staticmethod
  def strip_doc(f):
    if not f.__doc__:
      return 'No help available'
    return re.sub(r'\s+', ' ', f.__doc__.strip())

  @staticmethod
  def copy_fields(a, b):
    b.names = a.names
    b.player_only = a.player_only
    b.help = a.help
    b.iff_pm = a.iff_pm

  def __call__(self, f):
    if not self.names:
      self.names = [f.__name__]

    f.names = self.names
    f.command = True
    f.player_only = self.player_only
    f.help = self.strip_doc(f)
    f.iff_pm = self.iff_pm

    return f

  @staticmethod
  def is_command(f):
    return callable(f) and getattr(f, 'command', False)


class GamePhase(object):
  def copy_command(self, method):
    name = method.__name__
    copy = lambda *args, **kwargs: method(self, *args, **kwargs)
    copy = Command()(copy)
    Command.copy_fields(method, copy)
    setattr(self, name, copy)

  def process(self, g: Game, nick, command, args, is_pm):
    for i in dir(self):
      method = getattr(self, i)
      if Command.is_command(method) and command in method.names:
        if method.player_only and nick not in g.players:
          continue

        if method.iff_pm != is_pm:
          continue

        method(g, nick, args)

  def next_czar(self, g: Game):
    g.czar_index = (g.czar_index + 1) % len(g.players)
    g.czar = g.players[g.czar_index]

  @Command(names=['h', 'help', '?', 'wtf', 'command', 'commands'])
  def help(self, g: Game, nick, args):
    """
    help [<command>] -- lists commands available in the current phase or returns help about
    a specific command
    """
    args = args.strip()
    if args:
      c = args.split()[0]

      for i in dir(self):
        method = getattr(self, i)
        if Command.is_command(method) and c in method.names:
          g.com.notice(nick, method.help)
      return

    command_names = []
    for i in dir(self):
      method = getattr(self, i)
      if Command.is_command(method):
        command_names.append('/'.join(method.names))
    g.com.notice(nick, 'Commands in this phase: {}. Type "? <command>" to learn more.'
                       ''.format(', '.join(command_names)))

  @Command(names=['time', 't'])
  def time(self, g: Game, nick, args):
    """
    time -- shows time left until timeout
    """
    if g.timeout_handles:
      g.com.announce('Timeout will happen in {}.'.format(g.timeout_time - datetime.now()))
      return
    g.com.announce('There is no timeout now.')


class NoGame(GamePhase):
  def __init__(self):
    self.copy_command(WaitingForPlayers.list_sets)

  @Command(names=['create', 'c', 'join', 'j', 'play', 'p'])
  def create(self, g: Game, nick, args):
    """
    create -- creates a game. Creator of the game can then set various settings and start the game
    """
    g.com.announce('∆{}∆ has created a game! Type ∆j∆ to join.'.format(nick))

    g.reset()

    g.creator = nick
    g.players = [nick]

    g.phase = new_phase = WaitingForPlayers()
    new_phase.prepare(g)

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    """
    status -- shows information about the current game
    """
    g.com.announce('No one is playing.')


class WaitingForPlayers(GamePhase):
  def prepare(self, g: Game):
    def timeout_soon(g: Game):
      if len(g.players) == 1:
        g.com.announce('The game will timeout soon if nobody joins!')

    g.timeout_handles.append(
      g.loop.call_later(g.WAITING_FOR_PLAYERS_TIMEOUT_SOON.total_seconds(), timeout_soon, g))

    def timeout(g: Game):
      if len(g.players) == 1:
        g.com.announce('Time out! Game stopped.')
        g.reset()

    g.timeout_handles.append(
      g.loop.call_later(g.WAITING_FOR_PLAYERS_TIMEOUT.total_seconds(), timeout, g))

    g.timeout_time = datetime.now() + g.WAITING_FOR_PLAYERS_TIMEOUT

  @Command(names=['join', 'j'])
  def join(self, g: Game, nick, args):
    """
    join -- joins the active game
    """
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
    else:
      g.players.append(nick)
      g.com.announce('∆{}∆ has joined the game. ∆{}∆ players total.'
                     ''.format(nick, g.count_players()))

  @Command(names=['leave'], player_only=True)
  def leave(self, g: Game, nick, args):
    """
    leave -- leaves the active game
    """
    g.players.remove(nick)
    g.com.announce(
      '∆{}∆ has left the game. ∆{}∆ players remaining.'.format(nick, g.count_players()))

    if nick == g.creator:
      g.com.announce('Creator has left the game. Game aborted.')
      g.reset()

  @Command(names=['start', 'st'], player_only=True)
  def start(self, g: Game, nick, args):
    """
    start -- starts the game. Only the game creator can use it. Once started, game's parameters
    cannot be changed
    """
    if nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can start the game.'.format(g.creator))
    elif g.count_players() < g.MIN_PLAYERS:
      g.com.reply(nick, 'Need at least ∆{}∆ players to start a game.'.format(g.MIN_PLAYERS))
    else:
      g.cancel_timeouts()

      g.phase = new_phase = PlayingCards()
      new_phase.prepare(g)
      new_phase.deal(g)

  @Command(names=['limit', 'l'])
  def limit(self, g: Game, nick, args):
    """
    limit [<number>] -- shows current point limit or sets it
    """
    parts = args.split()
    if len(parts) == 0:
      g.com.reply(nick, 'Current point limit is ∆{}∆ points.'.format(g.limit))
      return

    if not parts[0].isnumeric():
      g.com.notice(nick, 'Invalid argument.')
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can change the point limit.'.format(g.creator))
      return

    c = int(parts[0])
    if 0 < c <= g.MAX_POINT_LIMIT:
      g.limit = c
      g.com.announce('∆{}∆ changed the point limit to ∆{}∆.'.format(nick, c))
    else:
      g.com.notice(nick, 'Invalid number.')

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    """
    status -- shows information about the current game
    """
    g.com.announce('Waiting for people to join. Creator: ∆{}∆. ∆{}∆ players: {}.'
                   ''.format(g.creator, g.count_players(), ', '.join(g.list_players())))

  @Command(names=['list_sets', 'listsets', 'listall', 'list_all', 'la'])
  def list_sets(self, g: Game, nick, args):
    """
    list_sets -- lists all available card sets. Admins can add more with .load_set
    """
    sets = g.deck.list_all_sets()
    g.com.announce(
      'All card sets: ' + ', '.join(['[∆{}∆] {}'.format(i, j) for i, j in enumerate(sets)]))

  @Command(names=['list_used', 'listused', 'lu'])
  def list_used_sets(self, g: Game, nick, args):
    """
    list_used_sets -- lists all active card sets in the deck
    """
    sets = g.deck.list_used_sets()
    g.com.announce(
      'Used card sets: ' + ', '.join(['[∆{}∆] {}'.format(i, j) for i, j in enumerate(sets)]))

  @Command(names=['add_set', 'addset', 'add', 'a'])
  def add_set(self, g: Game, nick, args):
    """
    add_set -- adds a card set to the deck
    """
    if nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can change used card sets.'.format(g.creator))
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
        g.com.notice(nick, 'Invalid index ∆{}∆.'.format(i))
        return

      g.deck.add_set(sets[i])
    self.list_used_sets(g, nick, args)

  @Command(names=['remove_set', 'removeset', 'remove', 'r'])
  def remove_set(self, g: Game, nick, args):
    """
    remove_set -- removes a card set from the deck
    """
    if nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can change used card sets.'.format(g.creator))
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
    """
    rando [on|off] -- allows to control Rando's setting
    """
    if not args:
      g.com.announce('{} is ∆{}∆.'.format(g.RANDO_NICK, 'on' if g.rando else 'off'))
    elif nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can control ∆{}∆.'.format(g.creator, g.RANDO_NICK))
    elif args == 'on':
      g.rando = True
      g.com.announce('{} is ∆on∆.'.format(g.RANDO_NICK))
    elif args == 'off':
      g.rando = False
      g.com.announce('{} is ∆off∆.'.format(g.RANDO_NICK))
    else:
      g.com.reply(nick, 'Possible arguments: ∆on∆, ∆off∆.')

  @Command(names=['blank', 'blank', 'b'])
  def blank(self, g: Game, nick, args):
    """
    blank [<num>] -- controls number of blank white cards in the deck
    """
    if not args:
      g.com.announce('There are ∆{}∆ blank cards in the deck.'.format(g.blanks))
      return

    if nick != g.creator:
      g.com.notice(nick, 'Only ∆{}∆ can change the number of blanks in the deck.'.format(g.creator))
      return

    parts = args.split()
    if not parts[0].isnumeric():
      g.com.notice(nick, 'Specify a number.')
      return

    c = int(parts[0])
    if c < 0 or c > 100:
      g.com.notice(nick, 'Invalid argument.')
      return

    g.blanks = c
    g.com.announce('There are ∆{}∆ blank cards in the deck.'.format(g.blanks))


class PlayingCards(GamePhase):
  def __init__(self):
    self.copy_command(WaitingForPlayers.list_sets)
    self.copy_command(WaitingForPlayers.list_used_sets)

  def prepare(self, g: Game):
    g.com.announce('Starting a ∆{}∆ player ∆{}∆/∆{}∆ card game.'
                   .format(len(g.players),
                           len(g.deck.black_pool),
                           len(g.deck.white_pool)))

    g.deck.add_blank(g.blanks)

    for i in g.list_players():
      g.scores.register(i)

    random.shuffle(g.players)
    for player in g.list_players():
      g.hands[player] = g.deck.draw_white(g.HAND_SIZE)
      g.scores.register(player)

    g.czar_index = 0

    self.next_czar(g)

  def deal(self, g: Game):
    if g.scores.highest() >= g.limit or len(g.deck.black_pool) == 0 or not self._are_hands_full(g):
      g.com.announce('The game is over! ∆{}∆ won!'.format(', '.join(g.scores.winners())))
      g.reset()
      return

    self._set_timeouts(g)

    for i in g.joiners:
      g.com.announce('∆{}∆ is joining the game!'.format(i))
      g.players.append(i)
      g.hands[i] = g.deck.draw_white(g.HAND_SIZE)
      g.scores.register(i)

    g.joiners.clear()

    g.black_card = g.deck.draw_black()
    g.com.announce('Round ∆{}∆. The card czar is ∆{}∆. This round\'s card is...'
                   ''.format(g.round, g.czar))
    g.com.announce('    {}'.format(g.black_card))

    example_args = ' '.join(map(str, range(g.black_card.gaps)))
    example = 'pick {}'.format(example_args)
    waiting = list(g.players)
    waiting.remove(g.czar)
    msg = '{}: Play ∆{}∆ card{}, like "∆{}∆" or just "∆{}∆".' \
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

      hand_s = ' '.join(['[∆{}∆] {}'.format(i, j) for i, j in enumerate(hand)])
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
        return

      g.played[g.RANDO_NICK] = list(hand[:g.black_card.gaps])

  def _waiting_for(self, g: Game):
    return [i for i in g.players if i not in g.played and i != g.czar]

  def _set_timeouts(self, g: Game):
    def timeout_soon(g: Game):
      g.com.announce('Waiting for ∆{}∆ to play...'.format(', '.join(self._waiting_for(g))))

    g.timeout_handles.append(
      g.loop.call_later(g.PLAYING_CARDS_TIMEOUT_SOON.total_seconds(), timeout_soon, g))

    def timeout(g: Game):
      g.com.announce('∆{}∆ timed out!'.format(', '.join(self._waiting_for(g))))
      self._transition_choosing_winner(g)

    g.timeout_handles.append(
      g.loop.call_later(g.PLAYING_CARDS_TIMEOUT.total_seconds(), timeout, g))
    g.timeout_time = datetime.now() + g.PLAYING_CARDS_TIMEOUT

  def _are_hands_full(self, g: Game):
    return all(len(i) == g.HAND_SIZE for i in g.hands.values())

  def _transition_choosing_winner(self, g):
    g.cancel_timeouts()
    g.phase = ChoosingWinner()
    g.phase.prepare(g)

  def sanitize(self, s):
    return ''.join([i for i in s.strip() if i.isprintable()])

  @Command(names=['scores', 'sc', 'stats', 'points', 'pts'])
  def scores(self, g: Game, nick, args):
    """
    scores -- shows current point score
    """
    g.com.announce(str(g.scores))

  @Command(names=['join', 'j'])
  def join(self, g: Game, nick, args):
    """
    join -- allows to join an already running game
    """
    if nick in g.players:
      g.com.notice(nick, 'You are already playing.')
      return

    if nick in g.joiners:
      g.com.notice(nick, 'You are already joining.')
      return

    g.joiners.append(nick)
    g.com.notice(nick, 'You will be dealt into the game when the next round begins.')

  @Command(names=['leave'], player_only=True)
  def leave(self, g: Game, nick, args):
    """
    leave -- allows to leave an already running game
    """
    if nick in g.joiners:
      g.com.notice(nick, 'You will not join.')
      g.joiners.remove(nick)
      return

    g.com.notice(nick, 'You left the game.')
    g.com.announce('∆{}∆ has left the game!'.format(nick))

    g.players.remove(nick)
    if nick in g.played:
      del g.played[nick]
    g.deck.return_whites(g.hands[nick])
    del g.hands[nick]

    if g.count_players() < g.MIN_PLAYERS:
      g.com.announce('There are not enough players to continue. Game stopped.')
      g.reset()
      return

    if nick == g.czar:
      g.com.announce('The card czar left. Restarting the round...')
      g.deck.return_black(g.black_card)

      self.next_czar(g)

      g.phase = new_phase = PlayingCards()
      new_phase.deal(g)

    g.czar_index = g.players.index(g.czar)

  @Command(names=['pick', 'p'], player_only=True)
  def pick(self, g: Game, nick, args):
    """
    pick [<num>[ <num>[...]]] -- pick cards from you hand to play
    """
    if nick == g.czar:
      g.com.notice(nick, 'You are the card czar. '
                         'You choose the winner after everyone else has played.')
      return

    parts = args.split()
    choice = []
    if len(parts) != g.black_card.gaps:
      g.com.notice(nick, 'Wrong number of cards. ∆{}∆ needed.'.format(g.black_card.gaps))
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

    g.com.notice(nick, 'Your choice: {}'.format(g.black_card.insert(choice)))

    g.played[nick] = choice

    if len(g.played) == g.count_players() - 1:
      self._transition_choosing_winner(g)

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    """
    status -- shows information about the current game
    """
    g.com.announce('∆{}∆ players. ∆{}∆ is the card czar. Black card: "{}". '
                   'Waiting for ∆{}∆ to play.'
                   ''.format(g.count_players(),
      g.czar,
      g.black_card,
      ', '.join(self._waiting_for(g))))

  @Command(names=['cards', 'c', 'hand', 'h'], player_only=True)
  def cards(self, g: Game, nick, args):
    """
    cards -- shows your hand
    """
    hand = g.hands[nick]
    hand_s = ' '.join(['[∆{}∆] {}'.format(i, j) for i, j in enumerate(hand)])
    g.com.notice(nick, 'Your hand: {}.'.format(hand_s))

  @Command(names=['limit', 'l'])
  def limit(self, g: Game, nick, args):
    """
    limit -- shows the point limit
    """
    g.com.reply(nick, 'The point limit is ∆{}∆ points.'.format(g.limit))

  @Command(player_only=True, iff_pm=True)
  def write(self, g: Game, nick, args: str):
    """
    write <num> <text> -- writes <text> on blank card <num> from you hand
    """
    args = self.sanitize(args)

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

  @Command(player_only=True)
  def swap(self, g: Game, nick, args):
    if nick == g.czar:
      g.com.notice(nick, 'The card czar cannot swap cards.')
      return

    if g.scores.get_score(nick) <= 0:
      g.com.notice(nick, 'You need positive score to swap cards.')
      return

    g.com.announce('∆{}∆ traded one point for a brand new hand!'.format(nick))

    if nick in g.played:
      del g.played[nick]

    g.deck.return_whites(g.hands[nick])
    g.hands[nick] = g.deck.draw_white(g.HAND_SIZE)

    self.cards(g, nick, '')


class ChoosingWinner(GamePhase):
  def __init__(self):
    self.copy_command(PlayingCards.join)
    self.copy_command(PlayingCards.leave)
    self.copy_command(PlayingCards.cards)
    self.copy_command(PlayingCards.scores)
    self.copy_command(PlayingCards.swap)

    self.copy_command(WaitingForPlayers.list_sets)
    self.copy_command(WaitingForPlayers.list_used_sets)

  def prepare(self, g: Game):
    if len(g.played) < 2:
      g.com.announce('Not enough people have played anything :(. Restarting the round...')
      self._transition_playing_cards(g)
      return

    self._set_timeouts(g)

    g.com.announce('Everyone has played. Now ∆{}∆ has to choose a winner. '
                   'Candidates are:'.format(g.czar))

    g.player_perm = g.list_players()
    g.player_perm.remove(g.czar)
    random.shuffle(g.player_perm)

    for i, player in enumerate(g.player_perm):
      s = g.black_card.insert(g.played[player])
      g.com.announce('[∆{}∆] {}'.format(i, s))

  def _set_timeouts(self, g: Game):
    def timeout_soon(g: Game):
      g.com.announce('Waiting for ∆{}∆ to choose the winner...'.format(g.czar))

    g.timeout_handles.append(
      g.loop.call_later(g.CHOOSING_WINNER_TIMEOUT_SOON.total_seconds(), timeout_soon, g))

    def timeout(g: Game):
      g.com.announce('The czar ∆{}∆ timed out! Restarting the round...'.format(g.czar))
      g.deck.return_black(g.black_card)

      self._transition_playing_cards(g)

    g.timeout_handles.append(
      g.loop.call_later(g.CHOOSING_WINNER_TIMEOUT.total_seconds(), timeout, g))
    g.timeout_time = datetime.now() + g.CHOOSING_WINNER_TIMEOUT

  def _transition_playing_cards(self, g: Game):
    for player, cards in g.played.items():
      for card in cards:
        g.hands[player].remove(card)
      g.hands[player].extend(g.deck.draw_white(len(cards)))

    g.played.clear()

    g.cancel_timeouts()

    g.phase = new_phase = PlayingCards()
    new_phase.deal(g)

  @Command(names=['pick', 'p', 'winner', 'w'], player_only=True)
  def pick(self, g: Game, nick, args):
    """
    pick <num> -- pick the winner
    """
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
    if winner != g.RANDO_NICK and winner not in g.players:
      g.com.announce('Winner {} has left the game. No one gets a point.')
    else:
      g.com.announce('∆{}∆ wins with "{}".'
                     .format(winner, g.black_card.insert(g.played[winner])))
      s = 'Last round: {}'.format(
        ', '.join('[∆{}∆] {}'.format(i, Game.inject_zwsp(j)) for i, j in enumerate(g.player_perm)))
      g.com.announce(s)
      g.scores.point(winner)

    g.com.announce(str(g.scores))

    self.next_czar(g)

    g.round += 1

    self._transition_playing_cards(g)

  @Command(names=['status', 's'])
  def status(self, g: Game, nick, args):
    """
    status -- shows information about the current game
    """
    g.com.announce(
      '∆{}∆ players. Black card: "{}". Waiting for card czar ∆{}∆ to choose the winner.'
      ''.format(g.count_players(), g.black_card, g.czar))
