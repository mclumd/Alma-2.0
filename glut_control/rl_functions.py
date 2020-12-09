"""
Reinforcement learning functionality.

Currently, the following are planned:
  a) A neural network that takes two alma_functions as parameters and outputs a probability that these will not unify.
  b)
  c)
"""


from tensorflow import keras
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, Dropout
from spektral.layers import GCNConv, GlobalSumPool

import spektral
import spektral.models

import numpy as np
import unif.unifier as un
from rl_dataset import potential_inference_data
import sys
import pickle
import alma_functions as aw
from sklearn.utils import shuffle


def forward_model(use_tf = False):
    # TODO:  fix use_tf code to return everything if this ever gets used.
    if use_tf:
        import tensorflow as tf
        model  = tf.keras.models.Sequential([
            tf.keras.Input(shape=( (  2*(len(subjects)+1),)) ),    # One input for each term
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(1),
            tf.keras.layers.Softmax()
        ])
        loss_object = tf.keras.losses.BinaryCrossentropy(from_logits=True)
        optimizer = tf.keras.optimizers.Adam()
        train_loss = tf.keras.metrics.Mean(name='train_loss')
        train_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='train_accuracy')
        test_loss = tf.keras.metrics.Mean(name='test_loss')
        test_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='test_accuracy')
        print("Model summary:", self.model.summary())
    else:
        model = keras.models.Sequential()
        model.add(keras.Input(shape=( (  2*(len(subjects)+1),)) ))    # One input for each term
        model.add(keras.layers.Dense(8, activation='tanh'))
        model.add(keras.layers.Dense(8, activation='tanh'))
        model.add(keras.layers.Dense(1, activation='sigmoid'))
    return model

class gnn_model(Model):
    def __init__(self, max_nodes=20):
        super().__init__()
        self.graph_net = spektral.models.general_gnn.GeneralGNN(1, activation=None, hidden=256, message_passing=4, pre_process=2, post_process=2, connectivity='cat', batch_norm=True, dropout=0.0, aggregate='sum', hidden_activation='prelu', pool='sum')




    def call(self, inputs):
        return self.graph_net(inputs)



class res_prefilter:
    def __init__(self, subjects, words, use_tf=False, debug=True, use_gnn=False):
        self.use_tf = use_tf
        self.model = forward_model(use_tf) if not use_gnn else gnn_model()
        self.model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy', 'binary_crossentropy'])

        self.subjects = subjects
        self.words = words
        self.num_subjects = len(subjects)
        self.num_words = len(words)
        self.subjects_dict = {}
        for idx, subj in enumerate(self.subjects):
            self.subjects_dict[subj] = idx+1
        self.words_dict = {}
        for idx, word in enumerate(self.words):
            self.words_dict[word] = idx+1
        self.batch_size = 32
        self.debug=debug
        if self.debug:
            self.saved_prbs = []
            self.saved_inputs = []

        self.Xbuffer = []
        self.ybuffer = []
        self.yneg_count = 0
        self.ypos_count = 0
        print("Subjects dictionary:", self.subjects_dict)

        self.use_gnn = use_gnn
        self.vectorize_alg = 'gnn1' if use_gnn else 'bow1'
        if use_gnn:
            #self.graph_buffer = potential_inference_data()
            self.graph_buffer = None
    




    def fmla_to_graph(self, inputs):
        A, X = [], []
        for inp0, inp1 in inputs:
            graph_struct, graph_features = inputs_to_graphs(inp0, inp1)
            A.append(graph_struct)
            X.append(graph_features)

    # Use word2vec for the embeddings
    def vectorize_w2vec(self, inputs):
        X = []
        for inp0, inp1 in inputs:
            #print("inp0: {} \t inp1: {}\n".format(inp0, inp1))
            #print("inp0 constants:", aw.alma_constants([inp0]))
            #print("inp1 constants:", aw.alma_constants([inp1]))
            x = np.zeros( (2, self.num_subjects + 1))
            for idx, inp in enumerate([inp0, inp1]):
                for subj in aw.alma_constants([inp], True):
                    try:
                        x[idx, self.subjects_dict[subj]] = 1
                    except KeyError:
                        x[idx, 0] = 1
            X.append(x.flatten())
        #print('Vectorized inputs: ', X)
        #return np.array(X)
        return np.array(X, dtype=np.float32)


    def vectorize(self, inputs):
        if self.vectorize_alg == 'bow1' or self.vectorize_alg == 'gnn1':
            return self.vectorize_bow1(inputs)
        elif self.vectorize_alg == 'word2vec':
            return self.vectorize_w2vec(inputs)
        


    # Save to some buffer; use for training when we can have reasonably balanced samples.
    # The buffers will consist of numpy arrays
    
    def save_batch(self, inputs, prb_strings):
        X = self.vectorize(inputs)
        y0 = self.unifies(prb_strings)

        if self.use_tf:
            y = tf.reshape(y0, (-1, 1))
        else:
            y = np.reshape(y0, (-1, 1))
        for i in range(len(X)):
            self.Xbuffer.append(X[i])
            self.ybuffer.append(y0[i])
            # if self.use_gnn:
            #     self.graph_buffer.add(inputs[i], y0[i])
            if self.debug or self.use_gnn:
                self.saved_inputs.append(inputs[i])
                self.saved_prbs.append(prb_strings[i])

        ypos = sum(y0)
        yneg = len(y0) - ypos
        self.yneg_count += yneg
        self.ypos_count += ypos

            

    # Get a batch (X,y) of num_samples training pairs, 
    # Here X will be a (num_samples, input_size) input array
    # and y will be a (num_samples, 1) training vector.
    def get_training_batch(self, num_samples, num_pos):
        if self.debug:
            self.Xbuffer, self.ybuffer, self.saved_prbs, self.saved_inputs = shuffle(self.Xbuffer, self.ybuffer, self.saved_prbs, self.saved_inputs)
        else:
            self.Xbuffer, self.ybuffer = shuffle(self.Xbuffer, self.ybuffer)

        if self.use_gnn and self.graph_buffer is None:
            self.graph_buffer = potential_inference_data(self.saved_inputs, self.Xbuffer, self.ybuffer)

        total_samples = 0
        total_pos = 0
        Xres, yres = [], []
        num_neg = num_samples - num_pos
        while (total_samples < num_samples) and (total_pos < num_pos):
            x, y = self.Xbuffer.pop(), self.ybuffer.pop()
            if self.debug:
               self.saved_prbs.pop(), self.saved_inputs.pop()
            total_neg = total_samples - total_pos
            needed_pos = num_pos - total_pos
            needed_neg  = num_neg - total_neg
            if y == 0:
                self.yneg_count -= 1
                # Only add a negative sample if there's still enough
                # room for the remaining positives
                if (total_samples + needed_pos) < num_samples:
                    Xres.append(x)
                    yres.append(y)
                    total_samples += 1
            else:
                self.ypos_count -= 1
                # Only add a positive sample if there's still enough
                # room for the remaining negatives
                if (total_samples + needed_neg) < num_samples:
                    Xres.append(x)
                    yres.append(y)
                    total_samples += 1
                    total_pos += 1
        return np.array(Xres), np.array(yres)

    def train_buffered_batch(self, sample_ratio=0.5):
        X, y0 = self.get_training_batch(self.batch_size, int(self.batch_size*sample_ratio))
        if self.use_tf:
            y = tf.reshape(y0, (-1, 1))
        else:
            y = y0
        if self.use_tf:
            with tf.GradientTape() as tape:
                predb = self.model(X)
                loss = self.loss_object(y, predb)
            gradients = tape.gradient(loss, self.model.trainable_variables)
            self.optimizer.apply_gradients(zip(gradients, self.model.trainable_variables))
            print("y, pred:", y.numpy().T, pred.numpy().T)
            print("loss: {} \t acc: {}\n".format(self.train_loss(loss), self.train_accuracy(y, pred), end='\r'))
            return pred
        else:
            # TODO:  make sure this continues training rather than reinitializing
            return self.model.fit(X, y, batch_size=self.batch_size, verbose=True)

    #@tf.function
    def train_batch(self, inputs, prb_strings):
        #print("inputs=", inputs)
        X = self.vectorize(inputs)
        #print("X=", X)
        y0 = self.unifies(prb_strings)
        if self.use_tf:
            y = tf.reshape(y0, (-1, 1))
        else:
            y = np.reshape(y0, (-1, 1))
            #print("y=", y)
        preds = []
        if self.use_tf:
            num_batches = X.shape[0] // self.batch_size
            for b in range(num_batches):
                Xb = X[b*self.batch_size : (b+1)*self.batch_size]
                yb = y[b*self.batch_size : (b+1)*self.batch_size]
                with tf.GradientTape() as tape:
                    predb = self.model(Xb)
                    loss = self.loss_object(yb, predb)
                    preds.append(predb)
                gradients = tape.gradient(loss, self.model.trainable_variables)
                self.optimizer.apply_gradients(zip(gradients, self.model.trainable_variables))
                print("yb, predb:", yb.numpy().T, predb.numpy().T)
                print("loss: {} \t acc: {}\n".format(self.train_loss(loss), self.train_accuracy(yb, predb), end='\r'))
            return preds
        else:
            ones = sum(y0)
            zeros = len(y0) - ones
            if ones*zeros > 0:
                weights = {
                    0: ones,
                    1: zeros
                }
                self.model.fit(X, y, batch_size=self.batch_size, class_weight=weights)
            else:
                self.model.fit(X, y, batch_size=self.batch_size)

    def get_priorities(self, inputs):
        X = self.vectorize(inputs)
        preds = self.model.predict(X)
        return preds

    def model_save(self, id_str, numeric_bits):
        pkl_file = open("rl_model_{}.pkl".format(id_str), "wb")
        pickle.dump((self.subjects, self.words, self.num_subjects, self.num_words, self.subjects_dict, self.words_dict, self.batch_size, self.use_tf, numeric_bits), pkl_file)
        self.model.save("rl_model_{}".format(id_str))

    def model_load(self, id_str):
        self.model = keras.models.load_model("rl_model_{}".format(id_str))

    def unify_likelihood(self, inputs):
        X = self.vectorize(inputs)
        return self.model.predict(X)
    

def rpf_load(id_str):
    pkl_file = open("rl_model_{}.pkl".format(id_str), "rb")
    subjects, words, num_subjects, num_words, subjects_dict, words_dict, batch_size, use_tf, num_bits = pickle.load(pkl_file)
    rpf = res_prefilter(subjects, words, use_tf)
    rpf.num_subjects = num_subjects
    rpf.num_words = num_words
    rpf.subjects_dict = subjects_dict
    rpf.words_dict = words_dict
    rpf.batch_size = batch_size
    rpf.model_load(id_str)
    rpf.num_bits = num_bits
    return rpf

