class ColorStop:
  def __init__(self, r, g, b):
    self.r = r
    self.g = g
    self.b = b

def lerp(cs1, cs2, pos):
  if pos < 0:
    pos = 0
  elif pos > 1:
    pos = 1
  r = cs1.r * (1 - pos) + cs2.r * pos
  g = cs1.g * (1 - pos) + cs2.g * pos
  b = cs1.b * (1 - pos) + cs2.b * pos
  return ColorStop(r, g, b)