require recipes-st/images/st-image-weston.bb

SUMMARY = "OpenSTLinux Artificial Inteligence for Computer Vision image based on weston image"

IMAGE_AI_PART = "   \
    packagegroup-x-linux-ai \
"

#
# INSTALL addons
#
CORE_IMAGE_EXTRA_INSTALL += " \
    ${IMAGE_AI_PART}          \
"

CORE_IMAGE_EXTRA_INSTALL_append_stm32mp1-av96 = " av96-root-files "
