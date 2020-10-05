import json
import usocket as socket
import uselect as select
import utime
from machine import Pin, I2C

from ColorStop import ColorStop
from Fade import Fade
from Timer import Timer

from ds3231 import *

WAITING_FOR_FADE = 0
FADING = 1
MANUAL_MODE = 2

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
  return "#%02x%02x%02x" % (int(color.r), int(color.g), int(color.b))

def get_query_params(addr):
  query_params = {}
  if b"?" in addr:
    query = addr.split(b"?")[1]
    queries = query.split(b"&")
    for q in queries:
      kv = q.split(b"=")
      if len(kv) == 2:
        query_params[kv[0]] = kv[1]
  return query_params

def deserialize_fade(fade_json):
  start_time_json = fade_json["start_time"]
  start_time_seconds = time_to_seconds(start_time_json["hours"], start_time_json["minutes"], start_time_json["seconds"])
  fade = Fade(start_time_seconds, fade_json["millis_per_tick"], set(fade_json["days_of_week"]))
  for color_stop in fade_json["stops"]:
    fade.add_color_stop(ColorStop(color_stop["r"],color_stop["g"],color_stop["b"]), color_stop["t"]) 
  return fade

def main():
  i2c = I2C(sda=Pin(4), scl=Pin(5))
  i2c.writeto(8, bytearray([0,0,0]))
  
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server.bind(("0.0.0.0", 80))
  server.listen(5)
  
  cur_fade = None
  fades = {}
  with open("fades.json") as fade_file:
    fades_json = json.load(fade_file)
    for fade_id in fades_json["fades"]:
      fades[fade_id] = deserialize_fade(fades_json["fades"][fade_id])
  
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
              manual_color.r = 0
              manual_color.g = 0
              manual_color.b = 0
              qp = get_query_params(addr)
              if b"red" in qp:
                try:
                  manual_color.r = int(qp[b"red"])
                except ValueError:
                  pass
              if b"green" in qp:
                try:
                  manual_color.g = int(qp[b"green"])
                except ValueError:
                  pass
              if b"blue" in qp:
                try:
                  manual_color.b = int(qp[b"blue"])
                except ValueError:
                  pass
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
                color = color_to_hex(get_current_color(timer, cur_fade))
              send_ok(client, color)
            elif addr.startswith(b"/getmanualcolor"):
              send_ok(client, message=color_to_hex(manual_color))
            elif addr.startswith(b"/getdow"):
              send_ok(client, message="%d" % (getDow(i2c)))
            elif addr.startswith(b"/setdow"):
              qp = get_query_params(addr)
              if b"dow" in qp:
                setDow(i2c, int(qp[b"dow"]))
                send_ok(client)
            elif addr.startswith(b"/getdatetime"):
              year = getYear(i2c)
              month = getMonth(i2c)
              day = getDate(i2c)
              hour = getHour(i2c)
              minute = getMinute(i2c)
              second = getSecond(i2c)
              send_ok(client, message="%04d-%02d-%02dT%02d:%02d:%02d" % (2000 + year, month, day, hour, minute, second))
            elif addr.startswith(b"/setdatetime"):
              new_datetime = get_query_params(addr)
              if b"year" in new_datetime:
                try:
                  setYear(i2c, int(new_datetime[b"year"]))
                except ValueError:
                  pass
              if b"month" in new_datetime:
                try:
                  setMonth(i2c, int(new_datetime[b"month"]))
                except ValueError:
                  pass
              if b"day" in new_datetime:
                try:
                  setDate(i2c, int(new_datetime[b"day"]))
                except ValueError:
                  pass
              if b"hour" in new_datetime:
                try:
                  setHour(i2c, int(new_datetime[b"hour"]))
                except ValueError:
                  pass
              if b"minute" in new_datetime:
                try:
                  setMinute(i2c, int(new_datetime[b"minute"]))
                except ValueError:
                  pass
              if b"second" in new_datetime:
                try:
                  setSecond(i2c, int(new_datetime[b"second"]))
                except ValueError:
                  pass
              send_ok(client)
            else:
              send_ok(client, "Hello %d<br />You requested %s" % (utime.ticks_cpu(), addr.decode()))
          client.close()
        except OSError as e:
          pass

    #background tasks
    if state == WAITING_FOR_FADE:
      current_time = get_time(i2c)
      current_dow = getDow(i2c)
      for fade_id in fades:
        fade = fades[fade_id]
        if current_time > fade.start_time and current_time < fade.start_time + fade.duration and current_dow in fade.days_of_week:
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
