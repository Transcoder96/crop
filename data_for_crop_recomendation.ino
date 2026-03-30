#include "DHT.h"

#define DHTPIN 2     
#define DHTTYPE DHT11
#define SOIL_PIN A0  
#define LDR_PIN A1   // Naya LDR Pin (Analog 1 par lagana)
#define RAIN_PIN 3  

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  dht.begin();
  pinMode(RAIN_PIN, INPUT);
  // Analog pins (A0, A1) ke liye pinMode ki zarurat nahi hoti
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  int m_raw = analogRead(SOIL_PIN);
  int r = (digitalRead(RAIN_PIN) == LOW) ? 1 : 0; // Rain = 1, No Rain = 0
  
  // LDR ki reading lo
  int ldr_raw = analogRead(LDR_PIN); 
  
  // LDR ki raw value (0-1023) ko 0 se 12 hours ke sunlight mein map karo
  // Note: Agar andhere mein value badh rahi ho, toh map ko (0, 1023, 12, 0) kar dena
  int sunlight_hrs = map(ldr_raw, 0, 1023, 0, 12);

  if (!isnan(h) && !isnan(t)) {
    // NAYA FORMAT: "Temp,Hum,Moist,Rain,Sunlight" (Total 5 values)
    Serial.print(t); Serial.print(",");
    Serial.print(h); Serial.print(",");
    Serial.print(m_raw); Serial.print(",");
    Serial.print(r); Serial.print(",");
    Serial.println(sunlight_hrs); // Nayi 5th value add ho gayi
  }
  delay(1000); 
}