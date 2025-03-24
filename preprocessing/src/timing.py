# timing.py
# imported as a module to calculate time to execute code

import time
from rich import print

# global variable to store the start time
start_time = None

# function to start measure time
def start():
    global start_time
    start_time = time.time()

# function to finish measure time
def stop():
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[green] Elapsed time: {elapsed_time:.2f} seconds! [/green] :white_check_mark:")
