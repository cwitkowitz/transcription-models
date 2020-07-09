# My imports
from .constants import *
from .dataproc import *
from .utils import *

# Regular imports
from torch.utils.data import Dataset
from abc import abstractmethod
from random import randint
from copy import deepcopy
from tqdm import tqdm

import torch.nn.functional as F
import numpy as np
import mirdata
import shutil
import os

# TODO - ComboDataset


class TranscriptionDataset(Dataset):
    def __init__(self, base_dir, splits, hop_length, data_proc, frame_length, reset_data):

        # Check if the dataset exists in memory
        if not os.path.isdir(base_dir):
            # Download the dataset if it is missing
            self.download(base_dir)

        self.splits = splits
        if self.splits is None:
            self.splits = self.available_splits()

        self.hop_length = hop_length

        self.data_proc = data_proc
        if self.data_proc is None:
            self.data_proc = CQT()

        self.frame_length = frame_length

        if self.frame_length is None:
            self.seq_length = None
        else:
            self.seq_length = max(self.data_proc.get_sample_range(self.frame_length))

        self.reset_data = reset_data

        if os.path.exists(self.get_gt_dir()) and self.reset_data:
            shutil.rmtree(self.get_gt_dir())
            os.makedirs(self.get_gt_dir())

        if os.path.exists(self.get_feats_dir()) and self.reset_data:
            shutil.rmtree(self.get_feats_dir())
            os.makedirs(self.get_feats_dir())

        # Load the paths of the audio tracks
        self.tracks = []

        # TODO - do I need this for-loop?
        for split in self.splits:
            self.tracks += self.get_tracks(split)

        self.data = {}

        # TODO - do I need this for-loop?
        print('Loading ground-truth')
        for track in tqdm(self.tracks):
            self.data[track] = self.load(track)

    def __len__(self):
        return len(self.tracks)

    def __getitem__(self, index):
        track = self.tracks[index]

        data = deepcopy(self.data[track])

        feats_path = self.get_feats_dir(track)

        if os.path.exists(feats_path):
            # TODO - different key for each module?
            feats = np.load(feats_path)['feats']
        else:
            # TODO - invoke data_proc only once unless fb learn
            feats = self.data_proc.process_audio(data['audio'])
            np.savez(feats_path, feats=feats)

        data['feats'] = feats

        if self.frame_length is not None:
            # TODO - how much will it hurt to pad with zeros instead of actual previous/later frames?

            # TODO - note splitting here for sample start
            sample_start = randint(0, len(data['audio']) - self.seq_length)

            frame_start = sample_start // self.hop_length
            frame_end = frame_start + self.frame_length

            # TODO - quantize at even frames or start where sampled?
            #sample_start = frame_start * self.hop_length
            sample_end = sample_start + self.seq_length

            data['audio'] = data['audio'][sample_start : sample_end]
            data['tabs'] = data['tabs'][:, :, frame_start : frame_end]
            data['feats'] = feats[:, :, frame_start : frame_end]
            #data.pop('notes')

        return data

    @abstractmethod
    def get_tracks(self, split):
        return NotImplementedError

    @abstractmethod
    def load(self, track):
        data = None
        gt_path = self.get_gt_dir(track)
        if os.path.exists(gt_path):
            data = dict(np.load(gt_path))
        return data

    def get_gt_dir(self, track=None):
        path = os.path.join(GEN_DATA_DIR, self.dataset_name(), 'gt')
        if track is not None:
            path = os.path.join(path, track + '.npz')
        return path

    def get_feats_dir(self, track=None):
        path = os.path.join(GEN_DATA_DIR, self.dataset_name(), self.data_proc.features_name())
        if track is not None:
            path = os.path.join(path, track + '.npz')
        return path

    @staticmethod
    @abstractmethod
    def available_splits():
        return NotImplementedError

    @staticmethod
    @abstractmethod
    def dataset_name():
        return NotImplementedError

    @staticmethod
    @abstractmethod
    def download(save_dir):
        return NotImplementedError

"""
class MAPS(TranscriptionDataset):
    def __init__(self, base_dir):
        super().__init__()

    @staticmethod
    def available_splits():
        return ['AkPnBcht', 'AkPnBsdf', 'AkPnCGdD', 'AkPnStgb',
                'ENSTDkAm', 'ENSTDkCl', 'SptkBGAm', 'SptkBGCl', 'StbgTGd2']

class MAESTRO(TranscriptionDataset):
    def __init__(self, base_dir):
        super().__init__()

    @staticmethod
    def available_splits():
        # TODO - alternative year splits?
        return ['train', 'validation', 'test']

    @staticmethod
    def download(save_dir):
        # TODO - "flac" option which download flac instead
        pass
"""


class GuitarSet(TranscriptionDataset):
    def __init__(self, base_dir=None, splits=None, hop_length=512,
                 data_proc=None, frame_length=None, reset_data=False):

        self.base_dir = base_dir
        if self.base_dir is None:
            self.base_dir = os.path.join(HOME, 'Desktop', 'Datasets', self.dataset_name())

        super().__init__(self.base_dir, splits, hop_length, data_proc, frame_length, reset_data)

    def get_tracks(self, split):
        jams_dir = os.path.join(self.base_dir, 'annotation')
        jams_paths = os.listdir(jams_dir)
        jams_paths.sort()

        tracks = [os.path.splitext(path)[0] for path in jams_paths]

        split_start = int(split) * 60

        tracks = tracks[split_start : split_start + 60]

        return tracks

    def load(self, track):
        data = super().load(track)

        if data is None:
            data = {}

            wav_path = os.path.join(self.base_dir, 'audio_mono-mic', track + '_mic.wav')
            audio, _ = load_audio(wav_path)
            data['audio'] = audio

            num_frames = self.data_proc.get_expected_frames(audio)

            jams_path = os.path.join(self.base_dir, 'annotation', track + '.jams')
            tabs = load_jams_guitar_tabs(jams_path, self.hop_length, num_frames)
            data['tabs'] = tabs

            i_ref, p_ref = load_jams_guitar_notes(jams_path)
            p_ref = np.array([p_ref]).T
            notes = np.concatenate((i_ref, p_ref), axis=-1)
            data['notes'] = notes

            gt_path = self.get_gt_dir(track)
            np.savez(gt_path, audio=audio, tabs=tabs, notes=notes)

        data['track'] = track

        return data

    @staticmethod
    def available_splits():
        return ['00', '01', '02', '03', '04', '05']

    @staticmethod
    def dataset_name():
        return 'GuitarSet'

    @staticmethod
    def download(save_dir):
        # If the directory already exists, remove it
        if os.path.isdir(save_dir):
            shutil.rmtree(save_dir)

        # Create the base directory
        os.mkdir(save_dir)

        print(f'Downloading {GuitarSet.dataset_name()}')

        # Download GuitarSet
        # TODO - mirdata might be overkill if I don't use its load function
        # TODO - "flac" option which download flac instead
        mirdata.guitarset.download(data_home=save_dir)

    # TODO - MusicNet already implemented