import gc
import json
import uasyncio
import usocket as socket
import uselect as select
import utime
from machine import Pin, I2C

from ColorStop import ColorStop
from Fade import Fade
from Timer import Timer

from ESP8266WebServer import ESP8266WebServer

from ds3231 import *

WAITING_FOR_FADE = 0
FADING = 1
MANUAL_MODE = 2
SUNSET_MODE = 3
FADES_FILE = "fades.json"
RECENT_COLORS_FILE = "recents.json"
MAX_RECENT_COLORS = 10

SUNSET_FADE_JSON = "sunset.json"

sunset_fade = {}

def get_default_response():
  return {"headers": {"Access-Control-Allow-Origin": "*"}}

def lerp(cs1, cs2, pos):
  if pos < 0:
    pos = 0
  elif pos > 1:
    pos = 1
  r = cs1.r * (1 - pos) + cs2.r * pos
  g = cs1.g * (1 - pos) + cs2.g * pos
  b = cs1.b * (1 - pos) + cs2.b * pos
  w = cs1.w * (1 - pos) + cs2.w * pos
  return ColorStop(r, g, b, w)

def render_color_stop(cs, i2c):
  cmd = bytearray([int(cs.r), int(cs.g), int(cs.b), int(cs.w)])
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

def serialize_color(color):
  return json.dumps(color.__dict__)

def deserialize_fade(fade_json):
  start_time_json = fade_json["start_time"]
  start_time_seconds = time_to_seconds(start_time_json["hours"], start_time_json["minutes"], start_time_json["seconds"])
  fade = Fade(start_time_seconds, fade_json["millis_per_tick"], set(fade_json["days_of_week"]))
  for color_stop in fade_json["stops"]:
    r = color_stop["r"] if "r" in color_stop else 0
    g = color_stop["g"] if "g" in color_stop else 0
    b = color_stop["b"] if "b" in color_stop else 0
    w = color_stop["w"] if "w" in color_stop else 0
    fade.add_color_stop(ColorStop(r,g,b,w), color_stop["t"]) 
  return fade

def get_fade_timings_from_json(filename):
  fades = {}
  with open(filename) as fade_file:
    fades_json = json.load(fade_file)
    for fade_id in fades_json["fades"]:
      fade = fades_json["fades"][fade_id]
      start_hms = fade["start_time"]
      seconds_per_tick = fade["millis_per_tick"] / 1000
      color_stops = fade["stops"]
      start_time = time_to_seconds(start_hms["hours"], start_hms["minutes"], start_hms["seconds"])
      end_time = start_time
      for stop in color_stops:
        end_time = end_time + stop["t"] * seconds_per_tick
      fades[fade_id] = {"start_time": start_time, "end_time": end_time, "days_of_week": fade["days_of_week"]}
  return fades

def get_fade_from_json_by_id(filename, fade_id):
  with open(filename) as fade_file:
    fades_json = json.load(fade_file)
    return fades_json["fades"][fade_id]

def get_recent_colors(filename):
  try:
    with open(filename) as recent_colors_file:
      return json.load(recent_colors_file)
  except:
    return []

def add_recent_color(filename, color):
  color_serialized = serialize_color(color)
  recent_colors = get_recent_colors(filename)
  if color_serialized not in recent_colors:
    recent_colors.append(color_serialized)
  if len(recent_colors) > MAX_RECENT_COLORS:
    recent_colors = recent_colors[-MAX_RECENT_COLORS:]
  with open(filename, "w") as recent_colors_file:
    json.dump(recent_colors, recent_colors_file)

def main():
  i2c = I2C(sda=Pin(4), scl=Pin(5))
  i2c.writeto(8, bytearray([0,0,0,0]))
  i2c.writeto(8, bytearray([0,0,0,0]))
  
  ws = ESP8266WebServer()

  cur_fade = None
  fades = get_fade_timings_from_json(FADES_FILE)
  with open(SUNSET_FADE_JSON) as fade_file:
    sunset_fade = deserialize_fade(json.load(fade_file))

  manual_color = ColorStop(0,0,0,0)

  sunset_start_time = 0

  timer = Timer()

  context = {"state": WAITING_FOR_FADE}

  @ws.route("/manual")
  def manual_route(request_object):
    context["state"] = MANUAL_MODE
    manual_color.r = 0
    manual_color.g = 0
    manual_color.b = 0
    manual_color.w = 0
    qp = request_object["query_params"]
    if "red" in qp:
      try:
        manual_color.r = int(qp["red"])
      except ValueError:
        pass
    if "green" in qp:
      try:
        manual_color.g = int(qp["green"])
      except ValueError:
        pass
    if "blue" in qp:
      try:
        manual_color.b = int(qp["blue"])
      except ValueError:
        pass
    if "white" in qp:
      try:
        manual_color.w = int(qp["white"])
      except ValueError:
        pass
    cmd = bytearray([manual_color.r, manual_color.g, manual_color.b, manual_color.w])
    i2c.writeto(8, cmd)
    add_recent_color(RECENT_COLORS_FILE, manual_color)
    return get_default_response()

  @ws.route("/auto")
  def auto_route(request_object):
    context["state"] = WAITING_FOR_FADE
    i2c.writeto(8, bytearray([0,0,0,0]))
    return get_default_response()

  @ws.route("/sunset")
  def sunset_route(request_object):
    context["state"] = SUNSET_MODE
    sunset_fade.start_time = get_time(i2c)
    start_fade(timer, sunset_fade, i2c)
    return get_default_response()

  @ws.route("/getstate")
  def get_state_route(request_object):
    resp = get_default_response()
    resp["payload"] = ["WAITING_FOR_FADE","FADING","MANUAL_MODE", "SUNSET_MODE"][context["state"]]
    return resp

  @ws.route("/getcurrentcolor")
  def get_current_color_route(request_object):
    if context["state"] == MANUAL_MODE:
      color = serialize_color(manual_color)
    elif context["state"] == WAITING_FOR_FADE:
      color = '{"r":0,"g":0,"b":0,"w":0}'
    elif context["state"] == FADING:
      color = serialize_color(get_current_color(timer, cur_fade))
    resp = get_default_response()
    resp["payload"] = color
    return resp

  @ws.route("/getmanualcolor")
  def get_manual_color_route(request_object):
    resp = get_default_response()
    resp["payload"] = serialize_color(manual_color)
    return resp

  @ws.route("/getdow")
  def get_dow_route(request_object):
    resp = get_default_response()
    resp["payload"] = "%d" % (getDow(i2c))
    return resp

  @ws.route("/setdow")
  def set_dow_route(request_object):
    qp = request_object["query_params"]
    if "dow" in qp:
      setDow(i2c, int(qp["dow"]))
    return get_default_response()

  @ws.route("/getdatetime")
  def get_datetime_route(request_object):
    year = getYear(i2c)
    month = getMonth(i2c)
    day = getDate(i2c)
    hour = getHour(i2c)
    minute = getMinute(i2c)
    second = getSecond(i2c)
    resp = get_default_response()
    resp["payload"] = "%04d-%02d-%02dT%02d:%02d:%02d" % (2000 + year, month, day, hour, minute, second)
    return resp

  @ws.route("/setdatetime")
  def set_datetime_route(request_object):
    new_datetime = request_object["query_params"]
    if "year" in new_datetime:
      try:
        setYear(i2c, int(new_datetime["year"]))
      except ValueError:
        pass
    if "month" in new_datetime:
      try:
        setMonth(i2c, int(new_datetime["month"]))
      except ValueError:
        pass
    if "day" in new_datetime:
      try:
        setDate(i2c, int(new_datetime["day"]))
      except ValueError:
        pass
    if "hour" in new_datetime:
      try:
        setHour(i2c, int(new_datetime["hour"]))
      except ValueError:
        pass
    if "minute" in new_datetime:
      try:
        setMinute(i2c, int(new_datetime["minute"]))
      except ValueError:
        pass
    if "second" in new_datetime:
      try:
        setSecond(i2c, int(new_datetime["second"]))
      except ValueError:
        pass
    return get_default_response()

  @ws.route("/getmemfree")
  def get_memory_free(request_object):
    resp = get_default_response()
    resp["payload"] = "Memory Free: {} bytes".format(gc.mem_free())
    return resp

  @ws.route("/fades")
  def get_fades(request_object):
    resp = get_default_response()
    resp["headers"]["Content-type"] = "application/json"
    if "id" in request_object["query_params"]:
      resp["payload"] = json.dumps(get_fade_from_json_by_id(FADES_FILE, request_object["query_params"]["id"]))
    else:
      resp["payload"] = json.dumps(get_fade_timings_from_json(FADES_FILE))
    return resp

  @ws.route("/recent_colors")
  def get_recent_colors_route(request_object):
    resp = get_default_response()
    resp["headers"]["Content-type"] = "application/json"
    resp["payload"] = json.dumps(get_recent_colors(RECENT_COLORS_FILE))
    return resp

  @ws.background_process
  async def rgb_background():
    while True:
      if context["state"] == WAITING_FOR_FADE:
        current_time = get_time(i2c)
        current_dow = getDow(i2c)
        for fade_id in fades:
          fade = fades[fade_id]
          if current_time > fade["start_time"] and current_time < fade["end_time"] and current_dow in fade["days_of_week"]:
            cur_fade = deserialize_fade(get_fade_from_json_by_id(FADES_FILE, fade_id))
            start_fade(timer, cur_fade, i2c)
            context["state"] = FADING
      elif context["state"] == FADING:
        if cur_fade == None:
          context["state"] = WAITING_FOR_FADE
        elif timer.cur_stop >= len(cur_fade.color_stops) - 1:
          cur_fade = None
        else:
          increment_fade(timer, cur_fade, i2c)
      elif context["state"] == MANUAL_MODE:
        # set the color manually
        pass
      elif context["state"] == SUNSET_MODE:
        current_time = get_time(i2c)
        if timer.cur_stop >= len(sunset_fade.color_stops) - 1:
          context["state"] = WAITING_FOR_FADE
        else:
          increment_fade(timer, sunset_fade, i2c)
      await uasyncio.sleep(1)

  ws.run()

main()
