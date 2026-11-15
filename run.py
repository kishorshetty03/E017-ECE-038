"""Usage: python run.py [commands.txt] [output_dir]"""
import sys
from engine import run_commands

if __name__ == "__main__":
    run_commands(sys.argv[1] if len(sys.argv) > 1 else "data/commands.txt", sys.argv[2] if len(sys.argv) > 2 else "output")
