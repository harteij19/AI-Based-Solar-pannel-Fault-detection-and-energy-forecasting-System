# Solar PV Fault Classification Module

## Overview
This module classifies annotated solar-panel image regions using a
MobileNetV2 model trained with 30% context crops.

## Fault classes
- MultiHotSpot
- SingleHotSpot
- StringOpenCircuit

## Requirements
Python and the packages listed in requirements.txt.

Install dependencies:
    python -m pip install -r requirements.txt

## Input format
The script requires:
1. An original solar-panel image.
2. A YOLO-format label text file containing bounding boxes.

Each label line must contain:
class_id x_center y_center width height

The coordinates and dimensions must be normalized relative to the image,
as in standard YOLO label files.

## Run prediction
    python predict_final.py path/to/image.jpg path/to/labels.txt

The script prints a predicted fault class, confidence, and class
probabilities for each valid bounding box.

## Important limitations
- This classifier does not locate faults in an unannotated image.
- Bounding boxes must be provided by an annotation or detection system.
- Predictions are model outputs, not guaranteed diagnoses of real faults.
- The reported 88.32% test accuracy is the evaluation result on the
  project's test set, not a guarantee of real-world accuracy.

## Dashboard integration
The module can be integrated with the INA219 dashboard as a separate
image-classification feature. INA219 electrical readings are not inputs
to this image classifier.

The packaged model weights must remain at:
    model/FINAL_88_32_MODEL.weights.h5
