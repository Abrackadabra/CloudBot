from .deck import Deck
from .states import NoGame


class Game(object):
  def __init__(self, com, card_dir):
    """
    :type com: Communicator
    """
    self.deck = Deck.read(card_dir + '/official_deck.json')

    self._com = com

    self.state = NoGame(com, self.deck)

  def process(self, nick, command, args):
    self.state = self.state.process(nick, command, args) or self.state
