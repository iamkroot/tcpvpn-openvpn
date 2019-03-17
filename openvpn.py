from pathlib import Path
import select
import socket
import subprocess
import sys
import time
import logging

logger = logging.getLogger('OPVPN')
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel('DEBUG')


class OPVPNInterface:
    """Interface to control and monitor OpenVPN via Management Interface."""

    def __init__(self, config_path, creds=None, port=7505):
        self.config_path = config_path
        self.socket_port = port
        self.connected = False
        self.connect_sock()
        self.creds = creds
        if self.creds:
            self.username = self.creds['username']
            self.password = self.creds['password']

    def connect_sock(self):
        """Connect to management interface via socket."""
        self.management = socket.socket()
        self.management.settimeout(2)
        try:
            self.management.connect(('localhost', self.socket_port))
        except socket.timeout:
            logger.warning('Timed out while trying to connect to management.')
            self.connected = False
            self.management = None
        except ConnectionRefusedError:
            logger.error('Cant connect to management')
            self.management = None
            self.connected = False
        else:
            self.connected = True

    def disconnect_sock(self):
        self._send_msg('quit')

    def toggle_conn(self):
        if self.connected:
            self.kill_instance()
        else:
            self.create_instance()

    def _send_msg(self, msg):
        if not self.connected:
            return
        self.management.send(bytes(msg + '\n', 'utf-8'))

    def _recv_msgs(self):
        if not self.connected:
            return []
        readable, _, _ = select.select([self.management], [], [], 0.1)
        while readable:
            data = readable[0].recv(1024).decode().strip()
            if data:
                # logger.debug(f'==={data}===')
                yield data
            else:
                self.management.close()
                self.connected = False
                self.management = None
                break
            readable, _, _ = select.select([self.management], [], [], 0.1)

    def send_recv(self, msg):
        self._send_msg(msg)
        return self._recv_msgs()

    def parse_msg(self, data):
        pass

    def create_instance(self):
        """Start OpenVPN with given config."""
        cmd = [
            'sudo openvpn',
            '--management', '127.0.0.1', '7505',
            '--config', self.config_path,
            '--daemon'
        ]
        if self.creds:
            cmd.append('--management-query-passwords')
        subprocess.Popen(" ".join(cmd),
                         cwd=str(Path.cwd()),
                         shell=True,
                         stdout=subprocess.PIPE,
                         bufsize=1)
        time.sleep(1)
        self.connect_sock()
        if not list(self._recv_msgs()):
            self.connected = False
            return
        if self.creds:
            for _ in self.send_recv(f"username Auth {self.username}"):
                pass
            for _ in self.send_recv(f"password Auth {self.password}"):
                pass
        logger.info("OpenVPN started.")
        for _ in range(30):
            state = self.get_state()
            if not state:
                continue
            if state['connected'] == 'CONNECTED':
                logger.info('Connected to server.')
                break
            for msg in self.send_recv('log 2'):
                if "Verification Failed: 'Auth'" in msg:
                    logger.error("Wrong creds")
                    return
            time.sleep(1)
        else:
            logger.error('Timed out while connecting to server.')
            self.kill_instance()

    def kill_instance(self):
        for msg in self.send_recv('signal SIGTERM'):
            if msg.startswith('SUCCESS'):
                logger.info("OpenVPN killed.")
                break
        else:
            logger.warning('Failed to kill OpenVPN')

    def get_info(self, command):
        for msg in self.send_recv(command):
            if msg.startswith('>') or msg.startswith('END'):
                continue
            if command == 'state':
                data = self.parse_state(msg)
            elif command == 'load-stats':
                data = self.parse_stats(msg)
            if data:
                return data

    def get_state(self):
        return self.get_info('state')

    def get_stats(self):
        return self.get_info('load-stats')

    @staticmethod
    def parse_state(data):
        vals = ('up_since', 'connected', 'success', 'local_ip', 'remote_ip')
        return dict(zip(vals, data.split(',')))

    @staticmethod
    def parse_stats(data):
        parts = data[20:].split(',')
        return {'bytesin': int(parts[0][8:]), 'bytesout': int(parts[1][9:])}
