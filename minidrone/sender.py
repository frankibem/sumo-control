import time
import struct
import socket
import datetime
import logging
from collections import defaultdict
from threading import Thread, Lock, Event

"""
For full reference, see: http://developer.parrot.com/docs/bebop/ARSDK_Protocols.pdf
The xml files for command definitions can be found here: https://github.com/Parrot-Developers/arsdk-xml/tree/master/xml

A commands is identified by its first 4 bytes:
    - Project/Feature (1 byte)
    - Class ID in project/feature (1 byte)
    - Command ID in class (2 bytes) 
All data is sent in Little Endian byte order
"""


class SumoSender(Thread):
    """
    Sends commands to the Jumping Sumo. PCMD commands are sent at a fixed frequency (every 25ms)
    """

    def __init__(self, host, port):
        Thread.__init__(self, name='SumoSender')
        self.setDaemon(True)

        self.host = host
        self.port = port
        self.send_lock = Lock()
        self.should_run = Event()
        self.should_run.set()
        self.seq_ids = defaultdict(int)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Initial command (no motion)
        self.cmd = _pack_frame(move_cmd(0, 0))
        assert _is_pcmd(self.cmd)

    def _update_seq(self, cmd):
        """
        Updates the sequence number for the given framed command
        """
        assert len(cmd) > 3, str(cmd)
        buffer_id = cmd[1]

        self.seq_ids[buffer_id] = (self.seq_ids[buffer_id] + 1) % 256
        return cmd[:2] + struct.pack('<B', self.seq_ids[buffer_id]) + cmd[3:]

    def send(self, cmd):
        """
        Sends the given command to the Jumping Sumo. Non-PCMD commands are sent immediately
        while PCMD commands are sent at the next cycle (see run). cmd is the payload and the
        method creates a frame by prepending a header
        """
        if cmd is not None:
            with self.send_lock:
                frame = self._update_seq(_pack_frame(cmd))
                if _is_pcmd(frame):
                    self.cmd = frame
                else:
                    self.socket.sendto(frame, (self.host, self.port))

    def run(self):
        logging.info('SumoSender started.')

        # Initial configuration
        date_time = datetime.datetime.now()
        self.send(sync_date_cmd(date_time.date()))
        self.send(sync_time_cmd(date_time.time()))
        self.send(set_media_streaming_cmd(enable=True))

        # Run loop
        while self.should_run.isSet():
            with self.send_lock:
                logging.debug('PCMD: {}'.format(self.cmd))
                self.socket.sendto(self.cmd, (self.host, self.port))
                self.cmd = _pack_frame(move_cmd(0, 0))

            time.sleep(0.025)

    def disconnect(self):
        """
        Stops the main loop and closes the connection to the Jumping Sumo
        """
        self.should_run.clear()
        self.socket.close()


def move_cmd(speed, turn):
    """
    Project: jpsumo(3), Class: Piloting (0), Command: PCMD (0)
        Flag: boolean for touch screen
        Speed: [-100, 100]
        Turn: [-100, 100]
    """
    return struct.pack('<BBHBbb', 3, 0, 0, (speed != 0 or turn != 0), speed, turn)


def set_media_streaming_cmd(enable=True):
    """
    Project: jpsumo(3), Class: MediaStreaming (18), Command: VideoEnable (0)
    Args:
        enable: 1 to enable, 0 to disable
    :return:
    """
    flag = 1 if enable else 0
    return struct.pack('<BBHB', 3, 18, 0, flag)


def sync_date_cmd(sync_date):
    """
    Project: Commom(0), Class: Common(4), Command: CurrentDate(1)
        Date (ISO-8601 format)
    """
    return struct.pack('<BBH', 0, 4, 1) + sync_date.isoformat().encode() + b'\0'


def sync_time_cmd(sync_time):
    """
    Project: Commom(0), Class: Common(4), Command: CurrentDate(2)
        Time (ISO-8601 format)
    """
    return struct.pack('<BBH', 0, 4, 2) + sync_time.strftime('T%H%M%S+0000').encode() + b'\0'


def _pack_frame(payload):
    """
    Creates a complete frame by prepending a header to the given payload
    Data type: normal data(2)
    Target buffer ID:
    Sequence number
    Frame size
    Payload
    """
    data_type = 2
    buffer_id = 10
    seq_no = 0  # Will be set at a later time
    frame_size = 7 + len(payload)

    header = struct.pack('<BBBI', data_type, buffer_id, seq_no, frame_size)
    return header + payload


def _is_pcmd(cmd):
    """
    Returns true if the given command is a pcmd command and false otherwise
    """
    # BBHBbb: Header (7) + payload (7)
    if len(cmd) != 14:
        return False

    return struct.unpack('<BBH', cmd[7:11]) == (3, 0, 0)
