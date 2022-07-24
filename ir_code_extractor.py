"""
Extract IR code data in "TV-B-Gone" format from captured waveform

This script reads in a waveform from a .csv file, and extracts the 
timing information as a list of on/off times, and a packed list of
sequential indices into that first list. This is the required format
for the "TV-B-Gone" Arduino project.

To use:
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

Outline of program function:

First the signal is passed through a low-pass filter, to remove the
carrier. An edge detect then gives the rising and falling edges of each
code pulse, which then gives the on/off time of each pulse with some
simple subtraction. On/off pairs that are near enough in time value
are clustered and averaged. This information is turned into a list
of the unique on/off pairs, and a list of sequential indices in that
first list. These two defines the sequence of on/off times of the IR
code. This list of indices is packed in the manner used in the TV-B-Gone
Arduino code, and everything is output to CSV. 

"""

__author__ = "Andrew Palmer"
__version__ = "0.1.0"

# stdlib imports
import sys
import csv
import os
import math
import tkinter as tk
from tkinter import ttk  # tk widgets
from tkinter import filedialog
from tkinter import Label

# 3rd party imports
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, lfilter, freqz

# local imports


# output logging levels
INFO_OUTPUT = 1  # production logging output
WARN_OUTPUT = 0  # non-critical errors
ERROR_OUTPUT = 1  # critical errors
DEV1_OUTPUT = 0  # first level debug output
DEV2_OUTPUT = 0  # second level debug output

# config values
TRIGGER_V = 1.0
START_TIME_MS = -0.01
CLUSTERING_DIVERGENCE_US = 5

# filter config
order = 3
fs = 41666666.67  # sample rate, Hz
cutoff = 15000 # desired cutoff frequency of the filter, Hz

file = "Sharp Aquos 2018 power btn.csv"

SHOW_PLOT = 0


def butter_lowpass(cutoff, fs, order=5):
    return butter(order, cutoff, fs=fs, btype='low', analog=False)

def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y

if DEV1_OUTPUT:
    print(
        sys.argv[0], ", installed python version: ", sys.version_info.major,
        '.', sys.version_info.minor, sep='')

fs = float(sys.argv[1])

if DEV1_OUTPUT:
    print("\nSample rate: ", fs, sep='')

data = []

# User will choose this location with a GUI
input_directory = None

# Close all previous plots
plt.close('all')

# This next section starts a file selection GUI
# It gets the required input data directory
root = tk.Tk()

root.title('Select CSV file to process')
root.geometry("350x200")

csv_file_button_label = tk.StringVar()

def select_csv_file():
    global csv_data_file, csv_file_button_label
    filetypes = (
        ('CSV files', '*.csv'),
        ('Text files', '*.txt')
    )

    csv_data_file = filedialog.askopenfilename(
        title="Select a CSV file to process",
        filetypes=filetypes
    )
    csv_file_button_label.set(str(csv_data_file))

def start_processing():
    if csv_data_file is not None:
        root.destroy()


select_csv_file_button = ttk.Button(
    root,
    text="Select CSV Data",
    command=select_csv_file
)

select_csv_file_button.pack(pady=(15,0))

label1 = Label(root, text="Selected CSV data file:")
label1.pack(pady=(5,0))
label2 = Label(root, textvariable=csv_file_button_label)
label2.pack(pady=(5,15))

done_button = ttk.Button(
    root,
    text="Start processing data",
    command=start_processing
)

done_button.pack(pady=(5,25))

root.mainloop()

# The output file will take the name of the CSV data, so first
# remove the rest of the path.
split = os.path.split(csv_data_file)
csv_data_basename = split[0]
csv_data_filename = split[1]

# Create the names of the output file
output_file = os.path.join(
    csv_data_basename, os.path.splitext(csv_data_filename)[0]
    + "_output.csv")

if DEV1_OUTPUT or INFO_OUTPUT:
    print("Input CSV data file: ", str(csv_data_file))
    print("Output file: ", str(output_file))


if not os.path.exists(csv_data_file):
    print("Cannot find expected CSV file: ", csv_data_file)
    input("Press the any key to exit...")
    sys.exit(1)

print("Starting data read...")
with open(csv_data_file, newline='') as csvfile:
    csvreader = csv.reader(csvfile, delimiter=',')
    for count, row in enumerate(csvreader):
        if count > 2 and float(row[0]) > START_TIME_MS:
            # numpy append is VERY slow
#            data = np.append(data, [row], axis=0)
            data.append(row)
        if count < 10 and DEV1_OUTPUT:
            print("row contents: ", row, ", data array: ", data)
        if count % 100000 == 0 and DEV2_OUTPUT:
            print("row num: ", count, ", row contents: ", row)

print("Data length: ", len(data), ", row 0: ", str(data[0]))

print("Starting conversion to numpy array...")
# we want numpy array, for the 2D slicing ("[:, 0]" notation)
data = np.array(data, dtype=np.dtype(np.float64))

print("Starting data filtration...")
# filter the data
y = butter_lowpass_filter(data[:, 1], cutoff, fs, order)

# Get the filter coefficients so we can check its frequency response.
b, a = butter_lowpass(cutoff, fs, order)

# Get the frequency response
w, h = freqz(b, a, fs=fs, worN=8000)

print("Starting thresholding...")
# Bitwise comparison of all but last items that are below threshold,
# and all but first that are above threshold. 
# This catches rising edge
mask1 = (y[:-1] < TRIGGER_V) & (y[1:] > TRIGGER_V)

# and this for the falling edge
mask2 = (y[:-1] > TRIGGER_V) & (y[1:] < TRIGGER_V)

crossings_data = mask1 | mask2

# we end up losing one data point - put it back for plotting purposes
crossings_data = np.append(crossings_data, 0)

# get on/off times
# this gives us the indices of the non-zero items
# (which now are the crossing events)
fnz = np.flatnonzero(crossings_data)

# now use these indices to get the timestamps of the crossings 
crossings_times_ms = data[:, 0][fnz]
on_off_times_ms = []
for count, time in enumerate(crossings_times_ms[1:]):
    on_off_times_ms.append(time - crossings_times_ms[count])

# at this point, the array should have an odd number of items
# this is because there will be a trailing "on" time, with no defined "off"
# time. 
odd = len(on_off_times_ms) % 2

if odd:
    print("\nArray is odd! All good")
else:
    print("\nLiterally can't even")

# fill in the trailing "off" time
on_off_times_ms.append(10)

# make it into a 2D array, with pairs of times
# each pair will thus be an on and an off time 
on_off_times_ms = np.reshape(on_off_times_ms, (-1, 2))
if DEV2_OUTPUT:
    print("\non_off_times_ms: ", on_off_times_ms)

on_off_times_10us = on_off_times_ms * 100
on_off_times_10us = on_off_times_10us.astype(int)

if DEV1_OUTPUT:
    print("\non_off_times_10us:\n", on_off_times_10us)

# cluster the on/off times
on_off_time_keys = []
for x in range(0, len(on_off_times_10us)):
    on_off_time_keys.append(0)
num_keys = 0
increment_key = 1

for i, each_pair in enumerate(on_off_times_10us):
    if DEV2_OUTPUT:
        print("this pair: ", each_pair)
    # if this pair has not already been matched
    if on_off_time_keys[i] == 0:
        num_keys += increment_key
        on_off_time_keys[i] = round(num_keys)
        potential_match_indices = []
        # look through all the keys
        for count, potential_pair in enumerate(on_off_times_10us):
            #print("potential pair: ", potential_pair)
            if (
                i != count
                and abs(each_pair[0] - potential_pair[0]) 
                    < CLUSTERING_DIVERGENCE_US 
                and abs(each_pair[1] - potential_pair[1]) 
                    < CLUSTERING_DIVERGENCE_US
                ):
                if DEV2_OUTPUT:
                    print(
                        "potential pair: ", potential_pair,
                        " matches current pair: ", each_pair)
                on_off_time_keys[count] = round(num_keys)

print("keys array: ", on_off_time_keys)

last_key = on_off_time_keys[-1]
if DEV1_OUTPUT:
    print("last key: ", last_key)

key_vals = []

# calculate the average on/off time for each key
for unique_key in range(1, last_key + 1):
    on_t_accum = 0
    off_t_accum = 0
    num_items = 0
    for count, key in enumerate(on_off_time_keys):
        if key == unique_key:
            if DEV2_OUTPUT:
                print("unique key found: ", unique_key)
            on_t_accum += on_off_times_10us[count][0]
            off_t_accum += on_off_times_10us[count][1]
            num_items += 1
    # now we have looped through all the keys and accumulated all the values
    # for this key, get the average
    key_vals.append([round(on_t_accum / num_items), round(off_t_accum / num_items)])

print("key values: ", str(key_vals))

# handle last pair
# as the IR output will stay off after the last "on" time, we don't care about
# the last "off" time. See if we can use another key.
last_on_time = key_vals[last_key-1][0]
for key_index in range(0, last_key):
    this_on_time = key_vals[key_index][0]
    if abs(last_on_time - this_on_time) < CLUSTERING_DIVERGENCE_US:
        if DEV1_OUTPUT:
            print(
                "Found a substitute for last pair. ",
                "Original last pair: ", key_vals[last_key - 1],
                ", substitute last pair: ", key_vals[key_index], sep='')
        on_off_time_keys[-1] = key_index + 1
        key_vals.pop(-1)
        break;

# we were using initialised zeros for a special purpose, but now we need
# the keys array to be zero-indexed
on_off_time_keys = [
    on_off_time_key - 1 for on_off_time_key in on_off_time_keys]

print(
    "\nfinal keys array: ", str(on_off_time_keys),
    "\nlength of final keys array: ", str(len(on_off_time_keys)),
    "\nfinal key values: ", str(key_vals))

# do some binary packing on the key values.
# probably doesn't work for bits_per_index > max_bit_shift
max_bit_shift = 8
curr_bit_shift = max_bit_shift
bits_per_index = math.ceil(last_key / 2)
num_overflow_bits = 0
byte = 0
on_off_time_keys_packed = []
for key in on_off_time_keys:
    # if we have enough space
    if curr_bit_shift - bits_per_index >= 0:
        num_overflow_bits = 0
        curr_bit_shift = curr_bit_shift - bits_per_index
        byte = byte | (key << curr_bit_shift)
        if DEV1_OUTPUT:
            print(
                "we have space, new bit shift val: ", curr_bit_shift,
                ", new byte value: ", str(byte), sep='')
    else:
        num_overflow_bits = bits_per_index - curr_bit_shift
        byte = byte | (key >> num_overflow_bits)
        if DEV1_OUTPUT:
            print(
                "no space, num overflow bits: ", num_overflow_bits,
                ", appending byte: ", str(byte), sep='')
        on_off_time_keys_packed.append([hex(byte)])
        # put the remaining bits in the newly-reset byte array
        curr_bit_shift = max_bit_shift - num_overflow_bits
        byte = ((key << curr_bit_shift) & 0xFF)

# we probably got here with the last set of packed keys in "byte" but not
# appended to ouput array
if num_overflow_bits == 0:
    if DEV1_OUTPUT:
        print("appending last byte, value: ", byte, sep='')
    on_off_time_keys_packed.append([hex(byte)])


print("packed key array: ", str(on_off_time_keys_packed))

# write output somewhere useful
header1 = ["num. pairs", "bits per index"]
data1 = [len(on_off_time_keys), bits_per_index]
header2 = ["times (x10us)"]
header3 = ["codes"]

print("Saving to file...")

with open(output_file, 'w', newline='') as csvfile:
    output_writer = csv.writer(csvfile, delimiter=',')
    output_writer.writerow(header1)
    output_writer.writerow(data1)
    output_writer.writerow(header2)
    for row in key_vals:
        output_writer.writerow(row)
    output_writer.writerow(header3)
    for row in on_off_time_keys_packed:
        output_writer.writerow(row)

if SHOW_PLOT:
    print("Starting plot...")
    fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(13, 11))
    fig.suptitle("IR Data Processing", fontsize=16)

    # make a big subplot
    gs = axs[1, 0].get_gridspec()
    # remove underlying axes - bottom row, all cols
    for ax in axs[1, 0:]:
        ax.remove()

    axbig = fig.add_subplot(gs[1, 0:])

    # Plot the filter frequency response
    axs[0,0].plot(w, np.abs(h), 'b')
    axs[0,0].plot(cutoff, 0.5*np.sqrt(2), 'ko')
    axs[0,0].axvline(cutoff, color='k')
    axs[0,0].set_xlim(0, 3.0*cutoff)
    axs[0,0].set_title("Lowpass Filter Frequency Response")
    axs[0,0].set_xlabel('Frequency [Hz]')
    axs[0,0].grid()

    # plot both the original and filtered signals.
    axbig.plot(data[:, 0], data[:, 1], 'r', label="raw data")
    axbig.plot(data[:, 0], y, 'g-', linewidth=2, label="filtered data")
    axbig.plot(data[:, 0], crossings_data, 'b', marker="o", label="crossings")
    axbig.legend(loc="upper left")
    axbig.set_xlabel("Time (sec)")
    axbig.set_ylabel("Voltage")

    plt.show()
