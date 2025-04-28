import time
from rich import print

class Timer:
    """A simple timer class to measure elapsed time."""
    def __init__(self):
        self.total_start_time = time.time()
        pass

    def start(self):
        """Start the timer."""
        self.start_time = time.time()

    def stop(self):
        """Stop the timer and return the elapsed time."""
        if self.start_time is None:
            raise ValueError("Timer has not been started.")
        elapsed_time = time.time() - self.start_time
        self.start_time = None
        return elapsed_time
    
    def print_total_elapsed(self):
        """Return the total elapsed time since the timer was created."""
        if self.total_start_time is None:
            raise ValueError("Timer has not been started.")
        total_elapsed_time = time.time() - self.total_start_time
        print(f"[bold green]Total elapsed time: {total_elapsed_time:.2f} seconds[/bold green]")

    def print_elapsed(self):
        """Print the elapsed time in seconds."""
        elapsed_time = self.stop()
        print(f"[bold green]Elapsed time: {elapsed_time:.2f} seconds[/bold green]")

