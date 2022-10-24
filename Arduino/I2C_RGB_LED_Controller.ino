// Based on Wire Slave Reciever example

#define RED_PIN 9
#define GREEN_PIN 10
#define BLUE_PIN 11
#define WHITE_PIN 3
#define AUX1_PIN 5
#define AUX2_PIN 6

#include <Wire.h>

int red, green, blue, pRed, pGreen, pBlue, white, pWhite, aux1, pAux1, aux2, pAux2;

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
  if (pWhite != white) {
    analogWrite(WHITE_PIN, white);
  }
  if (pAux1 != aux1) {
    analogWrite(AUX1_PIN, aux1);
  }
  if (pAux2 != aux2) {
    analogWrite(AUX2_PIN, aux2);
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
    } else if (num == 3) {
      pWhite = white;
      white = val;
    } else if (num == 4) {
      pAux1 = aux1;
      aux1 = val;
    } else if (num == 5) {
      pAux2 = aux2;
      aux2 = val;
    }
    num++;
  }
}
