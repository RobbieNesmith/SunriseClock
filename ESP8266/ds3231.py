from machine import I2C

CLOCK_ADDRESS = 0x68

def time_to_seconds(hour, minute, second):
  return hour * 3600 + minue * 60 + second

def getSecond(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x00]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0])  

def getMinute(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x01]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0])

def getHour(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x02]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0] & 0b00111111)

def getDoW(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x03]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0])

def getDate(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x04]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0])

def getMonth(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x05]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0] & 0b01111111)

def getYear(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x06]))
  return _bcd_to_dec(i2c.readfrom(CLOCK_ADDRESS, 1)[0])

def setSecond(i2c, second):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x00, bytes([_dec_to_bcd(second)]))

def setMinute(i2c, minute):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x01, bytes([_dec_to_bcd(minute)]))

def setHour(i2c, hour):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x02]))
  h12 = i2c.readfrom(CLOCK_ADDRESS, 1)[0] & 0b01000000

  if h12:
    if hour > 12:
      hour = _dec_to_bcd((hour - 12) | 0b01100000)
    else:
      hour = _dec_to_bcd(hour) & 0b11011111
  else:
    hour = _dec_to_bcd(hour) & 0b10111111

  i2c.writeto_mem(CLOCK_ADDRESS, 0x02, bytes([hour]))
  
def setDow(i2c, dow):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x03, bytes([_dec_to_bcd(dow)]))

def setDate(i2c, date):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x04, bytes([_dec_to_bcd(date)]))

def setMonth(i2c, month):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x05, bytes([_dec_to_bcd(month)]))

def setYear(i2c, year):
  i2c.writeto_mem(CLOCK_ADDRESS, 0x06, bytes([_dec_to_bcd(year)]))

def setClockMode(i2c, h12):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x02]))
  temp = i2c.readfrom(CLOCK_ADDRESS, 1)[0]
  if h12:
    temp = temp | 0b01000000
  else:
    temp = temp & 0b10111111
  
  i2c.writeto_mem(CLOCK_ADDRESS, 0x02, temp)

def _bcd_to_dec(val):
# Convert binary coded decimal to normal decimal numbers
	return val // 16 * 10 + val % 16

def _dec_to_bcd(val):
  return val // 10 * 16 + val % 10

def get_time(i2c):
  i2c.writeto(CLOCK_ADDRESS, bytes([0x00]))
  date_bytes = i2c.readfrom(CLOCK_ADDRESS, 3)
  ss = _bcd_to_dec(date_bytes[0] & 0x7f)
  mm = _bcd_to_dec(date_bytes[1])
  hh = _bcd_to_dec(date_bytes[2])
  return ss + mm * 60 + hh * 3600