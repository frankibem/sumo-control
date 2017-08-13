import struct
import socket
import logging
from threading import Thread, Event, Lock

# See https://github.com/Parrot-Developers/libARDiscovery/blob/master/Sources/Wifi/ARDISCOVERY_DEVICE_Wifi.c
ARNETWORKAL_FRAME_TYPE_ACK = 0x01
ARNETWORKAL_FRAME_TYPE_DATA = 0x02
ARNETWORKAL_FRAME_TYPE_DATA_LOW_LATENCY = 0x03
ARNETWORKAL_FRAME_TYPE_DATA_WITH_ACK = 0x04

PROJECT_COMMOM = 0
PROJECT_SUMO = 3
VIDEO_DATA_BUFFER = 0x7D


class SumoReceiver(Thread):
    """
    Receives data from the Jumping Sumo
    """

    def __init__(self, host, port, sender):
        """
        :param host: The host to listen to
        :param port: The port to listen on
        :param sender: The sender for sending ACKS packets
        """
        Thread.__init__(self, name='SumoReceiver')
        self.setDaemon(True)

        self.host = host
        self.port = port
        self.sender = sender
        self.should_run = Event()
        self.should_run.set()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(1.0)

        # Video frames
        self.current_frame_no = None
        self.parts = None
        self.frames = []
        self.mutex_frames = Lock()

    def run(self):
        logging.info('SumoReceiver started.')
        self.socket.bind((self.host, self.port))

        while self.should_run.isSet():
            try:
                packet = self.socket.recv(262144)
            except socket.timeout:
                logging.error('SumoReceiver socket.recv() timed out')
                break

            while len(packet) > 0:
                # A packet can have one or more frames
                frame, packet = _split_frames(packet)
                if frame is None:
                    break

                # Process the next frame
                self._process_frame(frame)

    def _process_frame(self, frame):
        data_type, buffer_id, seq_no, frame_size = _read_header(frame)
        payload = frame[7:]

        # We received an ACK for a packet we sent
        if data_type == ARNETWORKAL_FRAME_TYPE_ACK:
            logging.debug('ACK packet received')

        # We received a data packet, log it (do more in future?)
        elif data_type == ARNETWORKAL_FRAME_TYPE_DATA or data_type == ARNETWORKAL_FRAME_TYPE_DATA_WITH_ACK:
            cmd_project, cmd_class, cmd_id = struct.unpack('<BBH', payload[:4])
            if cmd_project == PROJECT_COMMOM:
                if (cmd_class, cmd_id) == (5, 4):
                    # date = struct.unpack('s', payload[4:])
                    date = payload[4:-1].decode()
                    logging.info('Date updated to: {}'.format(date))
                elif (cmd_class, cmd_id) == (5, 5):
                    # time = struct.unpack('s', payload[4:])
                    time = payload[4:-1].decode()
                    logging.info('Time updated to: {}'.format(time))
                else:
                    logging.debug('DataFrame | Project: {}, Class: {}, Id: {}'.format(cmd_project, cmd_class, cmd_id))
            elif cmd_project == PROJECT_SUMO:
                if (cmd_class, cmd_id) == (1, 2):
                    speed, real_speed = struct.unpack('<bh', payload[4:])
                    logging.debug('Speed updated to {} ({} cm/s)'.format(speed, real_speed))
                elif (cmd_class, cmd_id) == (19, 0):
                    state = struct.unpack('<i', payload[4:])
                    logging.info('Media streaming state is: {} (enabled/disabled/error)'.format(state))
                else:
                    logging.debug('DataFrame | Project: {}, Class: {}, Id: {}'.format(cmd_project, cmd_class, cmd_id))
            else:
                logging.debug('DataFrame | Project: {}, Class: {}, Id: {}'.format(cmd_project, cmd_class, cmd_id))

            # Frame requires an ACK, send one
            if data_type == ARNETWORKAL_FRAME_TYPE_DATA_WITH_ACK:
                self.sender.send(_create_ack_packet(data_type, buffer_id, seq_no))
                logging.debug('Sending ACK for ', (data_type, buffer_id, seq_no, frame_size))

        # We received an ARStream packet, process it
        elif data_type == ARNETWORKAL_FRAME_TYPE_DATA_LOW_LATENCY:
            self._process_video_frame(buffer_id, frame_size, payload)
        else:
            logging.warning('Unknown header type: ', (data_type, buffer_id, seq_no, frame_size))

    def _process_video_frame(self, buffer_id, frame_size, payload):
        if buffer_id != VIDEO_DATA_BUFFER:
            # Stream data from another low-latency buffer (maybe audio?)
            logging.debug('ARStream | buffer: {}, size: {}'.format(buffer_id, frame_size - 7))
            return

        frame_no, frame_flags, frag_no, frags_per_frame = struct.unpack('<HBBB', payload[:5])
        fragment = payload[5:]

        # We got a fragment for a different frame
        if frame_no != self.current_frame_no:
            # Reset frame number and fragment buffer
            self.current_frame_no = frame_no
            self.parts = [None] * frags_per_frame

        if self.parts[frag_no] is not None:
            logging.debug('Duplicate fragment | Frame: {}, Fragment: {}'.format(frame_no, frag_no))
        else:
            self.parts[frag_no] = fragment

            # We've received the entire frame
            if None not in self.parts:
                self._add_frame(b''.join(self.parts))

    def _add_frame(self, frame):
        """
        Adds a new complete frame to the frame buffer
        """
        with self.mutex_frames:
            self.frames.append(frame)

    def get_frame(self):
        """
        Returns the last received frame and clears the buffer. Returns None if there is none
        """
        with self.mutex_frames:
            if len(self.frames) == 0:
                return None
            frame = self.frames[-1]
            self.frames = []
            return frame

    def disconnect(self):
        """
        Stops the main loop and closes the connection to the Jumping Sumo
        """
        self.should_run.clear()
        self.socket.close()


def _read_header(data):
    """
    Returns the header portion of the given data
    """
    return struct.unpack('<BBBI', data[:7])


def _split_frames(data):
    """
    Returns (head, tail) where head is the first frame in the given data
    and tail is the rest of the data
    """
    if len(data) < 7:
        # Must contain at least header, nothing to process
        return None, data[-1:-1]

    data_type, buffer_id, seq_no, frame_size = _read_header(data)
    return data[:frame_size], data[frame_size:]


def _create_ack_packet(data_type, buffer_id, seq_no):
    """
    Create an ACK packet based on the given header information
    """
    assert data_type == ARNETWORKAL_FRAME_TYPE_DATA_WITH_ACK, 'Must be data with ACK'

    # The payload of an ACK frame is the sequence no. of the data frame
    payload = struct.pack('<B', seq_no)

    # The buffer id is 128 + base_id
    return struct.pack('<BBBI', ARNETWORKAL_FRAME_TYPE_ACK, buffer_id + 128, 0, 7 + len(payload)) + payload
