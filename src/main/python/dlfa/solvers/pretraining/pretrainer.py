from keras.callbacks import EarlyStopping
import numpy

class Pretrainer:
    """
    A pretrainer takes a solver, pulls out some of the layers, makes a new model, and trains it on
    some objective with some data.  Theoretically, you could train the whole model on the same
    objective as the solver does, but that would be "training", not "pretraining", so the idea here
    is that something is different from the main training step.

    A _really_ important point: any layer from the model that you pull out here has to be saved in
    the solver as a member variable!  If it is not, you could easily think you're pretraining a
    layer, but not actually changing the weights used in the solver itself, because the solver will
    just re-build that layer with new weights during the training step.
    """
    # TODO(matt): this ended up being _really_ similar to the NNSolver code.  I've been wanting to
    # make the data loading code in NNSolver better, anyway; we should probably pull out all of the
    # common code here into a Trainer class that both of these can inherit from.

    # While it's not great, we need access to a few of the internals of the solver, so we'll
    # disable protected access checks.
    # pylint: disable=protected-access
    def __init__(self, solver, **kwargs):
        self.solver = solver
        self.num_epochs = kwargs.get('num_epochs', 30)
        self.validation_split = kwargs.get('validation_split', .1)
        self.early_stopping = kwargs.get('early_stopping', True)
        self.patience = kwargs.get('patience', 3)

        # We're expecting most pretrainers to want this loss function.  You can override it in a
        # subclass if you want.  The loss depends on the data and model you're using, so it makes
        # more sense to specify as a member variable (or a private method) than as a parameter.
        self.loss = "categorical_crossentropy"
        self.dataset = None

    def fit_data_indexer(self, data_indexer):
        dataset = self.get_dataset()
        data_indexer.fit_word_dictionary(dataset)

    def _load_dataset(self):
        """
        Actually does the work for self.get_dataset(), reading a file and returning a TextDataset
        object.
        """
        raise NotImplementedError

    def get_dataset(self):
        """
        Returns a TextDataset with the data that will be used during pre-training.
        """
        if self.dataset is None:
            self.dataset = self._load_dataset()
        return self.dataset

    def _get_model(self):
        """
        Build a model for pre-training, by pulling out some pieces of self.solver.
        """
        raise NotImplementedError

    def train(self):
        """
        Given some data and training parameters specified in constructor, run pre-training.  When
        this is done, the weights in the solver layers will have been updated during training, and
        you can just keep going with solver.train(), and things will just work.
        """
        dataset = self.get_dataset()
        indexed_dataset = dataset.to_indexed_dataset(self.solver.data_indexer)
        indexed_dataset.pad_instances(self.solver._get_max_lengths())

        inputs, labels = indexed_dataset.as_training_data()
        if isinstance(inputs[0], tuple):
            inputs = [numpy.asarray(x) for x in zip(*inputs)]
        else:
            inputs = numpy.asarray(inputs)
        labels = numpy.asarray(labels)

        model = self._get_model()
        model.summary()
        model.compile(loss=self.loss, optimizer='adam', metrics=['accuracy'])

        fit_kwargs = {
                'nb_epoch': self.num_epochs,
                }
        if self.validation_split > 0.0:
            fit_kwargs['validation_split'] = self.validation_split
        if self.early_stopping:
            early_stopping = EarlyStopping(monitor='val_loss', patience=self.patience)
            fit_kwargs['callbacks'] = [early_stopping]
        model.fit(inputs, labels, **fit_kwargs)
