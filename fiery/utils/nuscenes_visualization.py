
# nuScenes dev-kit.
# Code written by Holger Caesar, Varun Bankiti, and Alex Lang, 2019.

import json
from lib2to3.pgen2.literals import evalString
from typing import Any

import numpy as np
from matplotlib import pyplot as plt

from nuscenes import NuScenes
from nuscenes.eval.common.data_classes import EvalBoxes
from nuscenes.eval.detection.data_classes import DetectionBox
from nuscenes.eval.common.render import setup_axis
from nuscenes.eval.common.utils import boxes_to_sensor
from nuscenes.eval.detection.constants import TP_METRICS, DETECTION_NAMES, DETECTION_COLORS, TP_METRICS_UNITS, \
    PRETTY_DETECTION_NAMES, PRETTY_TP_METRICS
from nuscenes.eval.detection.data_classes import DetectionMetrics, DetectionMetricData, DetectionMetricDataList
from nuscenes.utils.data_classes import LidarPointCloud
from nuscenes.utils.geometry_utils import view_points
from nuscenes.utils.data_classes import Box as NuScenesBox
from fiery.utils.object_evaluation_utils import lidar_egopose_to_world
from pyquaternion import Quaternion

Axis = Any

general_to_detection = {
    "human.pedestrian.adult": "pedestrian",
    "human.pedestrian.child": "pedestrian",
    # "human.pedestrian.wheelchair": "ignore",
    # "human.pedestrian.stroller": "ignore",
    # "human.pedestrian.personal_mobility": "ignore",
    "human.pedestrian.police_officer": "pedestrian",
    "human.pedestrian.construction_worker": "pedestrian",
    # "animal": "ignore",
    "vehicle.car": "car",
    "vehicle.motorcycle": "motorcycle",
    "vehicle.bicycle": "bicycle",
    "vehicle.bus.bendy": "bus",
    "vehicle.bus.rigid": "bus",
    "vehicle.truck": "truck",
    "vehicle.construction": "construction_vehicle",
    # "vehicle.emergency.ambulance": "ignore",
    # "vehicle.emergency.police": "ignore",
    "vehicle.trailer": "trailer",
    "movable_object.barrier": "barrier",
    "movable_object.trafficcone": "traffic_cone",
    # "movable_object.pushable_pullable": "ignore",
    # "movable_object.debris": "ignore",
    # "static_object.bicycle_rack": "ignore",
}


def visualize_sample(nusc: NuScenes,
                     sample_token: str,
                     pred_boxes: NuScenesBox,
                     nsweeps: int = 1,
                     conf_th: float = 0.15,
                     eval_range: float = 50,
                     verbose: bool = False,
                     savepath: str = None) -> None:
    """
    Visualizes a sample from BEV with annotations and detection results.
    :param nusc: NuScenes object.
    :param sample_token: The nuScenes sample token.
    :param gt_boxes: Ground truth boxes grouped by sample.
    :param pred_boxes: Prediction grouped by sample.
    :param nsweeps: Number of sweeps used for lidar visualization.
    :param conf_th: The confidence threshold used to filter negatives.
    :param eval_range: Range in meters beyond which boxes are ignored.
    :param verbose: Whether to print to stdout.
    :param savepath: If given, saves the the rendering here instead of displaying.
    """
    #####
    # Get Sample Record
    #####
    rec = nusc.get('sample', sample_token)
    #####
    # Get GT boxes.
    #####
    gt_boxes = []
    #####
    # global coordinate to lidartop ego coordinate
    #####
    egopose = nusc.get('ego_pose',
                       nusc.get('sample_data', rec['data']['LIDAR_TOP'])['ego_pose_token'])
    ego_translation = -np.array(egopose['translation'])
    yaw = Quaternion(egopose['rotation']).yaw_pitch_roll[0]
    ego_rotation = Quaternion(scalar=np.cos(yaw / 2), vector=[0, 0, np.sin(yaw / 2)]).inverse

    for annotation_token in rec['anns']:
        annotation = nusc.get('sample_annotation', annotation_token)
        # Get label name in detection task and filter unused labels.
        if annotation['category_name'] not in general_to_detection:
            continue
        if int(annotation['visibility_token']) == 1:
            continue

        detection_name = general_to_detection[annotation['category_name']]

        gt_box = NuScenesBox(
            center=annotation['translation'],
            size=annotation['size'],
            orientation=Quaternion(annotation['rotation']),
            # label=labels[i],
            score=-1.0,
            # velocity=nusc.box_velocity(annotation['token'])[:2],
            name=detection_name,
            token=sample_token,
        )
        # gt_box = DetectionBox(
        #     sample_token=sample_token,
        #     translation=annotation['translation'],
        #     size=annotation['size'],
        #     rotation=annotation['rotation'],
        #     velocity=nusc.box_velocity(annotation['token'])[:2],
        #     detection_name=detection_name,
        #     detection_score=-1.0,  # GT samples do not have a score.
        # )

        gt_box.translate(ego_translation)
        gt_box.rotate(ego_rotation)

        gt_boxes.append(gt_box)
    # print("gt_boxes:", gt_boxes)
    #####
    # Get Pred boxes.
    #####
    # print("pred_boxes: ", pred_boxes)
    # Init axes.
    fig, ax = plt.subplots(1, 1, figsize=(9, 9))

    # Show ego vehicle.
    ax.plot(0, 0, 'x', color='black')

    # Show GT boxes.
    for box in gt_boxes:
        box.render(ax, view=np.eye(4), colors=('g', 'g', 'g'), linewidth=2)

    # Show EST boxes.
    for box in pred_boxes:
        # Show only predictions with a high score.
        assert not np.isnan(box.score), 'Error: Box score cannot be NaN!'
        if box.score >= conf_th:
            box.render(ax, view=np.eye(4), colors=('b', 'b', 'b'), linewidth=1)

    # Limit visible range.
    axes_limit = eval_range + 3  # Slightly bigger to include boxes that extend beyond the range.
    ax.set_xlim(-axes_limit, axes_limit)
    ax.set_ylim(-axes_limit, axes_limit)

    # Show / save plot.
    if verbose:
        print('Rendering sample token %s' % sample_token)
    plt.title(sample_token)
    # if savepath is not None:
    #     plt.savefig(savepath)
    #     plt.close()
    # else:
    #     plt.show()
    return fig