# My imports
from models.common import *

from tools.conversion import *
from tools.utils import *

# Regular imports
from torch import nn

import torch.nn.functional as F

# TODO - different file naming scheme? - don't remember why I put this here


class TabCNN(TranscriptionModel):
    def __init__(self, dim_in, dim_out, model_complexity=1, device='cpu', win_len=9):
        super().__init__(dim_in, dim_out, model_complexity, device)

        # TODO - redo model complexity
        # Number of frames required for a prediction
        sample_width = 9

        # Number of filters for each stage
        nf1 = 32 * self.model_complexity
        nf2 = 64 * self.model_complexity
        nf3 = nf2

        # Kernel size for each stage
        ks1 = (3, 3)
        ks2 = ks1
        ks3 = ks1

        # Reduction size for each stage
        rd1 = (2, 2)

        # Dropout percentages for each stage
        dp1 = 0.25
        dp2 = 0.50

        # Number of neurons for each fully-connected stage
        nn1 = 128
        nn2 = dim_out

        # TODO - fold into the data_proc module? might save redundant information to disk
        #        might also get hairy w.r.t. what the user decides to feed in - this pre_proc block will still be run
        self.win_len = win_len

        self.spatial = nn.Sequential(
            # 1st convolution
            nn.Conv2d(1, nf1, ks1),
            # Activation function
            nn.ReLU(),
            # 2nd convolution
            nn.Conv2d(nf1, nf2, ks2),
            # Activation function
            nn.ReLU(),
            # 3rd convolution
            nn.Conv2d(nf2, nf3, ks3),
            # Activation function
            nn.ReLU(),
            # 1st reduction
            nn.MaxPool2d(rd1),
            # 1st dropout
            nn.Dropout(dp1)
        )

        feat_map_height = (dim_in - 6) // 2
        feat_map_width = (sample_width - 6) // 2
        self.feat_map_size = nf3 * feat_map_height * feat_map_width

        self.dense = nn.Sequential(
            # 1st fully-connected
            nn.Linear(self.feat_map_size, nn1),
            # Activation function
            nn.ReLU(),
            # 2nd dropout
            nn.Dropout(dp2),
            # 2nd fully-connected
            SoftmaxGroups(nn1, NUM_STRINGS, NUM_FRETS + 2, 'tabs')
        )

    def pre_proc(self, batch):
        feats = batch['feats']
        # Window the features
        feats = framify_tfr(feats, self.win_len, 1, self.win_len // 2)
        # Switch the sample-frame and sequence-frame axes
        feats = feats.transpose(-1, -2)
        # Switch the sequence-frame and feature axes
        feats = feats.transpose(-2, -3)
        # Remove the single channel dimension
        feats = feats.squeeze(1)
        batch['feats'] = feats

        # Add the batch to the model's device
        super().pre_proc(batch)

        return batch

    def forward(self, feats):
        bs = get_batch_size(feats)
        # Collapse the sequence-frame axis into the batch axis, so that
        # each windowed group of frames is treated as one independent sample
        feats = feats.reshape(-1, 1, self.dim_in, self.win_len)
        x = (self.spatial(feats))
        x = x.flatten().view(bs, -1, self.feat_map_size)
        preds = self.dense(x)

        return preds

    # TODO - if this will be the same for other transcription models, abstract it to a function and just call that
    def post_proc(self, batch):
        preds = batch['preds']

        out_layer = self.dense[-1]

        label = out_layer.tag
        output = preds[label]

        loss = None

        # Check to see if ground-truth is available
        if label in batch.keys():
            reference = batch[label]
            loss = out_layer.get_loss(output, reference)

        preds.update({
            'loss' : loss
        })

        preds[label] = out_layer.finalize_output(output)

        return preds