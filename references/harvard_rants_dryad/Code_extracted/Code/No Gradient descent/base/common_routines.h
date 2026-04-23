#ifndef COMMON_ROUTINES_H
#define COMMON_ROUTINES_H

// get reading of sensors averaged over N measurements
void getPheromoneReading(float *sensorValues,float N) {
  // read the value from the sensor:
  float meanL = 0;
  float meanR = 0;
  for(int i=0;i<N;i++){
    meanL = analogRead(A4)/N + meanL;
    meanR = analogRead(A3)/N + meanR;    
  }
    sensorValues[0] = meanL;
    sensorValues[1] = meanR;
    delay(1);
}

void checkBumpSensor(float *bumpSens,float N) {
  float mean = 0;
  for(int i=0;i<N;i++){
    mean = (float)analogRead(A5)/N + mean;
  }
    bumpSens[0] = mean;
    delay(1);
}

// sensor calibration
void calibration(int calibrationThreshold, int sensorSamples, float *sensorLow, float *sensorHigh, float *sensorValues, Servo myservo) {
  bool calibrationStatus = 0;
  getPheromoneReading(sensorValues,sensorSamples);
  float sensorMemory[2];
  sensorMemory[0] = sensorValues[0];
  sensorMemory[1] = sensorValues[1];
  while(calibrationStatus != 1) {
    getPheromoneReading(sensorValues,sensorSamples);
    if(sensorValues[0] - sensorMemory[0] > calibrationThreshold){
      sensorLow[0] = sensorMemory[0];
      sensorLow[1] = sensorMemory[1];
      sensorHigh[0] = sensorValues[0];
      sensorHigh[1] = sensorValues[1];
      calibrationStatus = 1;
      setServo(myservo, 0);
      delay(5000);  
    }
    sensorMemory[0] = sensorValues[0];
    sensorMemory[1] = sensorValues[1];
    delay(500);
  }
}

// Gradient descent
void gradientDescent(float *sLo, float *sHi, int sensorSamples, int dir, int v0, float G, float ls, float lw, int ks, float sc, float P, float *rotMemory) {
  float sVal[2];
  getPheromoneReading(sVal,sensorSamples);
  float signalLeft = (sVal[0]-sLo[0])/(sHi[0]-sLo[0]);
  float signalRight = (sVal[1]-sLo[1])/(sHi[1]-sLo[1]);
  float randN = (float)random(-1000,1000)/1000.0;
  float randRotation = rotMemory[0] + 0.1*randN; // contribution from random rotation
  rotMemory[1] = randRotation;
  float randCont = sin(randRotation*PI)/ls; // contribution from random walk

  float omega = randCont;
  float w0 = omega*lw/2; // transform angular velocity to wheel speeds  
  w0 = 40 + (255-40)/(18-2)*(w0*100-2);
  float speedLeft;
  float speedRight;

  speedLeft = (v0 - G*w0)*(1+sc) ;
  speedRight = (v0 + G*w0)*(1-sc);
  
  setMotors(speedLeft*(float)dir,speedRight*(float)dir);

  //Serial.println(w0);
}

// set motor speeds to follow pheromone (dir=1) or be repelled by it (dir=-1)
void followPheromone(int baseSpeed, float *sLo, float *sHi, int sensorSamples, int dir, float P, float *rotMemory) {
  float sVal[2];
  getPheromoneReading(sVal,sensorSamples);
  float signalLeft = (sVal[0]-sLo[0])/(sHi[0]-sLo[0]); 
  float signalRight = (sVal[1]-sLo[1])/(sHi[1]-sLo[1]);
  float randN = (float)random(-1000,1000)/1000.0;
  float randRotation = rotMemory[0] + 0.1*randN; // contribution from random rotation
  rotMemory[1] = randRotation;
  float rotation = (float)dir*(signalLeft-signalRight)*P + 0.3*sin(randRotation*PI)*(1-P); // superposition of chemotaxis and random motion with tuning parameter P
  float speedLeft;
  float speedRight;
  if(rotation>0){
    speedLeft = baseSpeed*(1-2*abs(rotation)); 
    speedRight = baseSpeed;
  }
  else{
    speedRight = baseSpeed*(1-2*abs(rotation));
    speedLeft = baseSpeed; 
  }
  setMotors(speedLeft*(float)dir,speedRight*(float)dir);
}

// set motor speeds to follow pheromone (dir=1) or be repelled by it (dir=-1)
void randomWalk(unsigned long deltaT, int baseSpeed, int dir, float Dr, float *rotMemory) {
  // Box-Muller transform to generate normal distribution
  float U1 = random(1,1000)/1000.0;
  float U2 = random(1,1000)/1000.0;
  float randN = sqrt(-2*log(U1))*cos(2*PI*U2);
  
  float dtheta = rotMemory[0] + sqrt(2*Dr*(float)deltaT/1000.0)*randN; // contribution from random rotation
  rotMemory[1] = dtheta;

  float speedLeft = baseSpeed + 100*sin(dtheta);
  float speedRight = baseSpeed - 100*sin(dtheta);
  
  setMotors(speedLeft*dir,speedRight*dir);
}

// fetch a detected obstacle
void fetchingRoutine(Servo myservo){
  setServo(myservo, 1);
  delay(100);
  setMotors(50,50);
  delay(1000);
  setMotors(-50,-50);
  delay(1000);
}

#endif
