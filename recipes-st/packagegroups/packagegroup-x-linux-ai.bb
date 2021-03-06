SUMMARY = "X-LINUX-AI full components (TFLite, armNN and application samples)"
LICENSE = "MIT & Apache-2.0 & GPLv2 & BSD-3-Clause"

LIC_FILES_CHKSUM  = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
LIC_FILES_CHKSUM += "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"
LIC_FILES_CHKSUM += "file://${COMMON_LICENSE_DIR}/GPL-2.0;md5=801f80980d171dd6425610833a22dbe6"
LIC_FILES_CHKSUM += "file://${COMMON_LICENSE_DIR}/BSD-3-Clause;md5=550794465ba0ec5312d6919e203a55f9"

PACKAGE_ARCH = "${MACHINE_ARCH}"

inherit packagegroup

PROVIDES = "${PACKAGES}"
PACKAGES = "\
    packagegroup-x-linux-ai                  \
    packagegroup-x-linux-ai-tflite           \
    packagegroup-x-linux-ai-tflite-edgetpu   \
    packagegroup-x-linux-ai-armnn-tflite     \
"

# Manage to provide all framework tools base packages with overall one
RDEPENDS_packagegroup-x-linux-ai = "\
    packagegroup-x-linux-ai-tflite           \
    packagegroup-x-linux-ai-tflite-edgetpu   \
    packagegroup-x-linux-ai-armnn-tflite     \
"

SUMMARY_packagegroup-x-linux-ai-tflite = "X-LINUX-AI TensorFlow Lite components"
RDEPENDS_packagegroup-x-linux-ai-tflite = "\
    python3-tensorflow-lite \
    tensorflow-lite-tools \
    tflite-cv-apps-image-classification-c++ \
    tflite-cv-apps-image-classification-python \
    tflite-cv-apps-object-detection-c++ \
    tflite-cv-apps-object-detection-python \
"

SUMMARY_packagegroup-x-linux-ai-tflite-edgetpu = "X-LINUX-AI TensorFlow Lite Edge TPU components"
RDEPENDS_packagegroup-x-linux-ai-tflite-edgetpu = "\
    python3-tensorflow-lite-edgetpu \
    tflite-edgetpu-benchmark \
    tflite-cv-apps-edgetpu-image-classification-c++ \
    tflite-cv-apps-edgetpu-image-classification-python \
    tflite-cv-apps-edgetpu-object-detection-c++ \
    tflite-cv-apps-edgetpu-object-detection-python \
"

SUMMARY_packagegroup-x-linux-ai-armnn-tflite = "X-LINUX-AI armNN with TensorFlow Lite parser components"
RDEPENDS_packagegroup-x-linux-ai-armnn-tflite = "\
    arm-compute-library-tools \
    armnn \
    armnn-tensorflow-lite \
    armnn-tensorflow-lite-examples \
    armnn-tfl-benchmark \
    armnn-tools \
    python3-tensorflow-lite \
    tensorflow-lite-tools \
    armnn-tfl-cv-apps-image-classification-c++ \
    armnn-tfl-cv-apps-object-detection-c++ \
"
