import numpy as np
import os
import tensorflow as tf
from data_utils import minibatches, pad_sequences, get_chunks, label2ind_ret, max_words_in_sent,readcorpus, createMatrices
from general_utils import Progbar, print_sentence
#from tflearn.layers.embedding_ops import embedding
#from tflearn.layers.core import input_data
Globepoch = 0

class NERModel(object):
    Globepoch = 0
    def __init__(self, config, embeddings, ntags, nchars=None):
        """
        Args:
            config: class with hyper parameters
            embeddings: np array with embeddings
            nchars: (int) size of chars vocabulary
        """
        self.config     = config
        self.embeddings = embeddings
        self.nchars     = nchars
        self.ntags      = ntags
        self.logger     = config.logger # now instantiated in config

        #self.Globepoch+=1
    def add_placeholders(self):
        """
        Adds placeholders to self
        """

        # shape = (batch size, max length of sentence in batch)
        self.word_ids = tf.placeholder(tf.int32, shape=[None, None],
                        name="word_ids")
        #########################################################################################################
        ## Here we have to replicate the same steps of words since we have only 1 suffix per word and only 1 prefix per word unlike characters which are many in number per word.
        self.pref_ids = tf.placeholder(tf.int32, shape=[None, None],
                                       name="pref_ids")
        self.suff_ids = tf.placeholder(tf.int32, shape=[None, None],
                                       name="suff_ids")

        self.pref_ids_2 = tf.placeholder(tf.int32, shape=[None, None],
                                       name="pref_ids_2")
        self.suff_ids_2 = tf.placeholder(tf.int32, shape=[None, None],
                                       name="suff_ids_2")

        self.pref_ids_4 = tf.placeholder(tf.int32, shape=[None, None],
                                         name="pref_ids_4")
        self.suff_ids_4 = tf.placeholder(tf.int32, shape=[None, None],
                                         name="suff_ids_4")
        #########################################################################################################
        # shape = (batch size)


        self.sequence_lengths = tf.placeholder(tf.int32, shape=[None],
                        name="sequence_lengths")

        # shape = (batch size, max length of sentence, max length of word)
        self.char_ids = tf.placeholder(tf.int32, shape=[None, None, None],
                        name="char_ids")

        # shape = (batch_size, max_length of sentence)
        self.word_lengths = tf.placeholder(tf.int32, shape=[None, None],
                        name="word_lengths")

        # shape = (batch size, max length of sentence in batch)
        self.labels = tf.placeholder(tf.int32, shape=[None, None],
                        name="labels")

        # hyper parameters
        self.dropout = tf.placeholder(dtype=tf.float32, shape=[],
                        name="dropout")
        self.lr = tf.placeholder(dtype=tf.float32, shape=[], 
                        name="lr")


    def get_feed_dict(self, words, labels=None, lr=None, dropout=None):
        """
        Given some data, pad it and build a feed dictionary
        Args:
            words: list of sentences. A sentence is a list of ids of a list of words. 
                A word is a list of ids
            labels: list of ids
            lr: (float) learning rate
            dropout: (float) keep prob
        Returns:
            dict {placeholder: value}
        """
        # perform padding of the given data
        if self.config.chars:
            #print (words[0])
            char_ids,pref_ids, suff_ids,pref_ids_2, suff_ids_2,pref_ids_4, suff_ids_4, word_ids = zip(*words)  ##, pref_ids, suff_ids,
            word_ids, sequence_lengths = pad_sequences(word_ids, 0)
            #####################################################################
            pref_ids, sequence_lengths_pref = pad_sequences(pref_ids, 0)
            suff_ids, sequence_lengths_suff = pad_sequences(suff_ids, 0)
            pref_ids_2, sequence_lengths_pref_2 = pad_sequences(pref_ids_2, 0)
            suff_ids_2, sequence_lengths_suff_2 = pad_sequences(suff_ids_2, 0)

            pref_ids_4, sequence_lengths_pref_4 = pad_sequences(pref_ids_4, 0)
            suff_ids_4, sequence_lengths_suff_4 = pad_sequences(suff_ids_4, 0)
            #####################################################################
            char_ids, word_lengths = pad_sequences(char_ids, pad_tok=0, nlevels=2)   ##################################################################### Orig
        else:
            word_ids, sequence_lengths = pad_sequences(words, 0)

        # build feed dictionary
        feed = {                                         ########################### Same for suffix prefix
            self.word_ids: word_ids,
            self.sequence_lengths: sequence_lengths,     ###### The sequence length will be same for all these features: words, suffix, prefix, suffix_2 and suffix_3.

            self.pref_ids: pref_ids,
            self.sequence_lengths: sequence_lengths_pref,

            self.suff_ids: suff_ids,
            self.sequence_lengths: sequence_lengths_suff,

            self.pref_ids_2: pref_ids_2,
            self.sequence_lengths: sequence_lengths_pref_2,

            self.suff_ids_2: suff_ids_2,
            self.sequence_lengths: sequence_lengths_suff_2,

            self.pref_ids_4: pref_ids_4,
            self.sequence_lengths: sequence_lengths_pref_4,

            self.suff_ids_4: suff_ids_4,
            self.sequence_lengths: sequence_lengths_suff_4
        }

        if self.config.chars:
            feed[self.char_ids] = char_ids
            feed[self.word_lengths] = word_lengths
            ###
        if labels is not None:
            labels, _ = pad_sequences(labels, 0)
            feed[self.labels] = labels

        if lr is not None:
            feed[self.lr] = lr

        if dropout is not None:
            feed[self.dropout] = dropout

        return feed, sequence_lengths


    def add_word_embeddings_op(self):
        """
        Adds word embeddings to self
        """
        with tf.variable_scope("words"):
            _word_embeddings = tf.Variable(self.embeddings, name="_word_embeddings", dtype=tf.float32, 
                                trainable=self.config.train_embeddings)
            word_embeddings = tf.nn.embedding_lookup(_word_embeddings, self.word_ids, 
                name="word_embeddings")
        word_embeddings_shape = tf.shape(word_embeddings)
        #print("The shape of Word embedding is : ", word_embeddings[1])
        ########################################################### Adding embedding for Pref and Suff - randomly, same as chars

        with tf.device("/cpu:0"),tf.variable_scope("pref"):   ########### This is the original one
            _pref_embeddings = tf.get_variable(name="_pref_embeddings", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[9500, self.config.dim_pref])  ## max number of words in the sentence
            _pref_embeddings_shape = tf.shape(_pref_embeddings)
            print("The shape of Prefix embedding is : ", _pref_embeddings_shape)
            print ("Pref ids are as following:  ", self.pref_ids)
            pref_embeddings = tf.nn.embedding_lookup(_pref_embeddings, self.pref_ids,
                                                     name="pref_embeddings")

        with tf.device("/cpu:0"),tf.variable_scope("pref_2"):   ########### This is the original one
            _pref_embeddings_2 = tf.get_variable(name="_pref_embeddings_2", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[1800, self.config.dim_pref_2])  ## max number of words in the sentence
            pref_embeddings_2 = tf.nn.embedding_lookup(_pref_embeddings_2, self.pref_ids_2,
                                                     name="pref_embeddings_2")

        with tf.device("/cpu:0"),tf.variable_scope("pref_4"):   ########### This is the original one
            _pref_embeddings_4 = tf.get_variable(name="_pref_embeddings_4", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[18200, self.config.dim_pref_4])  ## max number of words in the sentence
            pref_embeddings_4 = tf.nn.embedding_lookup(_pref_embeddings_4, self.pref_ids_4,
                                                     name="pref_embeddings_4")
        """
        net = input_data(shape=[None, max_words_in_sent],dtype="float32")

        pref_embeddings = embedding(net, input_dim=6000, output_dim=self.config.dim_pref)
       
        """



        with tf.device("/cpu:0"),tf.variable_scope("suff"):
            _suff_embeddings = tf.get_variable(name="_suff_embeddings", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[9500, self.config.dim_suff])  ## max number of words in the sentence

            suff_embeddings = tf.nn.embedding_lookup(_suff_embeddings, self.suff_ids,
                                                     name="suff_embeddings")


        with tf.device("/cpu:0"),tf.variable_scope("suff_2"):
            _suff_embeddings_2 = tf.get_variable(name="_suff_embeddings_2", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[1800, self.config.dim_suff_2])  ## max number of words in the sentence

            suff_embeddings_2 = tf.nn.embedding_lookup(_suff_embeddings_2, self.suff_ids_2,
                                                     name="suff_embeddings_2")

        with tf.device("/cpu:0"),tf.variable_scope("suff_4"):
            _suff_embeddings_4 = tf.get_variable(name="_suff_embeddings_4", dtype=tf.float32,
                                               trainable=self.config.train_embeddings,shape=[18200, self.config.dim_suff_4])  ## max number of words in the sentence

            suff_embeddings_4 = tf.nn.embedding_lookup(_suff_embeddings_4, self.suff_ids_4,
                                                     name="suff_embeddings_4")

        ########################################################### Adding embedding for Pref and Suff - randomly, same as chars.
        with tf.variable_scope("chars"):
            if self.config.chars:
                # get embeddings matrix
                _char_embeddings = tf.get_variable(name="_char_embeddings", dtype=tf.float32, trainable=self.config.train_embeddings,     ########## Get embeddings for pref and suff in similar way
                    shape=[self.nchars, self.config.dim_char])
                char_embeddings = tf.nn.embedding_lookup(_char_embeddings, self.char_ids, 
                    name="char_embeddings")
                # put the time dimension on axis=1
                s = tf.shape(char_embeddings)
                print("The shape of char embedding is : ", s)

                char_embeddings = tf.reshape(char_embeddings, shape=[-1, s[-2], self.config.dim_char])   ### DOUBT- We don't have to do this step for Pref and suff emb
                word_lengths = tf.reshape(self.word_lengths, shape=[-1])
                # bi lstm on chars
                # need 2 instances of cells since tf 1.1
                cell_fw = tf.contrib.rnn.LSTMCell(self.config.char_hidden_size, 
                                                    state_is_tuple=True)
                cell_bw = tf.contrib.rnn.LSTMCell(self.config.char_hidden_size, 
                                                    state_is_tuple=True)

                _, ((_, output_fw), (_, output_bw)) = tf.nn.bidirectional_dynamic_rnn(cell_fw, 
                    cell_bw, char_embeddings, sequence_length=word_lengths, 
                    dtype=tf.float32)

                output = tf.concat([output_fw, output_bw], axis=-1)
                # shape = (batch size, max sentence length, char hidden size)
                output = tf.reshape(output, shape=[-1, s[1], 2*self.config.char_hidden_size])

                word_embeddings = tf.concat([word_embeddings,pref_embeddings,suff_embeddings, output], axis=-1)   ## Change here if you want to replicate challapti's approach  #####
                                                                                                                                                        ## ,pref_embeddings_2, suff_embeddings_2
                                                                                                                                                        ## pref_embeddings_4, suff_embeddings_4,
                                                                                                                                                        ## pref_embeddings, suff_embeddings, pref_embeddings_4, suff_embeddings_4,
        self.word_embeddings =  tf.nn.dropout(word_embeddings, self.dropout)    #### Dropout is applied after concatenating embeddings. Experiment with these vals.


    def add_logits_op(self):
        """
        Adds logits to self
        """
        with tf.variable_scope("bi-lstm"):
            cell_fw = tf.contrib.rnn.LSTMCell(self.config.hidden_size)
            cell_bw = tf.contrib.rnn.LSTMCell(self.config.hidden_size)
            (output_fw, output_bw), _ = tf.nn.bidirectional_dynamic_rnn(cell_fw, 
                cell_bw, self.word_embeddings, sequence_length=self.sequence_lengths, 
                dtype=tf.float32)
            output = tf.concat([output_fw, output_bw], axis=-1)
            output = tf.nn.dropout(output, self.dropout)

        with tf.variable_scope("proj"):
            W = tf.get_variable("W", shape=[2*self.config.hidden_size, self.ntags], 
                dtype=tf.float32)

            b = tf.get_variable("b", shape=[self.ntags], dtype=tf.float32, 
                initializer=tf.zeros_initializer())

            ntime_steps = tf.shape(output)[1]
            output = tf.reshape(output, [-1, 2*self.config.hidden_size])
            pred = tf.matmul(output, W) + b
            self.logits = tf.reshape(pred, [-1, ntime_steps, self.ntags])


    def add_pred_op(self):
        """
        Adds labels_pred to self
        """
        if not self.config.crf:
            self.labels_pred = tf.cast(tf.argmax(self.logits, axis=-1), tf.int32)


    def add_loss_op(self):
        """
        Adds loss to self
        """
        if self.config.crf:
            log_likelihood, self.transition_params = tf.contrib.crf.crf_log_likelihood(
            self.logits, self.labels, self.sequence_lengths)
            self.loss = tf.reduce_mean(-log_likelihood)
        else:
            losses = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=self.logits, labels=self.labels)
            mask = tf.sequence_mask(self.sequence_lengths)
            losses = tf.boolean_mask(losses, mask)
            self.loss = tf.reduce_mean(losses)

        # for tensorboard
        tf.summary.scalar("loss", self.loss)


    def add_train_op(self):
        """
        Add train_op to self
        """
        with tf.variable_scope("train_step"):
            # sgd method
            if self.config.lr_method == 'adam':
                optimizer = tf.train.AdamOptimizer(self.lr)
            elif self.config.lr_method == 'adagrad':
                optimizer = tf.train.AdagradOptimizer(self.lr)
            elif self.config.lr_method == 'sgd':
                optimizer = tf.train.GradientDescentOptimizer(self.lr)
            elif self.config.lr_method == 'rmsprop':
                optimizer = tf.train.RMSPropOptimizer(self.lr)
            else:
                raise NotImplementedError("Unknown train op {}".format(
                                          self.config.lr_method))

            # gradient clipping if config.clip is positive
            if self.config.clip > 0:
                gradients, variables   = zip(*optimizer.compute_gradients(self.loss))
                gradients, global_norm = tf.clip_by_global_norm(gradients, self.config.clip)
                self.train_op = optimizer.apply_gradients(zip(gradients, variables))
            else:
                self.train_op = optimizer.minimize(self.loss)


    def add_init_op(self):
        self.init = tf.global_variables_initializer()


    def add_summary(self, sess): 
        # tensorboard stuff
        self.merged = tf.summary.merge_all()
        self.file_writer = tf.summary.FileWriter(self.config.output_path, sess.graph)


    def build(self):
        self.add_placeholders()
        self.add_word_embeddings_op()
        self.add_logits_op()
        self.add_pred_op()
        self.add_loss_op()
        self.add_train_op()
        self.add_init_op()


    def predict_batch(self, sess, words):
        """
        Args:
            sess: a tensorflow session
            words: list of sentences
        Returns:
            labels_pred: list of labels for each sentence
            sequence_length
        """
        # get the feed dictionnary
        fd, sequence_lengths = self.get_feed_dict(words, dropout=1.0)

        if self.config.crf:
            viterbi_sequences = []
            #sess.run(tf.initialize_all_variables())
            logits, transition_params = sess.run([self.logits, self.transition_params],
                    feed_dict=fd)
            # iterate over the sentences
            for logit, sequence_length in zip(logits, sequence_lengths):
                # keep only the valid time steps
                logit = logit[:sequence_length]
                viterbi_sequence, viterbi_score = tf.contrib.crf.viterbi_decode(
                                logit, transition_params)
                viterbi_sequences += [viterbi_sequence]

            return viterbi_sequences, sequence_lengths

        else:
            #sess.run(tf.initialize_all_variables())
            labels_pred = sess.run(self.labels_pred, feed_dict=fd)

            return labels_pred, sequence_lengths


    def run_epoch(self, sess, train, dev, tags, epoch):
        """
        Performs one complete pass over the train set and evaluate on dev
        Args:
            sess: tensorflow session
            train: dataset that yields tuple of sentences, tags
            dev: dataset
            tags: {tag: index} dictionary
            epoch: (int) number of the epoch
        """
        nbatches = (len(train) + self.config.batch_size - 1) // self.config.batch_size
        prog = Progbar(target=nbatches)
        for i, (words, labels) in enumerate(minibatches(train, self.config.batch_size)):
            fd, _ = self.get_feed_dict(words, labels, self.config.lr, self.config.dropout)
            #sess.run(tf.initialize_all_variables())
            _, train_loss, summary = sess.run([self.train_op, self.loss, self.merged], feed_dict=fd)

            prog.update(i + 1, [("train loss", train_loss)])

            # tensorboard
            if i % 10 == 0:
                self.file_writer.add_summary(summary, epoch*nbatches + i)

        acc, f1 = self.run_evaluate(sess, dev, tags)
        self.logger.info("- dev acc {:04.2f} - f1 {:04.2f}".format(100*acc, 100*f1))
        return acc, f1


    def run_evaluate(self, sess, test, tags):
        """
        Evaluates performance on test set
        Args:
            sess: tensorflow session
            test: dataset that yields tuple of sentences, tags
            tags: {tag: index} dictionary
        Returns:
            accuracy
            f1 score
        """
        accs = []
        global Globepoch
        Globepoch += 1
        if Globepoch >= 8:
           OutFile = open("Res1/AWS_GPU_BEST_"+str(Globepoch), 'w')

        correct_preds, total_correct, total_preds = 0., 0., 0.
        for words, labels in minibatches(test, self.config.batch_size):    ## here raw words and tags from main.py is starting to get converted into word to id's and tag to id's
            labels_pred, sequence_lengths = self.predict_batch(sess, words)

            for lab, lab_pred, length in zip(labels, labels_pred, sequence_lengths):
                lab = lab[:length]
                lab_pred = lab_pred[:length]
                accs += [a==b for (a, b) in zip(lab, lab_pred)]
                lab_chunks = set(get_chunks(lab, tags))
                lab_pred_chunks = set(get_chunks(lab_pred, tags))
                test2lab=label2ind_ret()
                # print (test2lab)
                if Globepoch>= 8:
                    for lab1 in lab_pred:
                        OutFile.write(test2lab[lab1]+"\n")
                    OutFile.write("\n")

                correct_preds += len(lab_chunks & lab_pred_chunks)
                total_preds += len(lab_pred_chunks)
                total_correct += len(lab_chunks)

        p = correct_preds / total_preds if correct_preds > 0 else 0
        r = correct_preds / total_correct if correct_preds > 0 else 0
        f1 = 2 * p * r / (p + r) if correct_preds > 0 else 0
        acc = np.mean(accs)
        return acc, f1


    def train(self, train, dev, tags):
        """
        Performs training with early stopping and lr exponential decay

        Args:
            train: dataset that yields tuple of sentences, tags
            dev: dataset
            tags: {tag: index} dictionary
        """
        best_score = 0
        saver = tf.train.Saver()
        # for early stopping
        nepoch_no_imprv = 0
        with tf.Session() as sess:
            #sess.run(tf.initialize_all_variables())
            sess.run(self.init)
            if self.config.reload:
                self.logger.info("Reloading the latest trained model...")
                saver.restore(sess, self.config.model_output)
            # tensorboard
            self.add_summary(sess)
            for epoch in range(self.config.nepochs):
                self.logger.info("Epoch {:} out of {:}".format(epoch + 1, self.config.nepochs))

                acc, f1 = self.run_epoch(sess, train, dev, tags, epoch)

                # decay learning rate
                self.config.lr *= self.config.lr_decay

                # early stopping and saving best parameters
                if f1 >= best_score:
                    nepoch_no_imprv = 0
                    if not os.path.exists(self.config.model_output):
                        os.makedirs(self.config.model_output)
                    saver.save(sess, self.config.model_output)
                    best_score = f1
                    self.logger.info("- new best score!")

                else:
                    self.logger.info("current best score is "+ str (best_score))
                    nepoch_no_imprv += 1
                    if nepoch_no_imprv >= self.config.nepoch_no_imprv:
                        self.logger.info("- early stopping {} epochs without improvement".format(
                                        nepoch_no_imprv))
                        break


    def evaluate(self, test, tags):
        saver = tf.train.Saver()
        with tf.Session() as sess:
            self.logger.info("Testing model over test set")
            saver.restore(sess, self.config.model_output)
            acc, f1 = self.run_evaluate(sess, test, tags)
            self.logger.info("- test acc {:04.2f} - f1 {:04.2f}".format(100*acc, 100*f1))


    def interactive_shell(self, tags, processing_word):
        idx_to_tag = {idx: tag for tag, idx in tags.items()}
        saver = tf.train.Saver()
        with tf.Session() as sess:
            saver.restore(sess, self.config.model_output)
            self.logger.info("""
This is an interactive mode.
To exit, enter 'exit'. 
You can enter a sentence like
input> I love Paris""")
            while True:
                try:
                    try:
                        # for python 2
                        sentence = raw_input("input> ")
                    except NameError:
                        # for python 3
                        sentence = input("input> ")

                    words_raw = sentence.strip().split(" ")

                    if words_raw == ["exit"]:
                        break

                    words = [processing_word(w) for w in words_raw]
                    if type(words[0]) == tuple:
                        words = zip(*words)
                    pred_ids, _ = self.predict_batch(sess, [words])
                    preds = [idx_to_tag[idx] for idx in list(pred_ids[0])]
                    print_sentence(self.logger, {"x": words_raw, "y": preds})

                except Exception:
                    pass


    def predict_sentences(self, tags, processing_word, corpus):
        # idx_to_tag = {idx: tag for tag, idx in tags.items()}
        nonloc = tags["O"]
        iloc = tags["I-LOC"]

        saver = tf.train.Saver()
        with tf.Session() as sess:
            saver.restore(sess, self.config.model_output)
            
            files = os.listdir(corpus)

            fwriter = open(self.config.geoparsing_output, "w")

            for articleid in range(0,len(files),1):
                article_path = os.path.join(self.config.corpus_path, str(articleid))
                sentences = createMatrices(readcorpus(article_path))

                print("predicting on the {0} article".format(articleid))

                result_line = ""

                for words_raw, indexes in sentences:
                    if len(words_raw) == 1:
                        break
                    words = [processing_word(w) for w in words_raw]
                    if type(words[0]) == tuple:
                        words = zip(*words)
                    pred_ids, _ = self.predict_batch(sess, [words])
                    pred_loc_arr = list(np.where(np.array(pred_ids[0]) != nonloc)[0])
                    pred_iloc_arr = list(np.where(np.array(pred_ids[0]) == iloc)[0])

                    if len(pred_loc_arr)>=2 and len(pred_iloc_arr)>0 :

                        old_j = pred_loc_arr[0]
                        toponyms = words_raw[old_j]

                        for j in pred_loc_arr[1:]:

                            if j in pred_iloc_arr:
                                toponyms += " " + words_raw[j]
                            else:
                                # print(toponyms)
                                result_line += toponyms + ",," + toponyms + ",,30,,140,,"
                                result_line += str(indexes[old_j]) + ",," + str(indexes[old_j]+len(toponyms)-1) + "||"
                                old_j = j
                                toponyms = words_raw[j]

                        # last toponym

                        result_line += toponyms + ",," + toponyms + ",,30,,140,,"
                        result_line += str(indexes[old_j]) + ",," + str(indexes[old_j] + len(toponyms) - 1) + "||"

                    elif len(pred_loc_arr) > 0:
                        toponyms = [*map(words_raw.__getitem__, pred_loc_arr)]
                        # start_idx = [*map(test_article[i][1].__getitem__, pred_arr)][0]

                        for q, loc in enumerate(toponyms):
                            # print(loc)
                            start_index = indexes[pred_loc_arr[q]]
                            result_line += loc + ",," + loc + ",,30,,140,," + str(start_index) + ",," + str(start_index+len(loc)-1) + "||"

                fwriter.writelines(result_line + '\n')

                # if articleid == 5:
                #     break

            fwriter.close()

