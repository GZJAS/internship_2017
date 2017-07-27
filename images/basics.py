from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from routines.train import Train
from data.images import load_batch_images, get_split_images


class TrainImages(Train):

    def __init__(self, image_size=299, channels=3, **kwargs):
        super(TrainImages, self).__init__(**kwargs)
        self.image_size = image_size
        self.channels = channels

    def get_data(self, tfrecord_dir, batch_size):
        self.dataset_train = get_split_images(
            'train', tfrecord_dir, channels=self.channels)
        self.images_train, self.labels_train = load_batch_images(
            self.dataset_train, height=self.image_size,
            width=self.image_size, batch_size=batch_size)
        self.dataset_test = get_split_images(
            'validation', tfrecord_dir, channels=self.channels)
        self.images_test, self.labels_test = load_batch_images(
            self.dataset_test, height=self.image_size,
            width=self.image_size, batch_size=batch_size)
        return self.dataset_train