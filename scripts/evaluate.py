"""
Get average scores and various other metrics across entire dataset
"""

# My imports
from constants import *
from utils import *

# Regular imports
from mir_eval.transcription import precision_recall_f1_overlap as evaluate_notes
from mir_eval.separation import bss_eval_sources as evaluate_separation
from mir_eval.multipitch import evaluate as evaluate_frames
from scipy.stats import hmean
from sacred import Experiment
from tqdm import tqdm

import numpy as np
import sys
import os

eps = sys.float_info.epsilon

ex = Experiment('Evaluate_Predictions')

# TODO - avg prec to cover all thresholds?

@ex.config
def config():
    # Evaluate this single file if not empty
    # Example - '00_BN1-129-Eb_comp'
    single = ''#'00_BN1-129-Eb_comp'

    # Remove this player from the split if not empty
    # Example = '00'
    # Use this attribute if a single file is not chosen
    player = '01'

    hop_len = 512

    # Switch for console printing in addition to saving text to file
    verbose = True

def write_and_print_results(file, verbose, f_pr, f_re, f_f1,
                            n1_pr, n1_re, n1_f1, n2_pr, n2_re, n2_f1):
    # TODO - this could be cleaned up by passing the metrics dict with an additional name entry
    write_and_print(file, '-----Frame-----\n', verbose)
    write_and_print(file, f'  Precision : {f_pr}\n', verbose)
    write_and_print(file, f'  Recall    : {f_re}\n', verbose)
    write_and_print(file, f'  F1-Score  : {f_f1}\n\n', verbose)

    write_and_print(file, '-----Note-----\n', verbose)
    write_and_print(file, f'  Precision : {n1_pr}\n', verbose)
    write_and_print(file, f'  Recall    : {n1_re}\n', verbose)
    write_and_print(file, f'  F1-Score  : {n1_f1}\n\n', verbose)

    write_and_print(file, '-----Note w/ Offsets-----\n', verbose)
    write_and_print(file, f'  Precision : {n2_pr}\n', verbose)
    write_and_print(file, f'  Recall    : {n2_re}\n', verbose)
    write_and_print(file, f'  F1-Score  : {n2_f1}\n\n', verbose)

@ex.automain
def main(single, player, hop_len, verbose):
    # Create the dictionary directory if it does not already exist
    reset_generated_dir(GEN_RESULTS_DIR, [], False)

    # Obtain the track list for the chosen data partition
    track_keys = clean_track_list(GuitarSetHandle, single, player, False)

    # Initialize an array to hold a metric for each tracks
    empty = np.zeros(len(track_keys))

    # Create a dictionary to hold the metrics of each track
    metrics = {'f_pr' : empty.copy(),
               'f_re' : empty.copy(),
               'f_f1' : empty.copy(),
               'n1_pr' : empty.copy(),
               'n1_re' : empty.copy(),
               'n1_f1' : empty.copy(),
               'n2_pr' : empty.copy(),
               'n2_re' : empty.copy(),
               'n2_f1' : empty.copy()}

    for idx, track_id in tqdm(enumerate(track_keys)):
        # Construct a path for the track's transcription and separation results
        results_path = os.path.join(GEN_RESULTS_DIR, f'{track_id}.txt')

        # Open the file with writing permissions
        results_file = open(results_path, 'w')

        # Add heading to file
        write_and_print(results_file, f'Evaluating track : {track_id}\n', verbose)

        t_est, f_est, t_ref, f_ref = get_frames_contours(track_id, hop_len)
        #t_est2, f_est2, t_ref2, f_ref2 = get_frames_notes(track_id, hop_len)

        # Compare the ground-truth to the predictions to get the frame-wise metrics
        # TODO - mir_eval resampling is causing problems
        frame_metrics = evaluate_frames(t_ref, f_ref, t_est, f_est)

        # Calculate frame-wise precision, recall, and f1 score
        f_pr, f_re = frame_metrics['Precision'], frame_metrics['Recall']
        f_f1 = hmean([f_pr + eps, f_re + eps]) - eps

        # Add the frame-wise metrics to the dictionary
        metrics['f_pr'][idx], metrics['f_re'][idx], metrics['f_f1'][idx] = f_pr, f_re, f_f1

        i_est, p_est, i_ref, p_ref = get_notes(track_id)

        # Calculate frame-wise precision, recall, and f1 score ignoring a correct offset
        n1_pr, n1_re, n1_f1, _ = evaluate_notes(i_ref, p_ref, i_est, p_est, offset_ratio=None)

        # Calculate frame-wise precision, recall, and f1 score requiring a correct offset
        n2_pr, n2_re, n2_f1, _ = evaluate_notes(i_ref, p_ref, i_est, p_est)

        # Add the note-wise metrics to the dictionary
        metrics['n1_pr'][idx], metrics['n1_re'][idx], metrics['n1_f1'][idx] = n1_pr, n1_re, n1_f1
        metrics['n2_pr'][idx], metrics['n2_re'][idx], metrics['n2_f1'][idx] = n2_pr, n2_re, n2_f1

        # TODO - tablature metrics

        # Print the results for the individual file
        write_and_print_results(results_file, verbose, f_pr, f_re, f_f1,
                                n1_pr, n1_re, n1_f1, n2_pr, n2_re, n2_f1)

        # Close the results file
        results_file.close()

        if verbose:
            # Add a newline to the console
            print()

    if single == '':
        # TODO - cleanup using .values()
        # Obtain the average value across tracks for each metric
        f_pr = np.mean(metrics['f_pr'])
        f_re = np.mean(metrics['f_re'])
        f_f1 = np.mean(metrics['f_f1'])
        n1_pr = np.mean(metrics['n1_pr'])
        n1_re = np.mean(metrics['n1_re'])
        n1_f1 = np.mean(metrics['n1_f1'])
        n2_pr = np.mean(metrics['n2_pr'])
        n2_re = np.mean(metrics['n2_re'])
        n2_f1 = np.mean(metrics['n2_f1'])

        # Construct a path for the overall results
        ovr_results_path = os.path.join(GEN_RESULTS_DIR, f'_overall.txt')

        # Open the file with writing permissions
        ovr_results_file = open(ovr_results_path, 'w')

        # Add heading to file
        write_and_print(ovr_results_file, 'Overall Results\n', verbose)

        # Print the average results across this run
        write_and_print_results(ovr_results_file, verbose, f_pr, f_re, f_f1,
                                n1_pr, n1_re, n1_f1, n2_pr, n2_re, n2_f1)

        # Close the results file
        ovr_results_file.close()
