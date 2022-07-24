# TV-B-Gone_Code-Extractor
Exctracts IR code information for TV-B-Gone Arduino project

This script reads in a waveform from a .csv file, and extracts the 
timing information as a list of on/off times, and a packed list of
sequential indices into that first list. This is the required format
for the "TV-B-Gone" Arduino project.

## To use:
1. Record the output of the IR LED on your remote when the power button
is pressed. One way to do this is to solder a wire to each leg of the 
LED, and use a Picoscope (set to "trigger once", and with sufficient
timebase to capture the entire code in one screen) to record the 
waveform when the Power Button is pressed. This can then be saved as a
.csv. In any case, this script expects a .csv, with data starting on 
row 4, and with the first column containing timestamps in milliseconds,
and the second containing voltage values. 
2. You will need to manually measure the carrier frequency of the IR
signal (if present) - it is typically around 30kHz. This value is put
into the "freq_to_timerval" element of the IrCode struct in the Arduino
code.
3. You will also need to make a note of the sample rate of your
measurement. This can be done by doing "=1000/A5 - A4" in the .csv
4. Run the script, providing the sample rate as the first argument. 
Eg:
python ir_code_extractor.py 5000000
5. The output will be saved in a .csv, which will have the same name
as the input csv with "_output" appended.

6. Enjoy!

7. If necessary, the values "TRIGGER_V" and "START_TIME_MS" below can be
tweaked to match the recorded dataset.
