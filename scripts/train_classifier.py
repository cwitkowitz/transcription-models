"""
TODO
"""

# My imports
from constants import *
from utils import *

# Regular imports
from torch.utils.data import Dataset, DataLoader
from tensorboardX import SummaryWriter
from sacred import Experiment
from tqdm import tqdm
from torch import nn

import torch.nn.functional as F
import numpy as np
import librosa
import random
import torch
import jams
import os

# TODO - seed this S

ex = Experiment('Train Classifier')

@ex.config
def config():
    # Use this single file if not empty
    # Example - '00_BN1-129-Eb_comp'
    single = ''#'00_BN1-129-Eb_comp'

    # Remove this player from the split if not empty
    # Example = '00'
    # Use this attribute if a single file is not chosen
    player = '03'

    win_len = 512 # samples

    # Number of samples between frames
    hop_len = 512 # samples

    # GPU to use for convolutional sparse coding
    gpu_num = 0

    iters = 8000

    batch_size = 300

    l_rate = 1e0

    seed = 0

class TabCNN(nn.Module):
    def __init__(self, device):
        super().__init__()

        self.device = None

        self.cn1 = nn.Conv2d(1, 32, 3)
        self.cn2 = nn.Conv2d(32, 64, 3)
        self.cn3 = nn.Conv2d(64, 64, 3)
        self.mxp = nn.MaxPool2d(2)
        self.dp1 = nn.Dropout(0.25)
        self.fc1 = nn.Linear(5952, 128)
        self.dp2 = nn.Dropout(0.50)
        self.fc2 = nn.Linear(128, 126)

        self.changeDevice(device)

    def changeDevice(self, device):
        self.device = device
        self.to(self.device)

    def forward(self, batch):
        cqt = batch['cqt'].to(self.device)
        tabs = batch['tabs'].to(self.device)

        x = F.relu(self.cn1(cqt))
        x = F.relu(self.cn2(x))
        x = F.relu(self.cn3(x))
        x = self.mxp(x).flatten().view(-1, 5952)
        x = self.dp1(x)
        x = F.relu(self.fc1(x))
        x = self.dp2(x)
        out = self.fc2(x).view(tabs.shape)

        preds = torch.argmax(torch.softmax(out, dim=-1), dim=-1)

        out = out.view(-1, NUM_FRETS + 2)
        tabs = tabs.view(-1, NUM_FRETS + 2)
        loss = F.cross_entropy(out, torch.argmax(tabs, dim=-1), reduction='none')
        loss = torch.sum(loss.view(-1, NUM_STRINGS), dim=-1)

        return preds, loss

@ex.automain
def train_classifier(single, player, win_len, hop_len, gpu_num, iters, batch_size, l_rate, seed):
    # Create the activation directory if it does not already exist

    # Path for saving the dictionary
    if single == '':
        class_dir = f'excl_{player}'
    else:
        class_dir = f'{single}'

    reset_generated_dir(GEN_CLASS_DIR, [class_dir], False)
    reset_generated_dir(GEN_GT_DIR, [], False)

    class_dir = os.path.join(GEN_CLASS_DIR, class_dir)
    out_path = os.path.join(class_dir, 'model.pt')

    os.makedirs(class_dir, exist_ok=True)
    writer = SummaryWriter(class_dir)

    # Obtain the track list for the chosen data partition
    track_keys = clean_track_list(GuitarSetHandle, single, player, True)

    torch.backends.cudnn.deterministic = True
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    random.seed(seed)

    train_tabs = GuitarSet(track_keys, win_len, hop_len, 'train', seed)

    loader = DataLoader(train_tabs, batch_size, shuffle=True, num_workers=16, drop_last=False)

    device = f'cuda:{gpu_num}' if torch.cuda.is_available() else 'cpu'

    classifier = TabCNN(device)
    classifier.train()

    optimizer = torch.optim.Adadelta(classifier.parameters(), l_rate)

    # TODO - explicit epochs
    for i in tqdm(range(iters)):
        for batch in loader:
            optimizer.zero_grad()
            preds, loss = classifier(batch)
            writer.add_scalar(f'train_loss', torch.mean(loss), global_step=i)
            torch.mean(loss).backward()
            optimizer.step()

    if os.path.exists(out_path):
        os.remove(out_path)

    torch.save(classifier, out_path)
