import usocket as socket
import uselect as select
import utime
from machine import Pin, I2C

from ds3231 import *

WAITING_FOR_FADE = 0
FADING = 1
MANUAL_MODE = 2

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

class Timer:
  def __init__(self):
    self.millis = 0
    self.tick = 0
    self.cur_stop = 0

def render_color_stop(cs, i2c):
  cmd = bytearray([int(cs.r), int(cs.g), int(cs.b)])
  i2c.writeto(8, cmd)

def start_fade(timer, fade, i2c):
  current_time = get_time(i2c)
  timer.millis = utime.ticks_ms()
  timer.tick = (current_time - fade.start_time) * 1000 // fade.millis_per_tick
  timer.cur_stop = 0
  while timer.tick > fade.ticks_per_stop[timer.cur_stop]:
    timer.tick = timer.tick - fade.ticks_per_stop[timer.cur_stop]
    timer.cur_stop = timer.cur_stop + 1

def get_current_color(timer, fade):
  return lerp(fade.color_stops[timer.cur_stop], fade.color_stops[timer.cur_stop + 1], timer.tick / fade.ticks_per_stop[timer.cur_stop])

def increment_fade(timer, fade, i2c):
  curTime = utime.ticks_ms()
  tDiff = utime.ticks_diff(curTime, timer.millis)
  if timer.cur_stop < len(fade.color_stops) - 1:
    render_color_stop(get_current_color(timer, fade), i2c)
    if tDiff >= fade.millis_per_tick:
      timer.tick += 1
      timer.millis = curTime
    if timer.tick >= fade.ticks_per_stop[timer.cur_stop]:
      timer.tick = 0
      timer.cur_stop += 1

def time_to_seconds(hour, minute, second):
  return hour * 3600 + minute * 60 + second

def send_ok(client, message="200 OK", headers=[]):
  client.send('HTTP/1.0 200 OK\r\n')
  client.send('Access-Control-Allow-Origin: *\r\n')
  for header in headers:
    client.send(header.strip() + '\r\n')
  client.send('\r\n')
  client.send(message)

def color_to_hex(color):
  return "#%02x%02x%02x" % (color.r, color.g, color.b)

def main():
  i2c = I2C(sda=Pin(4), scl=Pin(5))
  i2c.writeto(8, bytearray([0,0,0]))
  
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server.bind(("0.0.0.0", 80))
  server.listen(5)
  
  cur_fade = None
  fades = []
  
  morning_fade = Fade(time_to_seconds(6, 30, 0), millis_per_tick=10000)
  morning_fade.add_color_stop(ColorStop(0,0,0), 90)
  morning_fade.add_color_stop(ColorStop(40,2,1), 90)
  morning_fade.add_color_stop(ColorStop(255,87,14), 180)
  morning_fade.add_color_stop(ColorStop(255,87,14), 6)
  morning_fade.add_color_stop(ColorStop(0,0,0),6)
  morning_fade.add_color_stop(ColorStop(0,0,0),6)
  fades.append(morning_fade)
  
  evening_fade = Fade(time_to_seconds(18,0,0), millis_per_tick=10000)
  evening_fade.add_color_stop(ColorStop(0,0,0), 6)
  evening_fade.add_color_stop(ColorStop(255,87,14), 1080)
  evening_fade.add_color_stop(ColorStop(255,87,14), 360)
  evening_fade.add_color_stop(ColorStop(40,2,1), 360)
  evening_fade.add_color_stop(ColorStop(3,0,4), 360)
  evening_fade.add_color_stop(ColorStop(0,0,0), 6)
  evening_fade.add_color_stop(ColorStop(0,0,0), 6)
  fades.append(evening_fade)
  
  manual_color = ColorStop(0,0,0)
  
  timer = Timer()
  
  state = WAITING_FOR_FADE
  
  while True:
    #server tasks
    r, w, err = select.select((server,), (), (), 1)
    if r:
      for readable in r:
        client, client_addr = server.accept()
        try:
          req = client.recv(1024)
          http = req.split(b"\r\n")[0]
          http_split = http.split(b" ")
          if len(http_split) > 1:
            addr = http.split(b" ")[1]
            if addr.startswith(b"/manual"):
              state = MANUAL_MODE
              if b"?" in addr:
                query = addr.split(b"?")[1]
                queries = query.split(b"&")
                for q in queries:
                  kv = q.split(b"=")
                  if len(kv) == 2:
                    if kv[0] == b"red":
                      if len(kv) > 1:
                        manual_color.r = int(kv[1])
                      else:
                        manual_color.r = 0
                    elif kv[0] == b"green":
                      if len(kv) > 1:
                        manual_color.g = int(kv[1])
                      else:
                        manual_color.g = 0
                    elif kv[0] == b"blue":
                      if len(kv) > 1:
                        manual_color.b = int(kv[1])
                      else:
                        manual_color.b = 0
              cmd = bytearray([manual_color.r, manual_color.g, manual_color.b])
              i2c.writeto(8, cmd)
              send_ok(client)
            elif addr.startswith(b"/auto"):
              state = WAITING_FOR_FADE
              i2c.writeto(8, bytearray([0,0,0]))
              send_ok(client)
            elif addr.startswith(b"/getstate"):
              send_ok(client, ["WAITING_FOR_FADE","FADING","MANUAL_MODE"][state])
            elif addr.startswith(b"/getcurrentcolor"):
              if state == MANUAL_MODE:
                color = color_to_hex(manual_color)
              elif state == WAITING_FOR_FADE:
                color = "#000000"
              elif state == FADING:
                color = get_current_color(timer, cur_fade)
              send_ok(client, color)
            elif addr.startswith(b"/getmanualcolor"):
              send_ok(client, message=color_to_hex(manual_color))
            else:
              send_ok(client, "Hello %d<br />You requested %s" % (utime.ticks_cpu(), addr.decode()))
          client.close()
        except OSError as e:
          pass

    #background tasks
    if state == WAITING_FOR_FADE:
      current_time = get_time(i2c)
      for fade in fades:
        if current_time > fade.start_time and current_time < fade.start_time + fade.duration:
          start_fade(timer, fade, i2c)
          cur_fade = fade
          state = FADING
    elif state == FADING:
      if cur_fade == None:
        state = WAITING_FOR_FADE
      elif timer.cur_stop >= len(cur_fade.color_stops) - 1:
        cur_fade = None
      else:
        increment_fade(timer, cur_fade, i2c)
    elif state == MANUAL_MODE:
      # set the color manually
      pass

main()