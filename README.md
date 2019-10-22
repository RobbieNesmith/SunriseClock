# SunriseClock
A sunrise alarm clock built using an ESP8266

## Parts list
* ESP8266
  * The main processor of the operation. Running [MicroPython](https://docs.micropython.org/en/latest/esp8266/tutorial/intro.html)
  * Copy the files in the ESP8266 directory to the root of the ESP's filesystem
* Arduino (In my case an Arduino Nano)
  * Handles the LED PWM so it doesn't block the server at all
  * Upload the `.ino` project from the Arduino directory
* DS3231 Clock module
* 3x P30N06LE N-Channel MOSFETs
* LED strips
  * 4 pin variety, no individually addressable LEDs