#!/bin/sh
python3 /usr/local/demo-ai/computer-vision/tflite-object-detection/python/objdetect_tfl_multiprocessing.py -m /usr/local/demo-ai/computer-vision/models/coco_ssd_mobilenet/detect.tflite -l /usr/local/demo-ai/computer-vision/models/coco_ssd_mobilenet/labels.txt -v 0
