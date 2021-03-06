RDEPENDS_${PN} += "\
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-image-classification-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-image-classification-python', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-object-detection-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-object-detection-python', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'armnn-tfl-cv-apps-image-classification-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'armnn-tfl-cv-apps-object-detection-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-edgetpu-image-classification-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-edgetpu-image-classification-python', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-edgetpu-object-detection-c++', '', d)} \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'tflite-cv-apps-edgetpu-object-detection-python', '', d)} \
    "
