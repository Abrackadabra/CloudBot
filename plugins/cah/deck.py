import json
import random


class Deck(object):
  def __init__(self, black_cards, white_cards):
    self.black_pool = list(black_cards)
    self.black_used = []

    self.white_pool = list(white_cards)
    self.white_used = []

  def draw_black(self):
    x = random.choice(self.black_pool)
    self.black_pool.remove(x)
    self.black_used.append(x)
    return x['text'], x['cards']

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
      return Deck(deck['black'], deck['white'])

  def reset(self):
    self.black_pool.extend(self.black_used)
    self.black_used = []

    self.white_pool.extend(self.white_used)
    self.white_used = []
