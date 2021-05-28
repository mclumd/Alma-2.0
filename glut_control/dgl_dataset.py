######################################################################
# ``DGLDataset`` Object Overview
# ------------------------------
#
# Your custom graph dataset should inherit the ``dgl.data.DGLDataset``
# class and implement the following methods:
#
# -  ``__getitem__(self, i)``: retrieve the ``i``-th example of the
#    dataset. An example often contains a single DGL graph, and
#    occasionally its label.
# -  ``__len__(self)``: the number of examples in the dataset.
# -  ``process(self)``: load and process raw data from disk.
#

import pandas as pd

import dgl
from dgl.data import DGLDataset
import torch
import numpy as np
import os

# Constructor takes an Xbuffer and ybuffer from res_prebuffer object (having saved batch(es))
# Built and tested with output from save_batch when use_gnn = True and use_tf = False
# save_batch calls vectorize, this built and tested on data from the vectorize_alg = gnn1 mode

class GNNDataset(DGLDataset):
    def __init__(self, Xbuffer, ybuffer):
        self.X = Xbuffer
        self.Y = ybuffer
        # The overridden process function is automatically called after construction
        super().__init__(name='GNN')

    def process(self):
        self.graphs = []
        self.labels = []
        src = np.array([1])     # A placeholder for the array before we begin appending edge information
        dst = np.array([1])     # It will be sliced off before passing to the dgl.graph constructor, maybe there is a better way to do this? Don't know numpy that well
        label = None
        num_nodes = -1

        # Iterate over list of graphs
        # For each adjacency, store a bidirectional edge between lowercase x and y,
        # this ensures no node is isolated from message passing
        # Then store the graph label from y
        # Last, grab num_nodes from size of adjacency matrix
        i = 0
        for graph in self.X:
            y = 0
            for row in graph[0]:
                x = 0
                for column in row:
                    if column == 1.0:
                        src = np.append(src, [x])
                        src = np.append(src, [y])
                        dst = np.append(dst, [y])
                        dst = np.append(dst, [x])
                    x += 1
                y += 1
            label = self.Y[i]
            num_nodes = len(graph[0][0])
            # Create a graph and add it to the list of graphs and labels.
            g = dgl.graph((src[1:], dst[1:]), num_nodes=num_nodes)
            # Grab features for g from X[i][1]
            # Convert to tensor via torch to avoid the "numpy.ndarray has no attribute 'device'" error
            # https://discuss.dgl.ai/t/attributeerror-numpy-ndarray-object-has-no-attribute-device/241
            g.ndata['feat'] = torch.LongTensor(graph[1])
            self.graphs.append(g)
            self.labels.append(label)
            i += 1

        # Convert the label list to tensor for saving.
        self.labels = torch.LongTensor(self.labels)

    def __getitem__(self, i):
        return self.graphs[i], self.labels[i]

    def __len__(self):
        return len(self.graphs)