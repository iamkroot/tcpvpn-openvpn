import argparse
from datetime import datetime
from operator import attrgetter
from pathlib import Path

from fuzzywuzzy import process

from openvpn import OPVPNInterface
from tcpvpn import create_account, serv_paths, credentials
from utils import cfg

CONFIGS_FOLD = Path('~/.openvpn/configs').expanduser()
CONFIGS_FOLD.mkdir(parents=True, exist_ok=True)


def get_serv_config(serv_name):
    fold = process.extractOne(
        Path(serv_name), CONFIGS_FOLD.iterdir(), attrgetter('name'))
    if not fold:
        print("Config folder not found.")
        return
    fold = fold[0]
    ports = {}
    for file in fold.iterdir():
        if not file.suffix == '.ovpn':
            continue
        try:
            ports[int(file.stem[file.stem.rfind('-') + 1:])] = file
        except (TypeError, ValueError):
            print("Invalid port", file)
    if not ports:
        return
    for port in cfg['port_priorities']:
        conf = ports.get(port)
        if conf:
            return conf
    return ports.popitem()[1]


def get_serv_name(name):
    serv_name = process.extractOne(name, serv_paths.keys())
    print("Using server", serv_name)
    if serv_name:
        return serv_name[0]


def get_serv_creds(name):
    creds = credentials.get(name)
    if not creds or creds['expires_at'].replace(tzinfo=None) < datetime.now():
        creds = create_account(name)
    return creds


def get_server(name):
    serv_name = get_serv_name(name)
    if not serv_name:
        return
    serv_config = get_serv_config(serv_name)
    serv_creds = get_serv_creds(serv_name)
    return serv_name, serv_config, serv_creds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--kill', action='store_true')
    parser.add_argument('server', nargs='?')
    args = parser.parse_args()

    if args.kill:
        op = OPVPNInterface(None)
        op.kill_instance()
        return

    if args.server:
        cfg['serv_priorities'].insert(0, args.server)
    for name in cfg['serv_priorities']:
        serv = get_server(name)
        if serv and all(serv):
            break
    else:
        print("No suitable server found.")
        return
    print("Selected", serv[0])
    print("Creds will expire after", serv[2]['expires_at'].date())
    op = OPVPNInterface(str(serv[1]), creds=serv[2])
    op.create_instance()


if __name__ == '__main__':
    main()
