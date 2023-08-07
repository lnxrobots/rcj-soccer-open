#include <ArduinoJson.h>

#define SENSOR_COUNT 16
#define MOTOR_COUNT 4

const unsigned int sensorPins[SENSOR_COUNT] = {
  A1,  A3,  A4,  A6,
  A5,  A7,  A8,  A10,
  A9,  A11, A12, A13,
  A14, A15, A0,  A2,
};

const unsigned int motorPins[MOTOR_COUNT][3] = {
  {5, 6, 7},
  {2, 3, 4},
  {28, 29, 30},
  {8, 9, 10},
};

const int builtinLedPin = LED_BUILTIN;
bool builtinLedStatus = false;

bool isConnected = false;

const unsigned int connectionTimeout = 1000;
const unsigned int sensorMessageInterval = 8;

unsigned long lastTime = 0;
unsigned long lastMessageTime = 0;
unsigned long lastSensorsMessage = 0;

unsigned long communicationLogTimeStart = 0;
unsigned long communicationLogTime = -1; 
const int LOG_COMM = 1;

const int DEBUG_SERIAL_WRITE = 0;

int motorMessageCount = 0;
int sensorMessageCount = 0;

int motorConf = 0;

int motorValues[4];
int colorSensorValues[SENSOR_COUNT] = {
  0, 0, 0, 0,
  0, 0, 0, 0,
  0, 0, 0, 0,
  0, 0, 0, 0,
};

enum MessageType
{
  NONE = -1,
  INIT, DISCONNECT, ERROR, MOTORS, SENSORS,
  SENSOR_STAT_RESET_RQ, SENSOR_STAT_RESET_RS, SENSOR_STAT_READ_RQ, SENSOR_STAT_READ_RS,
  SENSOR_LOG_READ_RQ, SENSOR_LOG_READ_RS 
};

String CreateErrorJson(const String& errorMessage)
{
  StaticJsonDocument<1024> outMessage;

  outMessage["type"] = MessageType::ERROR;
  outMessage["message"] = errorMessage;

  String outString = "";

  serializeJson(outMessage, outString);

  return outString;
}

void SetMotor(int m, int v)
{
  bool polarity = v >= 0;
  analogWrite(motorPins[m][0], abs(v));
  digitalWrite(motorPins[m][1], !polarity);
  digitalWrite(motorPins[m][2], polarity);
}

void SetMotors(int v1, int v2, int v3, int v4)
{
  if (motorConf == 2){
    SetMotor(1, -v1);
    SetMotor(2, -v2);
    SetMotor(3, -v3);
    SetMotor(0, -v4);  
  } else {
    SetMotor(0, v1);
    SetMotor(1, v2);
    SetMotor(2, v3);
    SetMotor(3, v4);
  }
}

String readSerialData;
const int READ_BUFFER_SIZE = 1024;
char readSerialBuffer[READ_BUFFER_SIZE];
int readSerialLength = 0;
int readSerialError = 0;
bool firstCharacter = false;

int ReadSerial(){
  while(1){
    int data = Serial1.read();
    if (data < 0){
      break;
    }
    
    if (!firstCharacter)
    {
      if (data == '{')
      {
        firstCharacter = true;
        readSerialBuffer[readSerialLength++] = char(data);
      }
    }

    else
    {
      if (data == '\n'){
        if(readSerialError == 1){
          readSerialError = 0;
          readSerialLength = 0;
          break;
        }
        readSerialBuffer[readSerialLength] = 0;
        readSerialData = String(readSerialBuffer);
        readSerialLength = 0;
        firstCharacter = false;
        return 1;
      } else {
        if(readSerialError == 0){
          readSerialBuffer[readSerialLength++] = char(data);
          if(readSerialLength >= READ_BUFFER_SIZE){
            readSerialError = 1;
          }
        }
      }
    }
  }
  return 0;
}

const int WRITE_BUFFER_SIZE = 1024*8;
const int SEND_BUFFER_SIZE = 32;
char serialWriteBuffer[WRITE_BUFFER_SIZE];
int serialWriteLength = 0;

int SerialWrite(String data){
  int n = data.length();
  if(serialWriteLength + n >= WRITE_BUFFER_SIZE){
    return -1; 
  }
  strcpy(&serialWriteBuffer[serialWriteLength], data.c_str());
  serialWriteLength += n;
  return 0;
}

int SerialWriteln(String data){
  int n = data.length();
  if(serialWriteLength + (n + 1) >= WRITE_BUFFER_SIZE){
    return -1; 
  }
  if(SerialWrite(data) < 0){
    return -1;
  }
  serialWriteBuffer[serialWriteLength++] = '\n';
  return 0;
}

int SerialSendBuffer(){
  while(1){
    if(serialWriteLength <= 0){
      return 0;
    }
    int n = serialWriteLength;
    if(n > SEND_BUFFER_SIZE){
      n = SEND_BUFFER_SIZE;
    }
    if(Serial1.availableForWrite() < n){
      return 0;
    }
    Serial1.write(serialWriteBuffer, n);
    serialWriteLength -= n;
    memcpy(serialWriteBuffer, &serialWriteBuffer[n], serialWriteLength);
  }
  return 0;
}

void OnStart()
{
  Serial.begin(9600);
  Serial1.begin(115200);
  //Serial.print("Serial1.availableForWrite(): ");
  //Serial.println(Serial1.availableForWrite());
  
  pinMode(builtinLedPin, OUTPUT);

  for (int i = 0; i < SENSOR_COUNT; i++)
  {
    pinMode(sensorPins[i], INPUT);
  }

  for (int m = 0; m < MOTOR_COUNT; m++)
  {
    for (int p = 0; p < 3; p++)
    {
      pinMode(motorPins[m][p], OUTPUT);
    }
  }

  digitalWrite(builtinLedPin, LOW);
}

void OnConnect(StaticJsonDocument<256> message)
{
  if(DEBUG_SERIAL_WRITE == 1){
    Serial.println("Init message received");
  }
  isConnected = true;

  if (message.containsKey("mc")){
    motorConf = message["mc"];
  } else {
    motorConf = 0;
  }

  builtinLedStatus = false;
  digitalWrite(builtinLedPin, builtinLedStatus);

  lastMessageTime = millis();
}

void OnUpdate()
{
  for (unsigned int i = 0; i < SENSOR_COUNT; i++)
  { 
    int sensorValue = analogRead(sensorPins[i]);
    SensorStatUpdate(i, sensorValue);
    if (sensorValue > colorSensorValues[i])
      colorSensorValues[i] = sensorValue;
  }

  unsigned long currentTime = millis();
  if (currentTime - lastTime >= 1000)
  {
    lastTime = currentTime;

    //Serial.println(motorMessageCount);
    //Serial.println(sensorMessageCount);

    motorMessageCount = 0;
    sensorMessageCount = 0;
  }

  if (currentTime - lastMessageTime >= connectionTimeout)
  {
    if(DEBUG_SERIAL_WRITE == 1){
      Serial.println("Connection timeout");
    }
    SerialWriteln(CreateErrorJson("Connection timeout"));

    OnDisconnect();
    isConnected = false;
  }


  if (currentTime - lastSensorsMessage >= sensorMessageInterval)
  {
    int n = serialWriteLength;

    lastSensorsMessage = currentTime;

    sensorMessageCount++;

    StaticJsonDocument<512> sensorValuesMessage;
    sensorValuesMessage["type"] = MessageType::SENSORS;

    JsonArray valuesArray = sensorValuesMessage.createNestedArray("v");

    for(unsigned int i = 0; i < SENSOR_COUNT; i++)
      valuesArray.add(colorSensorValues[i]);

    String outString = "";
    serializeJson(sensorValuesMessage, outString);

    //Serial1.println(outString);
    SerialWriteln(outString);
    
    for (unsigned int i = 0; i < SENSOR_COUNT; i++)
      colorSensorValues[i] = 0;
    
    if(n <= 0){ // assuming write buffer was empty 
      SensorsLogSend();
    }
  }
}

void OnMessage(MessageType messageType, StaticJsonDocument<256> message)
{
  switch (messageType)
  {
  case MessageType::INIT:
    break;

  case MessageType::DISCONNECT:
    OnDisconnect();
    isConnected = false;

    break;

  case MessageType::ERROR:
    break;

  case MessageType::MOTORS:
    {
      lastMessageTime = millis();

      motorMessageCount++;

      JsonArray motorValuesJson = message["v"].as<JsonArray>();

      int checksum = message["cs"];

      if (motorValuesJson[0].as<int>() + motorValuesJson[1].as<int>() + motorValuesJson[2].as<int>() + motorValuesJson[3].as<int>() != checksum)
      {
        SerialWriteln(CreateErrorJson("Checksum verification failed in motor packet"));
        return;
      }

      int mv1 = motorValuesJson[0];
      int mv2 = motorValuesJson[1];
      int mv3 = motorValuesJson[2];
      int mv4 = motorValuesJson[3];
      SetMotors(mv1, mv2, mv3, mv4);
    }

    break;

  case MessageType::SENSORS:
    break;

  case MessageType::SENSOR_STAT_RESET_RQ:
    SensorStatReset();
    break;
    
  case MessageType::SENSOR_STAT_READ_RQ:
    SensorStatGet();
    break;
  
  case MessageType::SENSOR_LOG_READ_RQ:
    SensorsLogGet(message);
    break;

  default:
    break;
  }
}

void OnDisconnect()
{
  if(DEBUG_SERIAL_WRITE == 1){
    Serial.println("Disconnected");
  }
  SetMotors(0, 0, 0, 0);
}
////////////////////////////////////////////////////////////
int sensorStatsMin[SENSOR_COUNT];
int sensorStatsMax[SENSOR_COUNT];
long sensorStatsSum[SENSOR_COUNT];
// histogram for each 1000/16 =cca64 values interval from ir sensors
const int HISTOGRAM_INTERVALS = 16; // 1000/64 = cca16
const int HISTOGRAM_INTERVALS_SHIFT = 6; // 2^6 = 64
const int HISTOGRAM_INTERVALS_MIN = 0;
const int HISTOGRAM_INTERVALS_MAX = 1023;

long sensorStatsHistogram[SENSOR_COUNT][HISTOGRAM_INTERVALS];
int sensorStatsUpdate = 0;

const int LOG_HISTORY = 6144;
const int LOG_SEND_MAX = 256;
const int SENSOR_LOG_ID_TIME = 90;
short sensorLog[SENSOR_COUNT][LOG_HISTORY];
int sensorLogPtrWrite = 0;
int sensorLogPtrRead = 0;
unsigned long sensorLogTimeStart = 0; 
int sensorLogTime[LOG_HISTORY];
int sensorLogReadDataId = -1;
int sensorLogReadDataFrom = 0;
int sensorLogReadDataCount = 0;
int sensorLogReadDataSent = 0;

void SensorStatUpdate(int sensorId, int sensorVal){
  if (!sensorStatsUpdate) return;
  
  if (sensorStatsMin[sensorId] > sensorVal){
    sensorStatsMin[sensorId] = sensorVal;
  }
  if (sensorStatsMax[sensorId] < sensorVal){
    sensorStatsMax[sensorId] = sensorVal;
  }

  sensorStatsSum[sensorId] += sensorVal;
  
  if(sensorVal < HISTOGRAM_INTERVALS_MIN){
    sensorStatsHistogram[sensorId][0]++;  
  }else
  if(sensorVal > HISTOGRAM_INTERVALS_MAX){
    sensorStatsHistogram[sensorId][HISTOGRAM_INTERVALS-1]++;
  } else {
    sensorStatsHistogram[sensorId][sensorVal>>HISTOGRAM_INTERVALS_SHIFT]++;
  }

  if (sensorId == 0) {
    if (LOG_COMM == 1)
    {
      communicationLogTime = micros() - communicationLogTimeStart;
      communicationLogTimeStart = micros();
      sensorLogTime[sensorLogPtrWrite] = communicationLogTime;
      communicationLogTime = -1;
    } else {
      sensorLogTime[sensorLogPtrWrite] = millis() - sensorLogTimeStart;
    } 
  }
  sensorLog[sensorId][sensorLogPtrWrite] = sensorVal;
   
  if (sensorId == SENSOR_COUNT-1)
  {
    if(sensorLogPtrWrite < LOG_HISTORY){
      sensorLogPtrWrite++; 
    } else {
      sensorLogPtrWrite = 0; 
    }

    if(sensorLogPtrWrite == sensorLogPtrRead){
      if(sensorLogPtrRead < LOG_HISTORY){
        sensorLogPtrRead++;
      } else {
        sensorLogPtrRead = 0; 
      }
    }
  }
}

void SensorStatReset(){
  sensorStatsUpdate = 1;
  
  for(int i = 0; i < SENSOR_COUNT; i++){
    sensorStatsMin[i] = 9999;
    sensorStatsMax[i] = -1;

    sensorStatsSum[i] = 0;
    
    for(int j = 0; j < HISTOGRAM_INTERVALS; j++){
      sensorStatsHistogram[i][j] = 0;
    }    
  }
  
  sensorLogPtrRead = 0;
  sensorLogPtrWrite = 0;
  sensorLogTimeStart = millis();

  sensorLogReadDataId = -1;
  sensorLogReadDataFrom = 0;
  sensorLogReadDataCount = 0;
  sensorLogReadDataSent = 0;

  communicationLogTimeStart = micros();

  StaticJsonDocument<128> sensorStatsResetMessage;

  sensorStatsResetMessage["type"] = MessageType::SENSOR_STAT_RESET_RS;
  sensorStatsResetMessage["result"] = "OK";

  String outString = "";
  serializeJson(sensorStatsResetMessage, outString);
  
  SerialWriteln(outString);
}

void SensorStatGet(){
  sensorStatsUpdate = 0;

  StaticJsonDocument<4096> sensorStatsValueMessage; 
  sensorStatsValueMessage["type"] = MessageType::SENSOR_STAT_READ_RS;
  sensorStatsValueMessage["result"] = "OK";

  JsonArray valuesMinArray = sensorStatsValueMessage.createNestedArray("v");
  JsonArray valuesMaxArray = sensorStatsValueMessage.createNestedArray("u");
  JsonArray valuesAvgArray = sensorStatsValueMessage.createNestedArray("w");


  for(unsigned int i = 0; i < SENSOR_COUNT; i++){
    valuesMinArray.add(sensorStatsMin[i]);
    valuesMaxArray.add(sensorStatsMax[i]);
  }
  
  JsonArray valuesArray = sensorStatsValueMessage.createNestedArray("h");
  for(unsigned int i = 0; i < SENSOR_COUNT; i++){
    long sum = 0;
    for (unsigned int j = 0; j < HISTOGRAM_INTERVALS; j++){
      sum += sensorStatsHistogram[i][j];
    }
    
    if (i == 0){
      sensorStatsValueMessage["count"] = sum;
    }
    if (sum > 0){  
      valuesAvgArray.add(int(sensorStatsSum[i]/sum));
      for (unsigned int j = 0; j < HISTOGRAM_INTERVALS/2; j++){
        // x is rounded up percentage of 2 Histogram values, so it would be easier to understand
        long y = sensorStatsHistogram[i][2*j] + sensorStatsHistogram[i][2*j+1];
        int x = double(y) / sum * 10000;
        x = (x + 5) / 10;
        if(x <= 0 && y > 0){
          x = 1;
        }
        valuesArray.add(x);  
      }
    } else {
      valuesAvgArray.add(-1);
    }
    
  }

  String outString = "";
  serializeJson(sensorStatsValueMessage, outString);
  
  SerialWriteln(outString);
}

void SensorsLogGet(StaticJsonDocument<256> message){
  sensorLogReadDataId = message["id"];
  sensorLogReadDataFrom = message["f"];
  sensorLogReadDataCount = message["c"];
  sensorLogReadDataSent = 0;

}

void SensorsLogSend(){
  if (sensorLogReadDataId < 0) return;

  StaticJsonDocument<6144> sensorsLogMessage; 
  sensorsLogMessage["type"] = MessageType::SENSOR_LOG_READ_RS;
  sensorsLogMessage["result"] = "OK";
  sensorsLogMessage["id"] = sensorLogReadDataId;
  sensorsLogMessage["f"] = sensorLogReadDataFrom + sensorLogReadDataSent;
  
  int x = sensorLogPtrWrite - sensorLogPtrRead;
  if (x < 0) x += LOG_HISTORY;
  sensorsLogMessage["s"] = x;

  int cnt = x - (sensorLogReadDataFrom + sensorLogReadDataSent);
  if(cnt < 0) cnt = 0;
  if(cnt > sensorLogReadDataCount - sensorLogReadDataSent) cnt = sensorLogReadDataCount - sensorLogReadDataSent;
  if(cnt > LOG_SEND_MAX) cnt = LOG_SEND_MAX;

  JsonArray valuesLogArray = sensorsLogMessage.createNestedArray("v");

  int ptr = sensorLogPtrRead + (sensorLogReadDataFrom + sensorLogReadDataSent);
  if (ptr > LOG_HISTORY) ptr -= LOG_HISTORY;  
  for(int i = 0; i < cnt; i++){
    if (sensorLogReadDataId == SENSOR_LOG_ID_TIME){
      valuesLogArray.add(sensorLogTime[ptr]);
    } else {
      valuesLogArray.add(sensorLog[sensorLogReadDataId][ptr]);
    }
    ptr++;
    if (ptr > LOG_HISTORY) ptr -= LOG_HISTORY;  
  }
  
  sensorLogReadDataSent += cnt;
  if(cnt == 0 || sensorLogReadDataSent >= sensorLogReadDataCount) sensorLogReadDataId = -1;

  String outString = "";
  serializeJson(sensorsLogMessage, outString);
  
  SerialWriteln(outString);
}


///////////////////////////////////////////////////////////



void setup()
{
  OnStart();
}

void loop()
{
  SerialSendBuffer();
  
  // If there is a new message available ...
  if (Serial1.available() > 0)
  {
    // Read input JSON
    //communicationLogTimeStart = micros();
    //String data = Serial1.readStringUntil('\n');
    int result = ReadSerial();
    //communicationLogTime = micros() - communicationLogTimeStart;
    if (result == 1){
      //communicationLogTimeStart = micros();
      StaticJsonDocument<256> message;
      DeserializationError err = deserializeJson(message, readSerialData);
      //communicationLogTime = micros() - communicationLogTimeStart;
  
      // Check for error in message deserialization
      if (err)
      {
        if(DEBUG_SERIAL_WRITE == 1){
          Serial.print(F("Deserialization failed: "));
          Serial.println(err.c_str());
        }
        message.clear();
  
        SerialWriteln(CreateErrorJson(err.c_str()));
      }
      else
      {
        int messageType = (message["type"] | -1);
  
        if (isConnected)
        {
          //communicationLogTimeStart = micros();
          OnMessage((MessageType)messageType, message);
          //communicationLogTime = micros() - communicationLogTimeStart;
        }
        else
        {
          if (messageType == MessageType::INIT)
          {
            OnConnect(message);
          }
        }
      } 
    }
  }

  if (isConnected)
  {
    OnUpdate();
  }
  else
  {
    // Blink builtin LED to indicate that there is no device connected
    unsigned long currentTime = millis();

    if (currentTime - lastTime >= 1000)
    {
      lastTime = currentTime;
      builtinLedStatus = !builtinLedStatus;
      digitalWrite(builtinLedPin, builtinLedStatus);
    }
  }
}
