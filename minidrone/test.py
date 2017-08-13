import cv2
import logging

from minidrone.controller import SumoController


def main():
    ctrl = SumoController()
    ctrl.connect()

    speed, turn = 0, 0
    while True:
        k = cv2.waitKey(30) & 0xff
        if k == ord('q'):
            break
        elif k == ord('j'):
            turn = -25
        elif k == ord('l'):
            turn = 25
        elif k == ord('i'):
            turn = 0
            speed = 25
        elif k == ord('k'):
            turn = 0
            speed = -25
        else:
            speed, turn = 0, 0

        ctrl.move(speed, turn)


if __name__ == '__main__':
    logging.basicConfig(filename='sumo.log', level=logging.INFO)
    main()
