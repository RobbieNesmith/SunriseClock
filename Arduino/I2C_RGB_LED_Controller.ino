// Based on Wire Slave Reciever example

#define RED_PIN 9
#define GREEN_PIN 10
#define BLUE_PIN 11

#include <Wire.h>

int red, green, blue, pRed, pGreen, pBlue;

void setup() {
  Serial.begin(9600);
  Wire.begin(8);
  Wire.onReceive(receiveEvent);
}

void loop() {
  if (pRed != red) {
    analogWrite(RED_PIN, red);
  }
  if (pGreen != green) {
    analogWrite(GREEN_PIN, green);
  }
  if (pBlue != blue) {
    analogWrite(BLUE_PIN, blue);
  }
  delay(100);
}

void receiveEvent(int howMany) {
  int num = 0;
  while (Wire.available()) {
    int val = Wire.read();
    if (num == 0) {
      pRed = red;
      red = val;
    } else if (num == 1) {
      pGreen = green;
      green = val;
    } else if (num == 2) {
      pBlue = blue;
      blue = val;
    }
    num++;
  }
}
