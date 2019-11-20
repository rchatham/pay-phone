/*
Arduino code to interpret the analog signal from the keypad and phone receiver and send serial messages indicating changes to their state.
*/
char* current = "";
int hasPrinted = 0;
char data[100] = {0};
int a = 0; 
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
  } else if (a0 > 10) {
    
    char* last = current;
  
    if (a1 < 10 && a2 < 10) { // Use 10 as threshold to avoid noise
      
      if (a0 > 500) {
        current = "1";
      } else if (a0 > 320 && a0 < 350) {
        current = "4";
      } else if (a0 > 245 && a0 < 260) {
        current = "7";
      } else if (a0 > 190 && a0 < 210) {
        current = "*";
      }
    } else if (a1 >= 10) {
      
      if (a0 > 390) {
        current = "2";
      } else if (a0 > 260 && a0 < 280) {
        current = "5";
      } else if (a0 > 190 && a0 < 210) {
        current = "8";
      } else if (a0 > 150 && a0 < 170) {
        current = "0";
      }
    } else if (a2 >= 10) {
      
      if (a0 > 390) {
        current = "3";
      } else if (a0 > 260 && a0 < 280) {
        current = "6";
      } else if (a0 > 190 && a0 < 210) {
        current = "9";
      } else if (a0 > 150 && a0 < 170) {
        current = "#";
      }
    }
  
    if (current == last && last != "" && hasPrinted == 0) {
      
      // sprintf(data, "%hd %hd %hd", a0, a1, a2);
      // Serial.println(data);
      
      sprintf(data, "%s", current);
      Serial.println(data);
      hasPrinted = 1;
      delay(250);
    } else {
      delay(50);
    }
  
  } else if (current != "" && a0 <= 10) {
    current = "";
    hasPrinted = 0;
    delay(50);
  }

}
