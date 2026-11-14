"""Run a command; print its wall time and the peak memory of the child process.

Used for the run-time and memory figures in the evidence reports. On macOS ``ru_maxrss`` is
in bytes. Usage: ``uv run python scripts/measure.py <command> [args...]``.
"""

import resource
import subprocess
import sys
import time

start = time.perf_counter()
code = subprocess.call(sys.argv[1:])
seconds = time.perf_counter() - start
peak_gib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 2**30
print(f"exit {code}  wall {seconds:.1f} s  peak memory {peak_gib:.2f} GiB")
sys.exit(code)
