Translation:

Teams

The project assignment is done in teams of two students.

Standard project activities

The project assignment aims to implement smart home devices. The house plan is given in the image:

The smart home system contains three Raspberry Pi devices, which are connected to different sensors and actuators. The list of sensors and actuators is given in the table:

| PI  | Code  | Name                                    |
| --- | ----- | --------------------------------------- |
| PI1 | DS1   | Door Sensor (Button)                    |
| PI1 | DL    | Door Light (LED diode)                  |
| PI1 | DUS1  | Door Ultrasonic Sensor                  |
| PI1 | DB    | Door Buzzer                             |
| PI1 | DPIR1 | Door Motion Sensor                      |
| PI1 | DMS   | Door Membrane Switch                    |
| PI1 | WEBC  | Door Web Camera                         |
| PI2 | DS2   | Door sensor (Button)                    |
| PI2 | DUS2  | Door Ultrasonic Sensor                  |
| PI2 | DPIR2 | Door Motion Sensor                      |
| PI2 | 4SD   | Kitchen 4 Digit 7 Segment Display Timer |
| PI2 | BTN   | Kitchen Button                          |
| PI2 | DHT3  | Kitchen DHT                             |
| PI2 | GSG   | Gyroscope                               |
| PI3 | DHT1  | Bedroom DHT                             |
| PI3 | DHT2  | Master Bedroom DHT                      |
| PI3 | IR    | Bedroom Infrared                        |
| PI3 | BRGB  | Bedroom RGB                             |
| PI3 | LCD   | Living room Display                     |
| PI3 | DPIR3 | Living Room Motion Sensor               |

Checkpoint 1

For the first checkpoint, it is necessary to implement a script that runs on the PI1 device. Enable configuration of the script so that any device can, or does not have to, be simulated.

Input data from each sensor must be printed in the console.

Enable control of actuators from the Raspberry Pi device through a console application.

It is not necessary to implement the Web camera.

Checkpoint 2

For the second checkpoint, it is necessary to extend the script that runs on the PI1 device, which was implemented for KT1. Extend the configuration of the script so that it contains additional information about which PI it runs on and what the name of the device is. This is the minimum; you can add any number of additional configurable pieces of information about the device, as long as it makes sense. The logic must be extended with sending measured/simulated values via the MQTT protocol to a specific topic. The topic can be configurable from the settings file or can be hardcoded for each sensor type. When sending, specify through a tag whether the sent value is simulated or not. It is mandatory for the measured values to be sent in batches through a daemon thread. It can also be done from a separate process for anyone who wants to try 🙂. The daemon thread/process can be implemented generically, meaning one thread/process for all sensors, or it can be implemented so that you have one daemon thread for each sensor type. Whoever uses a process must implement it generically because otherwise it makes no sense. In order to receive all points for KT2, it is necessary for the script to be implemented so that it does not enter a deadlock, and so that the parts of code locked with mutexes are minimal. It is necessary to implement a server — we recommend the Flask library, but you can use anything you want — which will retrieve messages from the MQTT broker and store them in an InfluxDB database. When modeling the database, it is possible to store everything in one bucket if that is easier for you, but you can also divide records by buckets in any way you want. It is necessary to enable visualization of sensor data and actuator activations in the Grafana tool. Each sensor type must have its own display panel. It is not necessary to implement the web camera.

Project defense

Implement scripts that run on all three PI devices. Enable configuration of the scripts so that any device — PI, sensor, actuator — can, or does not have to, be simulated.

Implement a server application that will receive data from PI devices via the MQTT protocol and store it in an InfluxDB database. Enable visualization of all data through the Grafana tool.

In other words, implement the requirements from KT1 and KT2 for all devices.

Implement a user Web application in any technology. The application should have the ability to display data from the Grafana tool, as well as display the current state of each element of the system.

Implement logic based on sensor input:

ALARM — represents the state of alarm in the facility. During this state, DB must be turned on. Events of entering and exiting this state must be stored in the database and displayed through the Grafana tool, as well as notify the user through the Web application. This state is exited by entering the PIN on the DMS, or through the Web application.

When DPIR1 detects motion, turn on DL1 for 10 seconds.

When DPIR1 detects motion, based on the distance detected by DUS1 in the previous few seconds, determine whether the person is entering or leaving the facility.

Apply the same logic to DPIR2 and DUS2.

Store the numerical count of people in the facility.

If a signal from DS1 or DS2 is detected for longer than 5 seconds, turn on ALARM until the DS state changes. This simulates an unlocked door.

Enable activation of the security alarm through the DMS component.

When a four-digit PIN code is entered, the system activates after 10 seconds.

If the system is active, after a detected signal on the DS1 or DS2 sensor, turn on ALARM if a correctly entered PIN is not detected on the DMS component.

By entering the PIN, ALARM is turned off and the system is deactivated.

If the numerical count of people in the facility according to point 2 is equal to zero — if there are no people in the facility — detecting motion on any of the RPIR1-3 sensors turns on ALARM.

If GSG, which is attached to the slava icon, detects significant movement, turn on ALARM.

Display temperature and air humidity from DHT1-3 on the LCD, so that the display from different DHTs alternates every few seconds.

Enable kitchen stopwatch settings.

Enable the stopwatch time to be set through the Web application. Display the time on the 4SD component.

Enable adding N seconds to the stopwatch by pressing the button (BTN). N is the number of seconds configured through the web application.

When the stopwatch time expires, 4SD must blink with 00:00 on the display. Pressing the button (BTN) stops the blinking.

Enable turning on, turning off, and controlling the colors of the BRGB light bulb through the remote control and IR sensor, as well as through the Web application.

Display video from the web camera in the web application.

Implement the listed logic in any way you choose.

During project defenses, for the maximum grade it is necessary to connect the required sensors and/or actuators to the PI device and demonstrate their operation in the system, where the remaining sensors/actuators will be simulated. For implementing this, students have 30 minutes, and all materials from the course and internet access are available. TAKE CARE that your script can be executed on the PI device — if you use any tools and libraries that were not used in the practical classes, you have no guarantee that they will be available on the PI device in the classroom.

If students do not have the complete functionalities from KT1 and KT2 implemented, they automatically receive 0 points on the project defense.

It is necessary to clearly demonstrate all functionalities within 15 minutes. All functionalities that are not demonstrated within this time frame will not be graded. It is recommended to enable a way for alarms for each functionality to be turned off when needed so that the demonstration is clear, as well as to implement scenarios that can be triggered manually for each functionality.

Project defense

Implement all requirements from the specification. Demonstrate the operation of the entire system.

Local defence scope for this repository:

- The implementation is validated as a single Raspberry Pi runtime, not as three separate scripts running on three separate PI devices.
- `settings.json` is the single source of truth for whether each device is simulated. Docker and the real Raspberry Pi runtime both load this same file; there is no Docker-specific simulation settings file.
- The Docker `iot-app` Linux container is used as a Linux/Raspberry-Pi-like runtime. It executes the same `settings.json` configuration as the PI runtime, with Docker-only network endpoint overrides for Mosquitto and InfluxDB.
- The Docker GPIO/I2C smoke test can still be used to prove unsimulated GPIO/I2C code paths import, initialize, run, and log hardware operations without crashing when no physical Raspberry Pi or protoboard devices are connected.
- Real sensor readings are not expected inside Docker. Timing-sensitive sensors such as DHT and ultrasonic sensors may log timeout/error values in the Docker compatibility run because no real hardware signal exists. This is acceptable for the Docker test as long as the GPIO-backed code path executes.
