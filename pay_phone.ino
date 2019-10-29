/*
Arduino code to interpret the analog signal from the keypad and phone receiver and send serial messages indicating changes to their state.
*/
char* current = "";
char data[100] = {0};
int switchState = 0;

void setup() {
  pinMode(13, INPUT);
  
  Serial.begin(9600);              //Starting serial communication
}
  
void loop() {           
  
  int a0 = analogRead(A0);
  int a1 = analogRead(A1);
  int a2 = analogRead(A2);
  
  // sprintf(data, "%hd %hd %hd", a0, a1, a2);
  // Serial.println(data);
  
  if (switchState != digitalRead(13)) {
    switchState = digitalRead(13);
    
    if (switchState == HIGH) {
      sprintf(data, "ACTIVE");
    } else {
      sprintf(data, "INACTIVE");
      delay(1000);
    }
    Serial.println(data);
  }
  
  if (switchState == LOW) {
    // ignore
  } else if (a0 > 10 && current == "") {
    
    char* last = current;
  
    if (a1 < 10 && a2 < 10) { // Use 10 as threshold to avoid noise
      
      if (a0 > 493) {
        current = "1";
      } else if (a0 > 419) {
        current = "4";
      } else if (a0 > 347) {
        current = "7";
      } else if (a0 > 335) {
        current = "*";
      }
    } else if (a1 >= 10) {
      
      if (a0 > 390) {
        current = "2";
      } else if (a0 > 331) {
        current = "5";
      } else if (a0 > 275) {
        current = "8";
      } else if (a0 > 260) {
        current = "0";
      }
    } else if (a2 >= 10) {
      
      if (a0 > 390) {
        current = "3";
      } else if (a0 > 331) {
        current = "6";
      } else if (a0 > 275) {
        current = "9";
      } else if (a0 > 260) {
        current = "#";
      }
    }
  
    if (current != last && last == "") {
      
      // sprintf(data, "%hd %hd %hd", a0, a1, a2);
      // Serial.println(data);
      
      sprintf(data, "%s", current);
      Serial.println(data);
      delay(250);
    } else {
      delay(50);
    }
  
  } else if (current != "" && a0 == 0) {
    current = "";
    delay(50);
  }

}
