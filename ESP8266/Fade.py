from ColorStop import ColorStop

class Fade:
  def __init__(self, start_time, millis_per_tick = 1000):
    self.start_time = start_time
    self.duration = 0
    self.millis_per_tick = millis_per_tick
    self.color_stops = []
    self.ticks_per_stop = []
  
  def add_color_stop(self, cs, ticks):
    self.color_stops.append(cs)
    self.ticks_per_stop.append(ticks)
    self.duration = self.duration + ticks * self.millis_per_tick / 1000
  
  def remove_color_stop(i):
    del self.color_stops[i]
    self.duration = self.duration - ticks * self.millis_per_tick / 1000
    del self.ticks_per_stop[i]