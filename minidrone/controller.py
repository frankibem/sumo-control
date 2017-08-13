import json
import socket
import logging

from minidrone.receiver import SumoReceiver
from minidrone.sender import SumoSender, move_cmd
from minidrone.video import SumoDisplay


class SumoController:
    def __init__(self):
        """
        Creates a controller for the Jumping Sumo
        """
        self.host = '192.168.2.1'
        self.discovery_port = 44444
        self.d2c_port = 43210

        # Will be set during discovery
        self.c2d_port = None
        self.fragment_size = None
        self.fragments_per_frame = None

        self.sender = None
        self.receiver = None
        self.display = None

    def _discovery(self):
        """
        Initiates discovery with the jumping sumo (via TCP)
        """
        logging.info('Connecting to Jumping sumo...')
        conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn_socket.connect((self.host, self.discovery_port))

        conn_msg = {'controller_name': 'Python Controller', 'controller_type': 'PC', 'd2c_port': self.d2c_port}
        conn_socket.send(json.dumps(conn_msg).encode())

        data = conn_socket.recv(1024)
        if len(data) <= 0:
            raise ConnectionError('SumoController.connect(): failed to read connection data')

        # Strip the terminating null character
        config_data = json.loads(data[:-1].decode('utf-8'))
        logging.info('Received config data: \n{}'.format(config_data))

        # Store config data
        self.c2d_port = config_data['c2d_port']
        self.fragment_size = config_data['arstream_fragment_size']
        self.fragments_per_frame = config_data['arstream_fragment_maximum_number']

    def connect(self):
        """
        Establish a connection to the drone and start receiving and sending data
        """
        self._discovery()

        self.sender = SumoSender(self.host, self.c2d_port)
        self.receiver = SumoReceiver('', self.d2c_port, self.sender)
        self.display = SumoDisplay(self.receiver)

        self.receiver.start()
        self.sender.start()
        self.display.start()

    def move(self, speed, turn):
        """
        Apply the given speed and turn to the Jumping Sumo
        :param speed: [-100, 100]
        :param turn:  [-100, 100]
        :return:
        """
        self.sender.send(move_cmd(speed, turn))

    def disconnect(self):
        """
        Stops sending, receiving and display threads and closes associated resources
        """
        if self.display is not None:
            self.display.disconnect()

        if self.sender is not None:
            self.sender.disconnect()

        if self.receiver is not None:
            self.receiver.disconnect()
