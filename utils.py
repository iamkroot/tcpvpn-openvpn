import rarfile
import zipfile
import json
import pytoml
import requests
from pathlib import Path


def read_dict(path, parser, error):
    try:
        with open(path) as f:
            try:
                return parser(f)
            except error:
                return {}
    except FileNotFoundError:
        return {}


def read_toml(path):
    return read_dict(path, pytoml.load, pytoml.TomlError)


def write_toml(data, path):
    with open(path, 'w') as f:
        pytoml.dump(data, f)


def read_json(path):
    return read_dict(path, json.load, json.JSONDecodeError)


def write_json(data, file_path):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)


cfg = read_toml('config.toml')
serv_paths = read_json('serv_paths.json')
credentials = read_toml('creds.toml')


def extract_archive(archive_path):
    """Extract the archive to a folder."""
    if archive_path.suffix == '.zip':
        archive = zipfile.ZipFile(str(archive_path), 'r')
    elif archive_path.suffix == '.rar':
        unrar_path = cfg['unrar_path']
        if not Path(unrar_path).exists():
            print_quit("Please ensure unrar_path exists!")
        rarfile.UNRAR_TOOL = unrar_path
        archive = rarfile.RarFile(str(archive_path), 'r')
    else:
        print_quit("Unknown archive type.")
    # if archive_path.parent.exists():
    #     archive_path.rename(archive_path.parent.with_suffix('.bak'))
    #     archive_path.parent.rmdir()
    archive.extractall(str(archive_path.parent))
    archive.close()
    archive_path.unlink()  # delete the archive


def print_quit(text="Quitting!"):
    print(text)
    exit(0)


def get_choice(options, find_arg, back_text="Go back"):
    while True:
        if back_text:
            print('0.', back_text)

        for index, option in enumerate(options, 1):
            label = option.select_one(find_arg).text.strip()
            print(f'{index}. {label}')

        print(f'{index + 1}. Cancel.')
        try:
            option_index = int(input()) - 1
            if -1 <= option_index < len(options):
                return option_index
            elif option_index == len(options):
                print_quit()
            else:
                raise ValueError
        except KeyboardInterrupt:
            print_quit()
        except ValueError:
            print('Incorrect option selected.')


def retry_on_conn_error(func, max_retries=5):
    def wrapper(*args, **kwargs):
        for _ in range(max_retries):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.ConnectionError:
                print("Connection Error. Retrying.")
                continue
            except KeyboardInterrupt:
                print_quit()
        else:
            print("Connection Error! Maximum retries exceeded.")
            print_quit()
    return wrapper
