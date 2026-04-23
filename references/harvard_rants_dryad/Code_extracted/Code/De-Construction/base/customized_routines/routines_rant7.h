#ifndef CUSTOMIZED_ROUTINES_H
#define CUSTOMIZED_ROUTINES_H

float detectionThreshold = 1008; // recognition of obstacle at this sensor value (max value 1024)
float sensorLow[2]={38,38}; // array storing lowest sensor value
float sensorHigh[2]={740,860}; // array storing highest sensor value
float speedCorrection = 0.0;

void setMotors(int mLeft, int mRight){
  if(mLeft<=0){
    digitalWrite(11, HIGH);
  }
  else {
    digitalWrite(11, LOW);
  }
  analogWrite(10,abs(mLeft));

  if(mRight<=0){
    digitalWrite(7, LOW);
  }
  else {
    digitalWrite(7, HIGH);
  }
  analogWrite(9,abs(mRight));
}

// set magnet state to be engaged (1) or disengaged (0)
void setServo(Servo myservo, bool state) {
  if(state){
	myservo.write(0);
  }
  else{
	myservo.write(180);
  }
  delay(100);
}

#endif
