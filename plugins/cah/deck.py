import json
import os
import random


class BlackCard(object):
  MARKER = '_'

  def __init__(self, text, gaps):
    """
    :type text: str
    :type gaps: int
    """
    self.text = text
    self.gaps = gaps

  def __str__(self):
    return self.text.replace(self.MARKER, '\x02___\x02')

  def insert(self, cards):
    s = str(self.text)

    if self.MARKER in s:
      for i in cards:
        s = s.replace(self.MARKER, '\x02{}\x02'.format(i), 1)
      return s

    return '{} {}'.format(s, ' '.join(cards))

  def __eq__(self, other):
    return self.text == other.text and self.gaps == other.gaps


class Set(object):
  def __init__(self, filename):
    with open(filename) as file:
      s = json.loads(' '.join(file.readlines()))

      self.black = [BlackCard(**i) for i in s['black']]
      self.white = s['white']
      self.name = s['name']


class Deck(object):
  def __init__(self, dir):
    self.sets = {}
    """:type : dict[str, Set]"""

    files = os.listdir(dir)
    for filename in files:
      filename = os.path.join(dir, filename)
      if os.path.isfile(filename) and filename.endswith('.json'):
        set = Set(filename)
        self.sets[set.name] = set

    self.reset()

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

  def reset(self):
    self.black_pool = []
    self.black_used = []

    self.white_pool = []
    self.white_used = []

    self.used_sets = []

    self.add_set('Base Set')

  def return_black(self, black_card):
    self.black_used.remove(black_card)
    self.black_pool.append(black_card)

  def return_whites(self, white_cards):
    for white_card in white_cards:
      self.white_used.remove(white_card)
      self.white_pool.append(white_card)

  def add_set(self, name):
    if name in self.used_sets:
      return

    self.used_sets.append(name)
    self.black_pool.extend(self.sets[name].black)
    self.white_pool.extend(self.sets[name].white)

  def remove_set(self, name):
    if name not in self.used_sets:
      return

    self.used_sets.remove(name)
    for i in self.sets[name].black:
      self.black_pool.remove(i)
    for i in self.sets[name].white:
      self.white_pool.remove(i)

  def list_all_sets(self):
    return sorted(self.sets.keys())

  def list_used_sets(self):
    return list(self.used_sets)
