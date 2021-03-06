#!/usr/bin/env python

import os
import argparse
import numpy as np
from collections import defaultdict
from tensorflow.python.summary.summary_iterator import summary_iterator
import pandas as pd
import matplotlib.pyplot as plt
from textwrap import wrap


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, type=str,
                        help="Input log directory. If using --multiple, this parameter indicates the suffix path of all"
                             " log directories of interest. To compare trainings or set of trainings (using "
                             "``--multiple``) with subplots, please list the paths by separating them with commas, eg "
                             "path_log_dir1,path_logdir2.")
    parser.add_argument("--multiple", required=False, dest="multiple", action='store_true',
                        help="Multiple log directories are considered: all available folders with -i as "
                             "prefix. The plot represents the mean value (hard line) surrounded by the standard "
                             "deviation envelope.")
    parser.add_argument("-y", "--ylim_loss", required=False, type=str,
                        help="Indicates the limits on the y-axis for the loss plots, otherwise these limits are "
                             "automatically defined. Please separate the lower and the upper limit by a comma, eg -1,0."
                             "Note: for the validation metrics: the y-limits are always 0.0 and 1.0.")
    parser.add_argument("-o", "--output", required=True, type=str,
                        help="Output folder.")
    return parser


def find_events(input_folder):
    """Get TF events path from input_folder.

    Args:
        input_folder (str): Input folder path.
    Returns:
        dict: keys are subfolder names and values are events' paths.
    """
    dict = {}
    for fold in os.listdir(input_folder):
        fold_path = os.path.join(input_folder, fold)
        if os.path.isdir(fold_path):
            event_list = [f for f in os.listdir(fold_path) if f.startswith("events.out.tfevents.")]
            if len(event_list):
                if len(event_list) > 1:
                    print('Multiple events found in this folder: {}.\nPlease keep only one before running '
                          'this script again.'.format(fold_path))
                dict[fold] = os.path.join(input_folder, fold, event_list[0])
    return dict


def get_data(event_dict):
    """Get data as Pandas dataframe.

    Args:
        event_dict (dict): Dictionary containing the TF event names and their paths.
    Returns:
        Pandas Dataframe: where the columns are the metrics or losses and the rows represent the epochs.
    """
    metrics = defaultdict(list)
    for tf_tag in event_dict:
        for e in summary_iterator(event_dict[tf_tag]):
            for v in e.summary.value:
                if isinstance(v.simple_value, float):
                    if tf_tag.startswith("Validation_Metrics_"):
                        tag = tf_tag.split("Validation_Metrics_")[1]
                    elif tf_tag.startswith("losses_"):
                        tag = tf_tag.split("losses_")[1]
                    else:
                        print("Unknown TF tag: {}.".format(tf_tag))
                        exit()
                    metrics[tag].append(v.simple_value)
    metrics_df = pd.DataFrame.from_dict(metrics)
    return metrics_df


def plot_curve(data_list, y_label, fig_ax, subplot_title, y_lim=None):
    """Plot curve of metrics or losses for each epoch.

    Args:
        data_list (list): list of pd.DataFrame, one for each log_directory
        y_label (str): Label for the y-axis.
        fig_ax (plt.subplot):
        subplot_title (str): Title of the subplot
        y_lim (list): List of the lower and upper limits of the y-axis.
    """
    # Create count of the number of epochs
    max_nb_epoch = max([len(data_list[i]) for i in range(len(data_list))])
    epoch_count = range(1, max_nb_epoch + 1)

    for k in data_list[0].keys():
        data_k = pd.concat([data_list[i][k] for i in range(len(data_list))], axis=1)
        mean_data_k = data_k.mean(axis=1, skipna=True)
        std_data_k = data_k.std(axis=1, skipna=True)
        std_minus_data_k = (mean_data_k - std_data_k).tolist()
        std_plus_data_k = (mean_data_k + std_data_k).tolist()
        mean_data_k = mean_data_k.tolist()
        fig_ax.plot(epoch_count, mean_data_k, )
        fig_ax.fill_between(epoch_count, std_minus_data_k, std_plus_data_k, alpha=0.3)

    fig_ax.legend(data_list[0].keys(), loc="best")
    fig_ax.grid(linestyle='dotted')
    fig_ax.set_xlabel('Epoch')
    fig_ax.set_ylabel(y_label)
    if y_lim is not None:
        fig_ax.set_ylim(y_lim)
    fig_ax.set_xlim([1, max_nb_epoch])
    fig_ax.title.set_text('\n'.join(wrap(subplot_title, 80)))


def run_plot_training_curves(input_folder, output_folder, multiple_training=False, y_lim_loss=None):
    """Utility function to plot the training curves.

    This function uses the TensorFlow summary that is generated during a training to plot for each epoch:
        - the training against the validation loss
        - the metrics computed on the validation sub-dataset.

    It could consider one log directory at a time, for example::
    .. image:: ../../images/plot_loss_single.png
        :width: 600px
        :align: center

    ... or multiple (using ``multiple_training=True``). In that case, the hard line represent the mean value across the
    trainings whereas the envelope represents the standard deviation::
    .. image:: ../../images/plot_loss_multiple.png
        :width: 600px
        :align: center

    It is also possible to compare multiple trainings (or set of trainings) by listing them in ``-i``, separeted by
    commas::
        .. image:: ../../images/plot_loss_mosaic.png
        :width: 600px
        :align: center

    Args:
        input_folder (str): Log directory name. Flag: --input, -i. If using ``--multiple``, this parameter indicates the
            suffix path of all log directories of interest. To compare trainings or set of trainings (using
            ``--multiple``) with subplots, please list the paths by separating them with commas, eg
            path_log_dir1,path_logdir2
        output_folder (str): Output folder. Flag: --output, -o.
        multiple_training (bool): Indicates if multiple log directories are considered (``True``) or not (``False``).
            Flag: --multiple. All available folders with ``-i`` as prefix are considered. The plot represents the mean
            value (hard line) surrounded by the standard deviation (envelope).
        y_lim_loss (list): List of the lower and upper limits of the y-axis of the loss plot.
    """
    group_list = input_folder.split(",")
    plt_dict = {}

    # Create output folder
    if os.path.isdir(output_folder):
        print("Output folder already exists: {}.".format(output_folder))
    else:
        print("Creating output folder: {}.".format(output_folder))
        os.makedirs(output_folder)

    # Config subplots
    if len(group_list) > 1:
        n_cols = 2
        n_rows = int(np.ceil(len(group_list) / float(n_cols)))
    else:
        n_cols, n_rows = 1, 1

    for i_subplot, input_folder in enumerate(group_list):
        input_folder = os.path.expanduser(input_folder)
        # Find training folders:
        if multiple_training:
            prefix = str(input_folder.split('/')[-1])
            input_folder = '/'.join(input_folder.split('/')[:-1])
            input_folder_list = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.startswith(prefix)]
        else:
            prefix = str(input_folder.split('/')[-1])
            input_folder_list = [input_folder]

        events_df_list = []
        for log_directory in input_folder_list:
            # Find tf folders
            events_dict = find_events(log_directory)

            # Get data as dataframe
            events_vals_df = get_data(events_dict)

            # Store data
            events_df_list.append(events_vals_df)

        # Plot train and valid losses together
        loss_keys = [k for k in events_df_list[0].keys() if k.endswith("loss")]
        if i_subplot == 0:  # Init plot
            plt_dict[os.path.join(output_folder, "losses.png")] = plt.figure(figsize=(10 * n_cols, 5 * n_rows))
        ax = plt_dict[os.path.join(output_folder, "losses.png")].add_subplot(n_rows, n_cols, i_subplot + 1)
        plot_curve([df[loss_keys] for df in events_df_list],
                   y_label="loss",
                   fig_ax=ax,
                   subplot_title=prefix,
                   y_lim=y_lim_loss)

        # Plot each validation metric separetly
        for tag in events_df_list[0].keys():
            if not tag.endswith("loss"):
                if i_subplot == 0:  # Init plot
                    plt_dict[os.path.join(output_folder, tag+".png")] = plt.figure(figsize=(10 * n_cols, 5 * n_rows))
                ax = plt_dict[os.path.join(output_folder, tag+".png")].add_subplot(n_rows, n_cols, i_subplot+1)
                plot_curve(data_list=[df[[tag]] for df in events_df_list],
                           y_label=tag,
                           fig_ax=ax,
                           subplot_title=prefix,
                           y_lim=[0, 1])

    for fname_out in plt_dict:
        plt_dict[fname_out].savefig(fname_out)


def main():
    parser = get_parser()
    args = parser.parse_args()
    input_folder = args.input
    multiple = args.multiple
    output_folder = args.output
    y_lim_loss = [int(y) for y in args.ylim_loss.split(',')] if args.ylim_loss else None

    # Run script
    run_plot_training_curves(input_folder, output_folder, multiple, y_lim_loss)


if __name__ == '__main__':
    main()
