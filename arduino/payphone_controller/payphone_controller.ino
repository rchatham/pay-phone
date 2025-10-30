#include <Keypad.h>

// Keypad configuration
const byte ROWS = 4;
const byte COLS = 3;
char keys[ROWS][COLS] = {
  {'1','2','3'},
  {'4','5','6'},
  {'7','8','9'},
  {'*','0','#'}
};
byte rowPins[ROWS] = {9, 8, 7, 6};
byte colPins[COLS] = {5, 4, 3};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// Hook switch pin
const int HOOK_PIN = 2;
bool lastHookState = HIGH;

void setup() {
  Serial.begin(9600);
  pinMode(HOOK_PIN, INPUT_PULLUP);
  Serial.println("READY");
}

void loop() {
  // Check keypad
  char key = keypad.getKey();
  if (key) {
    Serial.print("KEY:");
    Serial.println(key);
  }
  
  // Check hook switch
  bool hookState = digitalRead(HOOK_PIN);
  if (hookState != lastHookState) {
    Serial.print("HOOK:");
    Serial.println(hookState == LOW ? "ON" : "OFF");
    lastHookState = hookState;
  }
  
  delay(10);
}