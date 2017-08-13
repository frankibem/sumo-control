import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from threading import Event, Thread


class SumoDisplay(Thread):
    """
    Displays frames received from the Jumping Sumo
    """

    def __init__(self, receiver):
        Thread.__init__(self, name='SumoDisplay')
        # self.setDaemon(True)

        self.receiver = receiver
        self.should_run = Event()
        self.should_run.set()

        self.window_name = 'Sumo Display'
        # cv2.namedWindow('SumoDisplay')

    def run(self):
        while self.should_run.isSet():
            frame = self.receiver.get_frame()

            if frame is not None:
                byte_frame = BytesIO(frame)
                img = np.array(Image.open(byte_frame))
                cv2.imshow(self.window_name, img)

            cv2.waitKey(25)

    def disconnect(self):
        """
        Stops the main loop and closes the display window
        """
        self.should_run.clear()
        cv2.destroyWindow(self.window_name)
