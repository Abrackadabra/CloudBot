from collections import Counter
from datetime import datetime
import itertools
from cloudbot import hook


@hook.on_start()
def on_start():
  global words
  with open('data/countdown_wordlist') as file:
    lines = file.readlines()
    lines = [i.strip().lower() for i in lines]
    words = [i for i in lines if i]

@hook.command('words')
def words_command(text):
  if not text or any([not i.isalpha() for i in text]):
    return 'Invalid input'

  c = Counter(text)
  match = []
  for i in words:
    ok = True
    x = Counter(i)
    for j in i:
      ok &= x[j] <= c[j]
    if ok and len(i) > 2:
      match.append(i)

  match = sorted(match, key=lambda x: -len(x))

  return ', '.join(match[:10]) + ('...' if len(match) > 10 else '')


class Result(object):
  def __init__(self, num, ops=1, aset=None, arepr=None):
    self.num = num
    self.ops = ops
    if not aset:
      aset = {num}
    self.set = aset
    if not arepr:
      arepr = str(num)
    self.repr = arepr

  def __and__(self, other):
    return self.set & other.set

  def __str__(self):
    if self.ops > 1:
      return '({})'.format(self.repr)
    return self.repr

  def __repr__(self):
    return '{} = {} [{}]'.format(self.num, self, ', '.join(map(str, sorted(self.set))))

  def __add__(self, other):
    if self.num + other.num > 1000:
      return
    return Result(num=self.num + other.num,
                  ops=self.ops + other.ops,
                  aset=self.set | other.set,
                  arepr='{} + {}'.format(self, other))

  def __sub__(self, other):
    if self.num <= other.num:
      return
    return Result(num=self.num - other.num,
                  ops=self.ops + other.ops,
                  aset=self.set | other.set,
                  arepr='{} - {}'.format(self, other))

  def __mul__(self, other):
    if self.num * other.num > 1000:
      return
    return Result(num=self.num * other.num,
                  ops=self.ops + other.ops,
                  aset=self.set | other.set,
                  arepr='{} * {}'.format(self, other))

  def __truediv__(self, other):
    if self.num % other.num != 0:
      return None
    return Result(num=self.num // other.num,
                  ops=self.ops + other.ops,
                  aset=self.set | other.set,
                  arepr='{} / {}'.format(self, other))

  def __xor__(self, other):
    if self & other:
      return []
    a = [self + other,
         self - other,
         self * other,
         self / other]
    return [i for i in a if i]

  def __eq__(self, other):
    return self.num == other.num and self.set == other.set

  def __hash__(self):
    return self.num ^ self.ops

  def __bool__(self):
    return self.num > 0


def get_all(nums):
  a = set([Result(i) for i in nums])
  while True:
    b = set(a)
    for i, j in itertools.combinations(a, 2):
      b |= set(i ^ j)

    if a == b:
      break
    a = b
  return a

@hook.command('numbers')
def numbers_command(text, reply):
  parts = text.split()
  if len(parts) < 3:
    return 'Too few numbers.'
  if len(parts) > 7:
    return 'Too many numbers.'
  for i in parts:
    if not i.isnumeric():
      return 'Not a number.'

  parts = [int(i) for i in parts]

  target = parts[0]
  nums = parts[1:]
  if max(nums) > 100 or target > 1000:
    return 'Numbers are too big.'
  if len(set(parts)) < len(parts):
    return 'Numbers are not unique.'

  results = get_all(nums)

  sol = False
  for i in results:
    if i.num == target:
      reply(repr(i))
      sol = True

  if not sol:
    reply('No exact solution exists.')

    for i in results:
      if abs(i.num - target) == 1:
        reply(repr(i))
