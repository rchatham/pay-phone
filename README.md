# pay-phone
This repository has code and circuit plans to hack a 1995 Pay Phone. https://imgur.com/gallery/ZZQrFqB

### Components
- [Raspberry Pi Zero W](https://www.adafruit.com/product/3400)
- [Audio Injector RPi Zero Sound Card](http://www.audioinjector.net/rpi-zero)
- [MakerSpot RPi Zero Docking Hub](https://www.amazon.com/MakerSpot-Stackable-Raspberry-Connector-Bluetooth/dp/B07CPQK9ND)
- [Arduino Nano](https://www.amazon.com/ELEGOO-Arduino-ATmega328P-Without-Compatible/dp/B0713XK923/ref=sr_1_5?keywords=arduino+nano&qid=1573163867&s=electronics&sr=1-5)
- [Adafruit Perma-Proto Board](https://www.amazon.com/Adafruit-Perma-Proto-Half-sized-Breadboard-PCB/dp/B00SK8QR8S/ref=sr_1_3?crid=2E5H3ZQ6V08E4&keywords=adafruit+perma-proto&qid=1573163906&s=electronics&sprefix=adafruit+perma%2Celectronics%2C165&sr=1-3)


### Connect Raspberry Pi to Arduino via serial connection
- [Raspberry Pi - Arduino Serial Communication](https://www.instructables.com/id/Raspberry-Pi-Arduino-Serial-Communication/)
- [I2C Communication between Arduino and Raspberry Pi](https://create.arduino.cc/projecthub/bmr1314/i2c-communication-between-arduino-and-raspberry-pi-1d00dd)
- [Serial Communication between Raspberry Pi & Arduino](https://classes.engineering.wustl.edu/ese205/core/index.php?title=Serial_Communication_between_Raspberry_Pi_%26_Arduino)
- [Home Automation using Raspberry Pi 2](https://create.arduino.cc/projecthub/cyborg-titanium-14/home-automation-using-raspberry-pi-2-windows-10-iot-core-784235?f=1)
- [SwiftSerial](https://github.com/yeokm1/SwiftSerial)


### Raspberry Pi Sound Stuff
- [Raspberry Pi Zero audio recording with the AudioInjector hat](https://www.richardmudhar.com/blog/2018/07/raspberry-pi-zero-audio-recording-with-the-audioinjector-hat/)
- [Sound configuration on Raspberry Pi with ALSA](http://blog.scphillips.com/posts/2013/01/sound-configuration-on-raspberry-pi-with-alsa/)
- [Raspberry Pi – Setting Up Your Audio](http://iwearshorts.com/blog/raspberry-pi-setting-up-your-audio/)
- [SoundcardTesting](https://www.alsa-project.org/main/index.php/SoundcardTesting)


### Arduino stuff
- [Arduino code for Pay Phone](https://create.arduino.cc/editor/rchatham/044c4320-8126-4371-ab3c-54f0d22aaedc)
- [sprintf function](https://arduinobasics.blogspot.com/2019/05/sprintf-function.html)


### Circuit Stuff
Speaker stuff for handset:
- [Adafruit Speaker Bonnet for Raspberry Pi](https://learn.adafruit.com/adafruit-speaker-bonnet-for-raspberry-pi)

Likely similar to microphone in handset:
- [Electret Microphone - 20Hz-20KHz Omnidirectional](https://www.adafruit.com/product/1064)
- [Electret Microphones](http://www.openmusiclabs.com/learning/sensors/electret-microphones/)

Understanding audio jacks: - Might be similar to how handset is wired up.
- [Understanding TRRS and Audio Jacks](https://www.cablechick.com.au/blog/understanding-trrs-and-audio-jacks/)

Signal Processing: - Do I have to?
- [Interpreting microphone output signal](https://dsp.stackexchange.com/questions/45117/interpreting-microphone-output-signal)

Designing an Electret microphone amplifier circuit:
- [How to Build an Elecret Microphone Circuit](http://www.learningaboutelectronics.com/Articles/Electret-microphone-circuit.php)
- IN DEPTH: [Simple electret microphone circuit](http://mynixworld.info/2017/09/01/simple-electret-microphone-circuit/)
- PCB Schematics: [Electret Microphone Amplifier Circuit](https://www.electroschematics.com/electret-microphone-amplifier-circuit/)
- [Electret condenser microphone amplifier for use in microcontroller projects](https://scienceprog.com/electret-condenser-microphone-amplifier-for-use-in-microcontroller-projects/)


### Payphone Hacking Tutorials and Project Ideas
- ['90s Payphone Boombox Hack](https://www.instructables.com/id/90s-Payphone-Boombox-Hack/)
- [PAYPHONE HACKS](https://hackaday.com/tag/payphone/)
- [My payphone runs Linux now.](https://www.jwz.org/blog/2016/01/my-payphone-runs-linux-now/)


### Phones and Parts
- [Old Phone Works](https://www.oldphoneworks.com/)
- [PayPhone.com](https://www.payphone.com)
- [Western Electric Handsets - Receivers & Transmitters](https://beatriceco.com/bti/porticus/bell/telephones-technical-handsets.html)


### Notes
**Handset conections:**
Using your multimeter set to Ohms, check the leads coming from the handset. The leads that register in kΩ (mine read 110) is the mic and the ones registering in Ω is the speaker (mine read 137). I was able to figure out which was wires were for the speaker using trial and error by using a trs cable connecting to my iphone while playing some Bo Diddley and when the yellow and black wires were touched to the speaker line and ground respectively you could hear the song playing from the headset. Alternatively if the leads register in MΩ then they don't connect.
- Speaker - Blk(GND)/Yel
- Mic - Grn/Red

UPDATE: I fried the mic in my original handset the first time I used it so I found a place I could buy replacement parts. This is the new [speaker](https://www.payphone.com/BT-R8-Receiver.html) and [microphone](https://www.payphone.com/Noise-Canceling-Microphone.html).
