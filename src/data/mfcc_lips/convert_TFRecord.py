"""Convert TFRecords for the AVSR transfer learning experiment.

This is an ad hoc script to split the AVLetters dataset in different
subsets for the transfer learning experiment according to what's
described in my report.

The generated TFRecords have six different parts, 'train_all', 'trainAT'
'trainUZ', 'validation', 'validaionAT' and 'validationUZ'.
Each single sample contains the mfcc features, lip movement image sequence
and the label.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys
import math
import random

import tensorflow as tf
from data import dataset_utils
from data.mfcc import parse_mfcc
from data.lips import read_mat


def to_tfexample(mfcc_data, video_data, class_id):
    return tf.train.Example(features=tf.train.Features(feature={
        'audio/mfcc': dataset_utils.float_feature(mfcc_data),
        'video/data': dataset_utils.float_feature(video_data),
        'label': dataset_utils.int64_feature(class_id)
    }))


def get_tfrecord_filename(split_name, tfrecord_dir, shard_id, num_shards):
    output_filename = 'mfcc_lips_%s_%d-of-%d.tfrecord' % (
        split_name, shard_id, num_shards)
    return os.path.join(tfrecord_dir, output_filename)


def convert_dataset(split_name,
                    filepath_pairs,
                    class_names_to_ids,
                    tfrecord_dir,
                    num_shards=5,
                    feature_len_audio=26,
                    num_frames_audio=24,
                    num_frames_video=12):
    """Converts the given filenames to a TFRecord dataset.

    Args:
        split_name: The name of the dataset, either 'train' or 'validation'.
        filepath_pairs: A list of path pairs to mfcc and .mat video files.
        class_names_to_ids: A dictionary from class names (strings) to ids
            (integers).
        tfrecord_dir: The directory where the converted datasets are stored.
        num_shards: The number of shards per dataset split.
        feature_len_audio: The feature length of each time frame (this
            is fixed by the dataset and shouldn't be changed here).
        num_frames_audio: The number of frames of the stored audios.
        num_frames_video: The number of frames of the stored videos.
    """
    num_per_shard = int(math.ceil(len(filepath_pairs)/float(num_shards)))

    with tf.Graph().as_default():

        for shard_id in range(num_shards):
            output_filename = get_tfrecord_filename(
                split_name, tfrecord_dir, shard_id, num_shards)

            with tf.python_io.TFRecordWriter(output_filename)\
                    as tfrecord_writer:
                start_ndx = shard_id * num_per_shard
                end_ndx = min((shard_id+1)*num_per_shard, len(filepath_pairs))
                for i in range(start_ndx, end_ndx):
                    sys.stdout.write(
                        '\r>> Converting file %d/%d shard %s %d' % (
                            i+1, len(filepath_pairs), split_name, shard_id))
                    sys.stdout.flush()

                    audio_path = filepath_pairs[i][0]
                    video_path = filepath_pairs[i][1]

                    mfcc = parse_mfcc(
                        audio_path,
                        feature_len=feature_len_audio,
                        num_frames=num_frames_audio)
                    mfcc_data = list(mfcc.reshape(-1))
                    video_data = list(read_mat(
                        video_path, num_frames=num_frames_video).reshape(-1))

                    class_name = os.path.basename(audio_path)[0]
                    class_id = class_names_to_ids[class_name]

                    example = to_tfexample(mfcc_data, video_data, class_id)
                    tfrecord_writer.write(example.SerializeToString())

    sys.stdout.write('\n')
    sys.stdout.flush()


def convert_mfcc_lips(dataset_dir_audio,
                      dataset_dir_video,
                      tfrecord_dir,
                      num_shards=5,
                      num_val_samples=100,
                      num_frames_audio=24,
                      num_frames_video=12):
    """Runs the conversion operation.

    Args:
        dataset_dir_audio: Where the audio data (mfcc ascii) is stored.
        dataset_dir_video: Where the video data (.mat) is stored.
        tfrecord_dir: Where to store the generated data (i.e. TFRecords).
        num_shards: The number of shards per dataset split.
        num_val_samples: The number of samples in 'validation' part.
        num_frames_audio: The number of frames of the stored audios.
        num_frames_video: The number of frames of the stored videos.
    """
    if not tf.gfile.Exists(tfrecord_dir):
        tf.gfile.MakeDirs(tfrecord_dir)

    filename_pairs = []

    for split_name in ['train', 'validation']:
        dirname = os.path.join(dataset_dir_audio, split_name)
        audio_filenames = sorted(
            [os.path.join(dirname, filename)
             for filename in os.listdir(dirname)])
        dirname = os.path.join(dataset_dir_video, split_name)
        video_filenames = sorted(
            [os.path.join(dirname, filename)
             for filename in os.listdir(dirname)])
        filename_pairs.extend(
            list(zip(audio_filenames, video_filenames)))

    alphabets = [chr(i) for i in range(ord('A'), ord('Z')+1)]
    class_names_to_ids = dict(zip(alphabets, range(26)))

    random.shuffle(filename_pairs)
    training_pairs = filename_pairs[:-num_val_samples]
    validation_pairs = filename_pairs[-num_val_samples:]

    train_AT_pairs = []
    train_UZ_pairs = []
    for p in training_pairs:
        if 'U' <= os.path.basename(p[0])[0] <= 'Z':
            train_UZ_pairs.append(p)
        else:
            train_AT_pairs.append(p)

    validation_AT_pairs = []
    validation_UZ_pairs = []
    for p in validation_pairs:
        if 'U' <= os.path.basename(p[0])[0] <= 'Z':
            validation_UZ_pairs.append(p)
        else:
            validation_AT_pairs.append(p)

    split_names = [
        'train_all', 'trainAT', 'trainUZ',
        'validation', 'validationAT', 'validationUZ'
    ]
    pairs = [
        training_pairs, train_AT_pairs, train_UZ_pairs,
        validation_pairs, validation_AT_pairs, validation_UZ_pairs
    ]

    for i in range(6):
        convert_dataset(split_names[i], pairs[i],
                        class_names_to_ids,
                        tfrecord_dir,
                        num_shards=num_shards,
                        num_frames_audio=num_frames_audio,
                        num_frames_video=num_frames_video)

    labels_to_class_names = dict(zip(range(26), alphabets))
    dataset_utils.write_label_file(labels_to_class_names, tfrecord_dir)

    print('\nFinished converting dataset!')
