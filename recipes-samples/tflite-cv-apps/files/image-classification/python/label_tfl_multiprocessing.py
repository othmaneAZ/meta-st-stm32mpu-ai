#!/usr/bin/python3
#
# Copyright (c) 2020 STMicroelectronics. All rights reserved.
#
# This software component is licensed by ST under BSD 3-Clause license,
# the "License"; You may not use this file except in compliance with the
# License. You may obtain a copy of the License at:
#                        opensource.org/licenses/BSD-3-Clause
#

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GdkPixbuf

import numpy as np
import argparse
import time
import ctypes
import signal
import sys
import os
import random

from threading import Thread
from multiprocessing import set_start_method
from multiprocessing import Process, Event, Array, Value
import cv2

from PIL import Image
import tflite_runtime.interpreter as tflr

from timeit import default_timer as timer

class VideoFrameCapture:
    """
    Class that handles video capture from device
    """
    def __init__(self, device=0, width=320, height=240, fps=15):
        """
        :param device: device index or video filename
        :param width:  width of the requested frame
        :param height: heigh of the requested frame
        :param fps:    framerate of the camera
        """
        self._device = device
        self._width = width
        self._height = height
        self._fps = fps
        self._cap = cv2.VideoCapture(device)
        assert self._cap.isOpened()

    def __getstate__(self):
        self._cap.release()
        return (self._device, self._width, self._height, self._fps)

    def __setstate__(self, state):
        self._device, self._width, self._height, self._fps = state
        self._cap = cv2.VideoCapture(self._device)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        assert self._cap.grab(), "The child could not grab the video capture"

    def get_frame(self):
        """
        :param delay: delay between frames capture(in seconds)
        :return: frame
        """
        frame = None
        correct_frame = False
        fail_counter = -1
        while not correct_frame:
            # capture the frame
            correct_frame, frame = self._cap.read()
            fail_counter += 1
            # raise exception if there's no output from the device
            if fail_counter > 10:
                raise Exception("Capture: exceeded number of tries to capture "
                                "the frame.")
        return frame

    def get_frame_size(self):
        """
        :return: size of the captured image
        """
        return (int(self._height), int(self._width), 3)

    def release(self):
        self._cap.release()

class NeuralNetwork:
    """
    Class that handles Neural Network inference
    """
    def __init__(self, model_file, label_file, input_mean, input_std):
        """
        :param model_path: .tflite model to be executedname of file containing labels")
        :param label_file:  name of file containing labels
        :param input_mean: input_mean
        :param input_std: input standard deviation
        """
        def load_labels(filename):
            my_labels = []
            input_file = open(filename, 'r')
            for l in input_file:
                my_labels.append(l.strip())
            return my_labels

        self._model_file = model_file
        self._label_file = label_file
        self._input_mean = input_mean
        self._input_std = input_std
        self._floating_model = False

        self._interpreter = tflr.Interpreter(self._model_file)

        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

        # check the type of the input tensor
        if self._input_details[0]['dtype'] == np.float32:
            self._floating_model = True
            print("Floating point Tensorflow Lite Model")

        self._labels = load_labels(self._label_file)

    def __getstate__(self):
        return (self._model_file, self._label_file, self._input_mean,
                self._input_std, self._floating_model,
                self._input_details, self._output_details, self._labels)

    def __setstate__(self, state):
        self._model_file, self._label_file, self._input_mean, \
                self._input_std, self._floating_model, \
                self._input_details, self._output_details, self._labels = state

        self._interpreter = tflr.Interpreter(self._model_file)
        self._interpreter.allocate_tensors()

    def get_labels(self):
        return self._labels

    def get_img_size(self):
        """
        :return: size of NN input image size
        """
        # NxHxWxC, H:1, W:2, C:3
        return (int(self._input_details[0]['shape'][1]),
                int(self._input_details[0]['shape'][2]),
                int(self._input_details[0]['shape'][3]))

    def launch_inference(self, img):
        # add N dim
        input_data = np.expand_dims(img, axis=0)

        if self._floating_model:
            input_data = (np.float32(input_data) - self._input_mean) / self._input_std

        self._interpreter.set_tensor(self._input_details[0]['index'], input_data)

        self._interpreter.invoke()

    def display_results(self):
        # display output results
        output_data = self._interpreter.get_tensor(self._output_details[0]['index'])
        results = np.squeeze(output_data)

        top_k = results.argsort()[-5:][::-1]
        for i in top_k:
            if self._floating_model:
                print('{0:08.6f}'.format(float(results[i]))+":", self._labels[i])
            else:
                print('{0:08.6f}'.format(float(results[i]/255.0))+":", self._labels[i])
        print("\n")

        if self._floating_model:
            return (results[top_k[0]], top_k[0])
        else:
            return (results[top_k[0]]/255.0, top_k[0])

def camera_streaming(cap,
                     preview_frame,
                     synchro_event,
                     grabbing_fps):
    """
    Function keeps capturing frames until process is killed (terminated)
    :param preview_frame: shared numpy array for multiprocessing
    :param synchro_event: used to synchronize parent and child process
    :return: nothing
    """

    #variable to compute grabbing framerate
    loop_count = 1
    loop_time = 0
    loop_start = 0
    total_time = 0

    shape = cap.get_frame_size()

    # define shared variables
    frame = np.ctypeslib.as_array(preview_frame.get_obj())
    frame = frame.reshape(shape[0], shape[1], shape[2])

    # incorrect input array
    if frame.shape != cap.get_frame_size():
        raise Exception("Capture: improper size of the input preview_frame")

    # send the synchro event to warn the main process
    print("camera_streaming process started")
    synchro_event.set()

    # capture frame in a infinite loop
    while True:
        #compute preview FPS
        loop_stop = timer();
        loop_time = loop_stop - loop_start
        loop_start = loop_stop
        total_time = total_time + loop_time
        if loop_count==15:
            grabbing_fps.value = loop_count / total_time
            loop_count = 0
            total_time = 0
        loop_count = loop_count + 1

        frame[:, :, :] = cap.get_frame()

    # release the device
    cap.release()
    print("camera_streaming process stoped")

def nn_processing(nn,
                  nn_image,
                  nn_processing_start,
                  nn_processing_finished,
                  inference_time,
                  accuracy,
                  label,
                  synchro_event,
                  inference_fps):
    """
    Function keeps capturing frames until process is killed (terminated)
    :param nn_image: shared numpy array for multiprocessing
    :param nn_processing_start: variable to warn that NN processing can start
    :param nn_processing_finished: varialbe to warn NN processing is finished
    :param synchro_event: used to synchronize parent and child process
    :return: nothing
    """

    #variable to compute inference framerate
    loop_count = 1
    loop_time = 0
    loop_start = 0
    total_time = 0

    shape = nn.get_img_size()

    # send the synchro event to warn the main process
    print("nn_processing process started")
    synchro_event.set()

    # enter the infinite while loop
    while True:
        if nn_processing_start.value == True:
            nn_processing_start.value = False

            #compute inference FPS
            loop_stop = timer();
            loop_time = loop_stop - loop_start
            loop_start = loop_stop
            total_time = total_time + loop_time
            if loop_count==5:
                inference_fps.value = loop_count / total_time
                loop_count = 0
                total_time = 0
            loop_count = loop_count + 1

            # define shared variables
            nn_img = np.ctypeslib.as_array(nn_image.get_obj())
            nn_img = nn_img.reshape(shape[0], shape[1], shape[2])

            # transform the nn_img array into image for NN
            img = Image.fromarray(nn_img)

            start_time = timer()

            # execute NN inference
            nn.launch_inference(img)

            stop_time = timer()
            inference_time.value = stop_time - start_time
            print("\nProcessing time = %.3f s" % inference_time.value)

            # display NN inference results
            accuracy.value, label.value = nn.display_results()

            nn_processing_finished.value = True

    print("nn_processing process stoped")


class MainUIWindow(Gtk.Window):
    def __init__(self, args):
        Gtk.Window.__init__(self)

        # set the title bar
        self.headerbar = Gtk.HeaderBar()
        Gtk.HeaderBar.set_has_subtitle(self.headerbar, True)
        Gtk.HeaderBar.set_title(self.headerbar, "TensorFlow Lite")
        Gtk.HeaderBar.set_show_close_button(self.headerbar, False)
        self.set_titlebar(self.headerbar)

        # add close button
        self.close_button = Gtk.Button.new_with_label("Close")
        self.close_button.connect("clicked", self.close)
        self.headerbar.pack_end(self.close_button)

        if args.image == "":
            self.enable_camera_preview = True
        else:
            self.enable_camera_preview = False

        GdkDisplay = Gdk.Display.get_default()
        monitor = Gdk.Display.get_monitor(GdkDisplay, 0)
        workarea = Gdk.Monitor.get_workarea(monitor)

        self.maximize()
        self.screen_width = workarea.width
        self.screen_height = workarea.height

        if self.screen_width == 720:
            self.picture_width = 480
            self.picture_height = 360
        else:
            self.picture_width = 320
            self.picture_height = 240

        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('destroy', Gtk.main_quit)

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        self.progressbar = Gtk.ProgressBar()
        self.vbox.pack_start(self.progressbar, False, False, 15)

        self.hbox = Gtk.HBox()
        self.vbox.pack_start(self.hbox, False, False, 15)

        self.image = Gtk.Image()
        self.hbox.pack_start(self.image, False, False, 15)

        self.label = Gtk.Label()
        self.label.set_size_request(400, -1) # -1 to keep height automatic
        self.label.set_xalign(0)
        self.label.set_yalign(0)
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Gtk.WrapMode.WORD)
        self.hbox.pack_start(self.label, False, False, 15)

        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

    def close(self, button):
        self.destroy()

    def on_timeout(self):
        self.progressbar.pulse()
        return True

    def update_label_preview(self, label, accuracy, inference_time, display_fps, grab_fps, inference_fps):
        str_accuracy = str("{0:.0f}".format(accuracy))
        str_inference_time = str("{0:0.1f}".format(inference_time))
        str_display_fps = str("{0:.1f}".format(display_fps))
        str_grab_fps = str("{0:.1f}".format(grab_fps))
        str_inference_fps = str("{0:.1f}".format(inference_fps))

        self.progressbar.show()
        self.progressbar.set_show_text(True)
        self.progressbar.set_fraction(accuracy / 100)

        self.label.set_markup("<span font='10' color='#002052FF'><b>display   @%sfps\n</b></span>"
                              "<span font='10' color='#002052FF'><b>inference @%sfps\n\n\n</b></span>"
                              "<span font='15' color='#002052FF'><b>inference time: %sms\n</b></span>"
                              "<span font='15' color='#002052FF'><b>accuracy:       %s&#37;\n\n</b></span>"
                              "<span font='15' color='#002052FF'><b>%s</b></span>"
                              % (str_grab_fps, str_inference_fps, str_inference_time, str_accuracy, label))

    def update_label_still(self, label, accuracy, inference_time):
        str_accuracy = str("{0:.2f}".format(accuracy))
        str_inference_time = str("{0:0.1f}".format(inference_time))

        self.progressbar.show()
        self.progressbar.set_show_text(True)
        self.progressbar.set_fraction(accuracy / 100)

        self.label.set_markup("<span font='15' color='#002052FF'><b>inference time: %sms\n</b></span>"
                              "<span font='15' color='#002052FF'><b>accuracy:       %s&#37;\n\n</b></span>"
                              "<span font='15' color='#002052FF'><b>%s</b></span>"
                              % (str_inference_time, str_accuracy, label))

    def update_frame(self, frame):
        img = Image.fromarray(frame)
        data = img.tobytes()
        data = GLib.Bytes.new(data)
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(data,
                                                 GdkPixbuf.Colorspace.RGB,
                                                 False,
                                                 8,
                                                 frame.shape[1],
                                                 frame.shape[0],
                                                 frame.shape[2] * frame.shape[1])
        self.image.set_from_pixbuf(pixbuf.copy())

    # termination function
    def terminate(self):
        print("Main: termination")
        if self.enable_camera_preview:
            if self.camera_not_started:
                return
            self.preview_process.terminate()
        self.nn_process.terminate()

    # get random file in a directory
    def getRandomFile(self, path):
        """
        Returns a random filename, chosen among the files of the given path.
        """
        files = os.listdir(path)
        index = random.randrange(0, len(files))
        return files[index]

    # GTK camera preview function
    def camera_preview(self):
        # crop the preview frame to fit the NN input size
        frame_crop = self.frame[self.y1:self.y2, self.x1:self.x2]
        frame_crop_RGB = cv2.cvtColor(frame_crop,cv2.COLOR_BGR2RGB)
        frame_crop_RGB_resize = cv2.resize(frame_crop_RGB, (self.nn_img.shape[1], self.nn_img.shape[0]))

        if self.nn_processing_finished.value == True:
            self.nn_processing_finished.value = False
            # grab a new frame
            self.nn_img[:, :, :] = frame_crop_RGB_resize
            # display the cropped image that will feed the NN
            #cv2.imshow("nn_img", self.nn_img)
            # request NN processing
            self.nn_processing_start.value = True

        # compute preview FPS
        loop_stop = timer();
        self.loop_time = loop_stop - self.loop_start
        self.loop_start = loop_stop
        self.total_time = self.total_time + self.loop_time
        if self.loop_count==15:
            self.preview_fps = self.loop_count / self.total_time
            self.loop_count = 0
            self.total_time = 0
        self.loop_count = self.loop_count + 1

        # write information onf the GTK UI
        labels = self.nn.get_labels()
        label = labels[self.nn_result_label.value]
        accuracy = self.nn_result_accuracy.value * 100
        inference_time = self.nn_inference_time.value * 1000
        inference_fps = self.nn_inference_fps.value
        display_fps = self.preview_fps
        grab_fps = self.grabbing_fps.value

        self.update_label_preview(str(label), accuracy, inference_time, display_fps, grab_fps, inference_fps)

        # update the preview frame
        self.update_frame(frame_crop_RGB)

        return True

    # GTK still picture function
    def still_picture(self, button):
        #input("Press Enter to process new inference...")
        self.nn_processing_finished.value = False
        # get randomly a picture in the directory
        rfile = self.getRandomFile(args.image)
        print("Picture ", args.image + "/" + rfile)
        img = Image.open(args.image + "/" + rfile)

        # display the picture in the screen
        prev_frame = cv2.resize(np.array(img), (self.picture_width, self.picture_height))

        # update the preview frame
        self.update_frame(prev_frame)

        # execute the inference
        nn_frame = cv2.resize(prev_frame, (self.nn_img.shape[1],  self.nn_img.shape[0]))
        self.nn_img[:, :, :] = nn_frame
        self.nn_processing_start.value = True
        while not self.nn_processing_finished.value:
            pass

        # write information onf the GTK UI
        labels = self.nn.get_labels()
        label = labels[self.nn_result_label.value]
        accuracy = self.nn_result_accuracy.value * 100
        inference_time = self.nn_inference_time.value * 1000

        self.update_label_still(str(label), accuracy, inference_time)

        return True

    def main(self, args):
        if self.enable_camera_preview:
            #variable to compute preview framerate
            self.loop_count = 1
            self.loop_time = 0
            self.loop_start = 0
            self.total_time = 0
            self.preview_fps = 0

            self.camera_not_started = True
            # initialize VideoFrameCapture object
            cap = VideoFrameCapture(int(args.video_device), float(args.frame_width), float(args.frame_height), float(args.framerate))
            shape = cap.get_frame_size()
            self.camera_not_started = False

            # define shared variables
            self.shared_array_base = Array(ctypes.c_uint8, shape[0] * shape[1] * shape[2])
            self.frame = np.ctypeslib.as_array(self.shared_array_base.get_obj())
            self.frame = self.frame.reshape(shape[0], shape[1], shape[2])
            self.grabbing_fps = Value('f', 0.0)

            # start processes which run in parallel
            self.preview_synchro_event = Event()
            self.preview_process = Process(name='camera_streaming', target=camera_streaming,
                                           args=(cap,
                                                 self.shared_array_base,
                                                 self.preview_synchro_event,
                                                 self.grabbing_fps))
            # launch capture process
            self.preview_process.daemon = True
            self.preview_process.start()

        # initialize NeuralNetwork object
        self.nn = NeuralNetwork(args.model_file, args.label_file, float(args.input_mean), float(args.input_std))
        shape = self.nn.get_img_size()

        if self.nn._floating_model:
            Gtk.HeaderBar.set_subtitle(self.headerbar, "float model " + os.path.basename(args.model_file))
        else:
            Gtk.HeaderBar.set_subtitle(self.headerbar, "quant model " + os.path.basename(args.model_file))

        # define shared variables
        self.nn_processing_start = Value(ctypes.c_bool, False)
        self.nn_processing_finished = Value(ctypes.c_bool, False)
        self.nn_img_shared_array = Array(ctypes.c_uint8, shape[0] * shape[1] * shape[2])
        self.nn_img = np.ctypeslib.as_array(self.nn_img_shared_array.get_obj())
        self.nn_img = self.nn_img.reshape(shape[0], shape[1], shape[2])
        self.nn_inference_time = Value('f', 0)
        self.nn_inference_fps = Value('f', 0.0)
        self.nn_result_accuracy = Value('f', 0.0)
        self.nn_result_label = Value('i', 0)

        # start processes which run in parallel
        self.nn_synchro_event = Event()
        self.nn_process = Process(name='nn_processing', target=nn_processing,
                                  args=(self.nn,
                                        self.nn_img_shared_array,
                                        self.nn_processing_start,
                                        self.nn_processing_finished,
                                        self.nn_inference_time,
                                        self.nn_result_accuracy,
                                        self.nn_result_label,
                                        self.nn_synchro_event,
                                        self.nn_inference_fps))
        # launch nn process
        self.nn_process.daemon = True
        self.nn_process.start()

        # wait the nn process to start
        self.nn_synchro_event.wait()

        if self.enable_camera_preview:
            self.preview_synchro_event.wait()

            # define the crop parameters that will be used to crop the input preview frame to
            # the requested NN input image size
            self.y1 = int(0)
            self.y2 = int(self.frame.shape[0])
            self.x1 = int((self.frame.shape[1] - self.frame.shape[0]) / 2)
            self.x2 = int(self.x1 + self.frame.shape[0])

            # set the following variable to True to trig the first NN inference
            self.nn_processing_finished.value = True

            # hidde the progress bar
            GLib.source_remove(self.timeout_id)
            self.progressbar.hide()

            GLib.idle_add(self.camera_preview)
        else:
            # hidde the progress bar
            GLib.source_remove(self.timeout_id)
            self.progressbar.hide()

            if not self.enable_camera_preview:
                self.button = Gtk.Button.new_with_label("Next inference")
                self.vbox.pack_start(self.button, False, False, 15)
                self.button.connect("clicked", self.still_picture)
                self.button.show_all()

def destroy_window(gtkobject):
    gtkobject.terminate()
    print("destroy")

if __name__ == '__main__':
    # add signal to catch CRTL+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    #Tensorflow Lite NN intitalisation
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--image", default="", help="image directory with image to be classified")
    parser.add_argument("-v", "--video_device", default=0, help="video device (default /dev/video0)")
    parser.add_argument("--frame_width", default=320, help="width of the camera frame (default is 320)")
    parser.add_argument("--frame_height", default=240, help="height of the camera frame (default is 240)")
    parser.add_argument("--framerate", default=15, help="framerate of the camera (default is 15fps)")
    parser.add_argument("-m", "--model_file", default="", help=".tflite model to be executed")
    parser.add_argument("-l", "--label_file", default="", help="name of file containing labels")
    parser.add_argument("--input_mean", default=127.5, help="input mean")
    parser.add_argument("--input_std", default=127.5, help="input standard deviation")
    args = parser.parse_args()

    set_start_method("spawn")

    try:
        win = MainUIWindow(args)
        win.connect("delete-event", Gtk.main_quit)
        win.connect("destroy", destroy_window)
        win.show_all()
        thread = Thread(target =  win.main, args = (args,))
        thread.daemon = True
        thread.start()
    except Exception as exc:
        print("Main Exception: ", exc )

    Gtk.main()
