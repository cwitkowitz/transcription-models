import numpy as np
import librosa
import os

# Paths
HOME = os.path.expanduser('~')
AUXL_DIR = os.path.dirname(os.path.abspath(__file__))
SCPT_DIR = os.path.dirname(os.path.join(AUXL_DIR))
ROOT_DIR = os.path.dirname(os.path.join(SCPT_DIR))
GENR_DIR = os.path.abspath(os.path.join(ROOT_DIR, 'generated'))

GEN_DATA_DIR = os.path.join(GENR_DIR, 'data')

# Guitar properties
TUNING = ['E2', 'A2', 'D3', 'G3', 'B3', 'E4']
NUM_STRINGS = len(TUNING)
NUM_FRETS = 19

# Create an array with the midi numbers of each open string
TUNING_MIDI = np.array([librosa.note_to_midi(TUNING)]).T

# The lowest possible note - i.e. the open note of the lowest string
LOWEST_NOTE = librosa.note_to_midi(TUNING[0])

# The highest possible note - i.e. the maximum fret on the highest string
HIGHEST_NOTE = librosa.note_to_midi(TUNING[NUM_STRINGS - 1]) + NUM_FRETS

# Number of notes in the guitar note range
NOTE_RANGE = HIGHEST_NOTE - LOWEST_NOTE + 1

# TODO - abstract some of these parameters - they can be different depending on experiment
SAMPLE_RATE = 44100

SEED = 0
