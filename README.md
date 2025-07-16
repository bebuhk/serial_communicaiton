# Serial Communication

!work in progress!

This repository contains python script that allow to connect to multiple serial devices (such as vaisala CO2 sensors) and store their measurement data to a single csv-file. It is developed for laboratory setups with multiple sensors and actors.

tested on cw-pc.


## workflow

1. (if sensors are not yet sending data): use seial_communication.py to iniate the communication and set the sensors to run (>r). This step can also be done with Putty.

2. use serial_communication_GUI.py to log the co2 sensors output and live-plot the data.