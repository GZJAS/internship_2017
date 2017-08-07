"""Contains common routines used for evaluating a model.

In practice, one should define a subclass inheriting from the class
`Evaluate` by giving definitions to `get_data`, `step_log_info`
and `compute`

Other methods may also be defined depending on different use cases.
See `EvaluateClassifyImagesCNN` for an evaluation class that implements
all these methods and can be used directly.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from six.moves import xrange
import abc

import numpy as np
import tensorflow as tf

from nets_base.arg_scope import nets_arg_scope

slim = tf.contrib.slim


class EvaluateAbstract(object):
    """The interface/abstract class of the evaluation framework.

    Note here we just put some methods that should be defined for
    evaluation classes, for detailed implementation please refer to the
    class `Evaluate` and its subclasses. The docstrings of subclasses
    sometimes also contain more information.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def evaluate(self, *args):
        """The main method that should be called when we evaluate a model."""
        pass

    @abc.abstractmethod
    def get_data(self, split_name, tfrecord_dir, batch_size):
        """Read data from some directory and load them in batches.

        Args:
            tfrecord_dir: The directory where the tfrecords of the
                dataset are stored.
            batch_size: The number of elements contained in each batch.
        """
        pass

    @abc.abstractmethod
    def used_arg_scope(self, batch_stat, use_batch_norm):
        """The slim argument scope that is used for main computations.

        Args:
            use_batch_norm: Whether to do batch normalization or not.
            renorm: Whether to do batch renormalization or not. I've in
                fact never used it.

        Returns:
            An argument scope to be used for model computations.
        """
        pass

    @abc.abstractmethod
    def compute(self, *args):
        """Compute necessary values of the model.

        The content of this function can vary a lot from case to case and
        we don't have some fixed arguments for this functions. For example,
        for classification normally it's used to compute the probabilities
        that an instance belongs to each class, and for auto-encoder it's
        used to compute the reconstruction of input.
        """
        pass

    @abc.abstractmethod
    def init_model(self, sess, checkpoint_dirs):
        """Initialize the model from a/several training directory(ies).

        Args:
            sess: The session in which we run the initialization.
            checkpoint_dirs: The directory(ies) containing the trained
                models to be evaluated.
        """
        pass

    @abc.abstractmethod
    def step_log_info(self, sess):
        """Things to be done at every evaluation step."""
        pass

    @abc.abstractmethod
    def last_step_log_info(self, sess, batch_size):
        """Things to be done at the very last step (show some extra info)."""
        pass

    def compute_log_data(self):
        """Compute some values that are used for evaluation."""
        pass


class Evaluate(EvaluateAbstract):
    """Implementation of the interface `EvaluateAbstract`.

    In practice, one should define a subclass inheriting from this class
    and implement `get_data`, `compute` and `step_log_info`.

    Other methods like `last_step_log_infor`, `compute_log_data`,
    `init_model` etc. can also be overrided or added.

    See `EvaluateClassifyImagesCNN` for a evaluation class that implements
    all these methods and can be used directly.
    """

    def evaluate(self,
                 tfrecord_dir,
                 checkpoint_dirs,
                 log_dir=None,
                 number_of_steps=None,
                 batch_size=24,
                 split_name='validation',
                 shuffle=False,
                 use_batch_norm=True,
                 batch_stat=False,
                 **kwargs):
        """Evaluate the model.

        Args:
            tfrecord_dir: The directory that contains the dataset tfreocrds
                (which can be generated by `convert_TFrecord` scripts).
            checkpoints_dir: The directorys containing checkpoints of
                the trained models to do evaluation.
            log_dir: The directory to log event files.
            number_of_steps: number of steps to run the evaluation
                (one step = one batch), if `None` then run through
                the whole dataset.
            batch_size: The batch size used for each step of evaluation.
                If `None` then evaluate all the data in one time.
            split_name: The part of the dataset to use.
            shuffle: Whether to shuffle the data for the evaluation.
            use_batch_norm: Passes to `self.used_arg_scope` to decide
                whether to use batch normalization.
            batch_stat: Whether to use batch statistics or moving
                mean/variance.
            **kwargs: Arguments pass to the `self.compute`.
        """
        if log_dir is not None and not tf.gfile.Exists(log_dir):
            tf.gfile.MakeDirs(log_dir)

        if not isinstance(checkpoint_dirs, (tuple, list)):
            checkpoint_dirs = [checkpoint_dirs]

        with tf.Graph().as_default():
            tf.logging.set_verbosity(tf.logging.INFO)

            # Read the data
            with tf.name_scope('Data_provider'):
                dataset = self.get_data(
                    split_name, tfrecord_dir, batch_size, shuffle)

            # Read all data in one time if `batch_size` is `None`
            if batch_size is None:
                batch_size = dataset.num_samples

            # Run through the whole dataset when `number_of_steps` is not given
            if number_of_steps is None:
                number_of_steps = int(np.ceil(dataset.num_samples/batch_size))

            # Create the model, use the default arg scope to configure the
            # batch norm parameters
            with slim.arg_scope(self.used_arg_scope(
                    batch_stat, use_batch_norm)):
                self.compute(**kwargs)

            self.compute_log_data()

            # Define global step to be show in tensorboard
            global_step = tf.train.get_or_create_global_step()
            self.global_step_op = tf.assign(global_step, global_step+1)

            # File writer for the tensorboard
            if log_dir is not None:
                self.fw = tf.summary.FileWriter(log_dir)

            with tf.Session() as sess:
                with slim.queues.QueueRunners(sess):
                    sess.run(tf.variables_initializer([global_step]))
                    self.init_model(sess, checkpoint_dirs)

                    for step in xrange(number_of_steps-1):
                        self.step_log_info(sess)
                    self.last_step_log_info(sess, batch_size)
                    tf.logging.info('Finished evaluation')

    def used_arg_scope(self, batch_stat, use_batch_norm):
        """The slim argument scope that is used for main computations.

        It includes weight regularization, batch normalization and
        proper initialization.

        Args:
            use_batch_norm: Whether to do batch normalization or not.
            renorm: Whether to do batch renormalization or not. I've in
                fact never used it.

        Returns:
            An argument scope to be used for model computations.
        """
        return nets_arg_scope(
            is_training=batch_stat, use_batch_norm=use_batch_norm)

    def last_step_log_info(self, sess, batch_size):
        """Generally just act as natural step."""
        return self.step_log_info(sess)

    def init_model(self, sess, checkpoint_dirs):
        """Simply restore the whole model from the checkpoint."""
        assert len(checkpoint_dirs) == 1
        checkpoint_path = tf.train.latest_checkpoint(checkpoint_dirs[0])
        saver = tf.train.Saver(tf.model_variables())
        saver.restore(sess, checkpoint_path)


def evaluate(evaluate_class,
             used_architecture,
             tfrecord_dir,
             checkpoint_dirs,
             log_dir,
             number_of_steps=None,
             **kwargs):
    evaluate_instance = evaluate_class(used_architecture)
    for key in kwargs.copy():
        if hasattr(evaluate_instance, key):
            setattr(evaluate_instance, key, kwargs[key])
            del kwargs[key]
    evaluate_instance.evaluate(
        tfrecord_dir, checkpoint_dirs, log_dir,
        number_of_steps=number_of_steps, **kwargs)
