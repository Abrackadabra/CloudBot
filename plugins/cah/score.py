class Scores(object):
  def __init__(self):
    self.scores = {}

  def register(self, player):
    self.scores[player] = 0

  def point(self, player):
    self.scores[player] += 1

  def __str__(self):
    s = []
    for i, j in sorted(self.scores.items(), key=lambda x: -x[1]):
      s.append('{}-{}p'.format(i, j))
    return 'Scores: {}.'.format(', '.join(s))
