/************************************************************************** 
************************************************************************** 
Rant main control
************************************************************************** 
************************************************************************** */

#include <Servo.h>
#include <math.h>
#include "customized_routines/routines_rant5.h" // select correct rant number
#include "common_routines.h"

// global variables
  // preallocation
Servo myservo;  // create servo object to control a servo
float sensorValues[2]={0,0}; // light sensor array. entry 1: left, entry 2: right
float bumpSensor[2]={0,0}; // bump sensor array. first entry sensor value, second entry empty
int dir = 1; // variable encoding attractive (1) or repelling (-1) behavior
bool servoState = 0; // state of magnet. 1 engaged, 0 disengaged.
float rotMemory[2]={0,0}; // array storing previous random rotation
unsigned long timer = 0;
unsigned long prevTime = 0;
template <typename T> int sgn(T val) { // sign function template
    return (T(0) < val) - (val < T(0));
}

  // sampling parameters
  int bumpSensorSamples = 50; // number of samples for averaging of bump sensor signal
  int sensorSamples = 200; // number of samples for averaging of light sensor signal

  // system parameters
    // advection
    int baseSpeed = 80; // base speed of rant out of 255

    // diffusion
    int diffusionSpeed = 50; // diffusion speed out of 255
    float rwStep = 20;
    
    // gradient descent
    float G = 0.01 * 5.0/4.0; // rotational gain
    //float G = 0.24;
    int v0 = 4; // speed in cm/s from 2 to 18 cm/s
    float ls = 0.01; // light sensor distance [m]
    float lw = 0.03; // distance between wheels [m]
        
    // collective construction
    float P = 0; // Cooperation parameter. P=0 fully random taxis, P=1 only chemotaxis.
    float pheromoneThresholdHi = 600; // light sensor value pick-up threshold (only picks up above this value multiplied by P)
    float pheromoneThresholdLo = 250; //150
    float pheromoneThresholdBndry = 80;
    float phDiff = (pheromoneThresholdHi-pheromoneThresholdLo)/2;
    float phMean = (pheromoneThresholdHi+pheromoneThresholdLo)/2;
    int ks = -1; // -1 construction, 1 de-construction

    // hacks
    unsigned long timeOut = 5000;

void setup() {
  myservo.attach(13);  // attaches the servo on pin 9 to the servo object
  setServo(myservo, servoState);
  randomSeed(analogRead(A2)); // pick initial seed from (roughly) random analog signal on light sensor
  Serial.begin(9600);
  v0 = 40 + (255-40)/(18-2)*(v0-2); // metric conversion to arduino-specific speed range
  int calibrationThreshold = 100;
  //calibration(calibrationThreshold, sensorSamples, sensorLow, sensorHigh, sensorValues, myservo); // initial calibration of sensors
}

/************************************************************************** 
************************************************************************** 
Main Loop
************************************************************************** 
************************************************************************** */

void loop() {
  
  getPheromoneReading(sensorValues, sensorSamples);
  
  // gradient descent
  gradientDescent(sensorLow, sensorHigh, sensorSamples, dir, v0, G, ls, lw, ks, speedCorrection, P, rotMemory);
  rotMemory[0] = rotMemory[1]; // update random walk memory

   // Obstacle avoidance
  checkBumpSensor(bumpSensor,bumpSensorSamples);
  float svMean = (sensorValues[0]+sensorValues[1])/2;

  if(dir==-1 && svMean<pheromoneThresholdBndry){
    if(millis()-timer>timeOut){ // wait after pick-up before avoiding boundary
      int randTurnSign = sgn(random(-1000,1000));
      setMotors(50, 50);
      delay(500);
      setMotors(-55*randTurnSign, 55*randTurnSign);
      delay(1500);
    }
  }
  else if(dir==1 && bumpSensor[0]<detectionThreshold){
    if(ks*svMean*P>ks*(phMean+ks*phDiff)){
      fetchingRoutine(myservo);
      servoState = 1;
      dir = -1; // reverse motion 
      timer = millis();
    }
    else{
      int randTurn = random(20,100);
      int randTurnSign = sgn(random(-1000,1000));
      setMotors(-randTurn*randTurnSign, randTurn*randTurnSign);
      delay(500);
    }
  }

  // if not carrying obstacle, return to forward motion
  checkBumpSensor(bumpSensor,bumpSensorSamples);
  if(bumpSensor[0]>detectionThreshold){
      dir = 1;
    if(servoState!=0){
      setServo(myservo, 0);
      delay(200);
      servoState = 0;
    }
  }

  // drop obstacle
  if(dir==-1 && ks*svMean<P*ks*(phMean-ks*phDiff)){
    int randTurnSign = sgn(random(-1000,1000));
    int randTurn = random(50,100);
    setMotors(50, 50);
    delay(500);
    setMotors(-55*randTurnSign, 55*randTurnSign);
    delay(1500);
    setServo(myservo, 0);
    setMotors(0, 0);
    servoState = 0;
    delay(2000); // pause after dropping
    setMotors(randTurn*randTurnSign, -randTurn*randTurnSign);
    delay(750);
    dir = 1;
  }

//  Serial.print(sensorValues[0]);
//  Serial.print(" ");
//  Serial.println(sensorValues[1]);
}
