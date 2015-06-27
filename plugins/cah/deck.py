import json
import os
import random
import requests


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
    return self.text.replace(self.MARKER, '\x02___\x02')

  def insert(self, cards):
    s = str(self.text)

    if self.MARKER in s:
      for i in cards:
        s = s.replace(self.MARKER, '\x02{}\x02'.format(i), 1 if len(cards) > 0 else -1)
      return s

    return '{} {}'.format(s, ' '.join(cards))

  def __eq__(self, other):
    return self.text == other.text and self.gaps == other.gaps

class Set(object):
  def __init__(self, name, black, white):
    self.name = name
    self.black = black
    self.white = white

  @staticmethod
  def read(filename):
    with open(filename) as file:
      s = json.loads(' '.join(file.readlines()))

      return Set(
        name=s['name'],
        black=[BlackCard(**i) for i in s['black']],
        white=s['white']
      )

  @staticmethod
  def load(set_id):
    if len(set_id) != 5:
      raise Exception('Wrong syntax, set id should be 5 symbols')

    URL_META = 'https://api.cardcastgame.com/v1/decks/{}'
    URL_CARDS = 'https://api.cardcastgame.com/v1/decks/{}/cards'

    r = requests.get(URL_META.format(set_id))

    if r.status_code == 404:
      raise Exception('No such set.')
    if r.status_code != 200:
      raise Exception('Strange error.')

    x = json.loads(r.text)
    name = x['name']

    r = requests.get(URL_CARDS.format(set_id))

    if r.status_code == 404:
      raise Exception('No such set.')
    if r.status_code != 200:
      raise Exception('Strange error.')

    x = json.loads(r.text)

    black = []
    for i in x['calls']:
      gaps = len(i['text']) - 1
      text = BlackCard.MARKER.join(i['text'])
      black.append(BlackCard(text, gaps))

    white = []
    for i in x['responses']:
      white.append(i['text'])

    return Set(name=name, black=black, white=white)

  def to_file(self, dir):
    filename = self.name.lower().replace(' ', '_') + '.json'

    with open(os.path.join(dir, 'cardcast', filename), 'w') as file:
      file.write(json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=2))


class Deck(object):
  def __init__(self, dir):
    self.sets = {}
    """:type : dict[str, Set]"""

    self.read_dir(dir)

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

  def read_dir(self, dir):
    files = os.listdir(dir)
    for filename in files:
      filename = os.path.join(dir, filename)
      if os.path.isfile(filename) and filename.endswith('.json'):
        set = Set.read(filename)
        self.sets[set.name] = set

    files = os.listdir(os.path.join(dir, 'cardcast'))
    for filename in files:
      filename = os.path.join(dir, 'cardcast', filename)
      if os.path.isfile(filename) and filename.endswith('.json'):
        set = Set.read(filename)
        self.sets[set.name] = set
