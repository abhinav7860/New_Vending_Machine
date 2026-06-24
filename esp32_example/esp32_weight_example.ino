// Simple ESP32 example to send simulated weight values over Serial
// Replace simulatedWeight() with real sensor read code (HX711, etc.)
void setup() {
  Serial.begin(115200);
}

long lastMillis = 0;

void loop() {
  if (millis() - lastMillis > 1000) {
    lastMillis = millis();
    float w = simulatedWeight();
    Serial.println(w); // send one numeric value per line
  }
}

float simulatedWeight() {
  // a simple simulated changing weight between 100 and 200 grams
  static float t = 0;
  t += 0.3;
  return 150.0 + 50.0 * sin(t);
}