"""
Run my algorithm on each file of GuitarSet and save results
"""

# My imports
from tools.constants import *
from tools.datasets import *
from tools.dataproc import *
from tools.models import *
from tools.utils import *

# Regular imports
from tqdm import tqdm

import numpy as np
import torch
import os

def extract_notes(frames, hop_len, min_note_span):
    # TODO - clean this ish up
    # Create empty lists for note pitches and their time intervals
    pitches, ints = [], []

    onsets = np.concatenate([frames[:, :1], frames[:, 1:] - frames[:, :-1]], axis=1) == 1

    # Find the nonzero indices
    nonzeros = onsets.nonzero()
    for i in range(len(nonzeros[0])):
        # Get the frame and pitch index
        pitch, frame = nonzeros[0][i], nonzeros[1][i]

        # Mark onset and start offset counter
        onset, offset = frame, frame

        # Increment the offset counter until the pitch activation
        # turns negative or until the last frame is reached
        while frames[pitch, offset]:
            if onset == offset and np.sum(onsets[:, max(0, onset - int(0.10 * SAMPLE_RATE // hop_len)) : onset]) > 0:
                break
            offset += 1
            if offset == frames.shape[1]:
                break

        # Make sure the note duration exceeds a minimum frame length
        if offset >= onset + min_note_span:
            # Determine the absolute frequency
            freq = librosa.midi_to_hz(pitch + LOWEST_NOTE)

            # Add the frequency to the list
            pitches.append(freq)

            # TODO - can probs utilize librosa here - it does same thing but with array
            # Determine the time where the onset and offset occur
            onset, offset = onset * hop_len / SAMPLE_RATE, offset * hop_len / SAMPLE_RATE

            # TODO - window length is ambiguous - remove? - also check librosa func
            # Add half of the window time for frame-centered predictions
            #bias = (0.5 * win_len / SAMPLE_RATE)
            #onset, offset = onset + bias, offset + bias

            # Add the interval to the list
            ints.append([onset, offset])

    # Convert the lists to numpy arrays
    pitches, intervals = np.array(pitches), np.array(ints)

    return pitches, intervals

def transcribe(classifier, loader, hop_length, min_note_span, log_dir):
    # Just in case
    classifier.eval()

    for track in tqdm(loader):
        track_id = track['track'][0]

        tabs, loss = classifier.run_on_batch(track)

        tabs = tabs.squeeze().cpu().detach().numpy().T
        loss = loss.cpu().detach().numpy()

        string_pianoroll = tabs_to_multi_pianoroll(tabs)

        string_notes = [extract_notes(string_pianoroll[i], hop_length, min_note_span) for i in range(NUM_STRINGS)]

        pianoroll = tabs_to_pianoroll(tabs).T

        all_pitches, all_ints = [], []

        os.makedirs(os.path.join(log_dir, 'frames'), exist_ok=True)
        os.makedirs(os.path.join(log_dir, 'notes'), exist_ok=True)
        os.makedirs(os.path.join(log_dir, 'tabs'), exist_ok=True)
        # Create the activation directory if it does not already exist

        tabs_dir = os.path.join(log_dir, 'tabs', f'{track_id}')
        os.makedirs(os.path.join(tabs_dir), exist_ok=True)

        for i, s in enumerate(TUNING):
            tab_txt_path = os.path.join(tabs_dir, f'{s}.txt')
            pitches, ints = string_notes[i]
            all_pitches += list(pitches)
            all_ints += list(ints)
            write_notes(tab_txt_path, pitches, ints)

        all_pitches, all_ints = np.array(all_pitches), np.array(all_ints)

        # Construct the paths for frame- and note-wise predictions
        frm_txt_path = os.path.join(log_dir, 'frames', f'{track_id}.txt')
        nte_txt_path = os.path.join(log_dir, 'notes', f'{track_id}.txt')

        # Save the predictions to file
        write_frames(frm_txt_path, hop_length, pianoroll)
        write_notes(nte_txt_path, all_pitches, all_ints)