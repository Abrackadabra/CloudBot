import json
import random


class BlackCard(object):
  MARKER = '%s'

  def __init__(self, text, gaps):
    """
    :type text: str
    :type gaps: int
    """
    self.text = text
    self.gaps = gaps

  def __str__(self):
    return self.text.replace(self.MARKER, '___')

  def insert(self, cards):
    s = str(self.text)

    if '%s' in s:
      for i in cards:
        s = s.replace(self.MARKER, i, 1)
      return s

    return '{} {}'.format(s, ' '.join(cards))

  def __eq__(self, other):
    return self.text == other.text and self.gaps == other.gaps


class Deck(object):
  def __init__(self, black_cards, white_cards):
    """
    :type black_cards: list[BlackCard]
    :type white_cards: list[str]
    """
    self.black_pool = black_cards
    self.black_used = []

    self.white_pool = white_cards
    self.white_used = []

  def draw_black(self):
    x = random.choice(self.black_pool)
    self.black_pool.remove(x)
    self.black_used.append(x)
    return x

  def draw_white(self, n):
    res = []
    for i in range(n):
      x = random.choice(self.white_pool)
      self.white_pool.remove(x)
      self.white_used.append(x)
      res.append(x)
    return res

  @staticmethod
  def read(filename):
    with open(filename) as file:
      deck = json.loads(''.join(file.readlines()))

      black_cards = []
      for i in deck['black']:
        x = BlackCard(**i)
        black_cards.append(x)

      return Deck(black_cards, deck['white'])

  def reset(self):
    self.black_pool.extend(self.black_used)
    self.black_used = []

    self.white_pool.extend(self.white_used)
    self.white_used = []

  def return_black(self, black_card):
    self.black_used.remove(black_card)
    self.black_pool.append(black_card)

  def return_whites(self, white_cards):
    for white_card in white_cards:
      self.white_used.remove(white_card)
      self.white_pool.append(white_card)
