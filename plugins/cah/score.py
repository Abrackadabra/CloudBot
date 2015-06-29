class Scores(object):
  def __init__(self):
    self.scores = {}

  def register(self, player):
    self.scores[player] = 0

  def point(self, player):
    self.scores[player] += 1

  def highest(self):
    if not self.scores:
      return 0

    return max(self.scores.values())

  def winners(self):
    m = self.highest()
    r = []
    for i, j in self.scores.items():
      if j == m:
        r.append(i)
    return r

  def __str__(self):
    s = []
    for i, j in sorted(self.scores.items(), key=lambda x: -x[1]):
      s.append('{}-{}p'.format(i, j))
    return 'Scores: {}.'.format(', '.join(s))
