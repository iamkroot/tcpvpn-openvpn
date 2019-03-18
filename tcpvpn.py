import argparse
import re
import secrets

import requests

from pathlib import Path
from datetime import datetime

from bs4 import BeautifulSoup
from fuzzywuzzy import process

from utils import (cfg, serv_paths, credentials,
                   extract_archive, print_quit, get_choice,
                   retry_on_conn_error, write_json, write_toml)


class TCPVPNServAccCreator():
    """Class that represents a tcpvpn.com scraper."""
    HOME_URL = 'https://www.tcpvpn.com'
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    STATES = ('continent', 'country', 'protocol', 'server', 'END')

    def __init__(self, serv_name=None, force_dl_config=False):
        self.sess = requests.Session()
        self.force_dl_config = force_dl_config
        self.choices = {}
        self.cache = {}
        self.state = self.STATES[0]
        self.server = {}
        self.skip_country = False
        serv_path = serv_paths.get(serv_name)
        if serv_path:
            self.serv_name = serv_name
            self.serv_path = dict(zip(self.STATES, serv_path))
        else:
            if serv_name:
                print("No server with provided name could be found.")
            self.serv_name = None
            self.serv_path = {}

    def _next_state(self):
        self.state = self.STATES[self.STATES.index(self.state) + 1]

    def _prev_state(self):
        self.state = self.STATES[self.STATES.index(self.state) - 1]
        if self.state == 'country' and self.skip_country:
            self.state = 'continent'
            self.skip_country = False

    def select_option(self, options, find_arg=None):
        if self.serv_name:
            self.choices[self.state] = options[self.serv_path[self.state]]
            self._next_state()
            return

        print(f'Select your {self.state} from below choices:')
        if self.state == 'continent':
            choice = get_choice(options, find_arg, None)
            if choice == -1:
                print_quit()
        else:
            choice = get_choice(options, find_arg)

        if choice == -1:
            if self.state in self.choices:
                del self.choices[self.state]
            self._prev_state()
            if self.state in self.cache:
                self.select_option(**self.cache[self.state])
        else:
            self.choices[self.state] = options[choice]
            self.serv_path[self.state] = choice
            name = options[choice].select_one(find_arg).text
            print(f"You have selected {name}.")
            self.cache[self.state] = {'options': options, 'find_arg': find_arg}
            self._next_state()

    def _get_continent(self):
        homepage = self.sess.get(self.HOME_URL)
        soup = BeautifulSoup(homepage.text, 'html.parser')
        continents = soup.select('section#plans div.col-md-4.text-center')
        continents.pop()
        self.select_option(continents, 'h3')

    def _get_country(self):
        continent_url = self.choices['continent'].find('a')['href']
        continent_page = self.sess.get(continent_url)
        soup = BeautifulSoup(continent_page.text, 'html.parser')
        if soup.find('ul', id='myTab'):
            try:
                self.choices['country'] = self.choices['continent']
                self.cache['country'] = self.cache['continent']
            except KeyError:
                pass
            self.state = 'protocol'
            self.skip_country = True
            self.serv_path['country'] = self.serv_path['continent']
        else:
            countries = soup.select('div.col-md-4')
            countries.pop()
            self.select_option(countries, 'h2')

    def _get_protocol(self):
        country_url = self.choices['country'].find('a')['href']
        country_page = self.sess.get(country_url)
        country_soup = BeautifulSoup(country_page.text, 'html.parser')
        protocols = country_soup.select_one('#myTab').select('li')
        self.select_option(protocols, 'a')

    def _get_server(self):
        protocol_url = self.choices['protocol'].find('a').attrs['href']
        if protocol_url.startswith(self.HOME_URL):
            servers_page = self.sess.get(protocol_url)
            server_soup = BeautifulSoup(servers_page.text, 'html.parser')
            servers = server_soup.select('div.col-md-4')
            servers.pop()
        else:
            country_url = self.choices['country'].find('a')['href']
            country_page = self.sess.get(country_url)
            country_soup = BeautifulSoup(country_page.text, 'html.parser')
            protocol_div = country_soup.select_one(protocol_url)
            servers = protocol_div.select('div.col-md-4')

        self.select_option(servers, 'h3')

    def get_serv_details(self):
        serv = self.choices.get('server')
        if not serv:
            print_quit('No server selected')

        if not self.serv_name:
            print("Details:")
            for item in serv.select('li.list-group-item'):
                print(item.text.strip())
        else:
            print("Selected", self.serv_name)

        form = serv.form
        config_url = form.a['href']
        config_name = config_url[config_url.rfind('/') + 1:]
        self.server = {
            'name': config_name[:config_name.find('.com')].lower(),
            'create_url': form['action'],
            'id': form.find('input')['value'],
            'config_url': config_url,
            'config_name': config_name
        }
        self.serv_name = self.server['name']
        self.save_serv_path()
        self.download_serv_config()

    def save_serv_path(self):
        if self.server['name'] not in serv_paths:
            serv_paths[self.server['name']] = list(self.serv_path.values())
            write_json(serv_paths, 'serv_paths.json')

    @retry_on_conn_error
    def download_serv_config(self):
        configs_fold = Path(cfg['configs_fold']).expanduser()
        configs_fold.mkdir(parents=True, exist_ok=True)
        config_archive_path: Path = configs_fold / self.server['config_name']
        config_path = configs_fold / config_archive_path.stem

        if not self.force_dl_config and config_path.exists():
            return
        print("Downloading server config.")
        r = self.sess.get(self.server['config_url'])
        with open(config_archive_path, 'wb') as f:
            f.write(r.content)
        extract_archive(config_archive_path)
        print("Saved config to", configs_fold / config_path)

    @retry_on_conn_error
    def state_loop(self):
        for _ in range(25):
            if self.state == 'END':
                break
            if self.state == 'continent':
                self._get_continent()
            elif self.state == 'country':
                self._get_country()
            elif self.state == 'protocol':
                self._get_protocol()
            elif self.state == 'server':
                self._get_server()
        else:
            print_quit("Too many choices")

    @retry_on_conn_error
    def send_request(self, creds):
        payload = {'server': self.server['id']}
        r = self.sess.post(self.server['create_url'], data=payload, timeout=10)
        data = {
            "serverid": self.server['id'],
            "username": creds[0],
            "password": creds[1],
            "create": ''
        }
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;" +
                      "q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Host": "www.tcpvpn.com",
            "Origin": self.HOME_URL,
            "Referer": self.server['create_url'],
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.USER_AGENT
        }
        r = self.sess.post(
            self.server['create_url'], data, headers=headers, timeout=10)
        match = re.search(r'Account will expire on (?P<date>.*?)\.', r.text)
        if not match:
            return False
        return datetime.strptime(match.group(1), "%d-%B-%Y")

    def create_account(self, creds):
        self.state_loop()
        self.get_serv_details()
        return self.send_request(creds)


def create_account(serv_name=None, force_dl=False):
    tcpvpn = TCPVPNServAccCreator(serv_name, force_dl)
    creds = credentials['defaults']
    creds = creds['username'].replace('tcpvpn.com-', ''), creds['password']

    for _ in range(5):
        try:
            expires_at = tcpvpn.create_account(creds)
        except requests.exceptions.Timeout:
            print("Timed out")
            return None
        if expires_at:
            serv_name = tcpvpn.serv_name
            break
        creds = secrets.token_urlsafe(9), secrets.token_urlsafe(9)
    else:
        return None
    credentials[serv_name] = {
        "username": 'tcpvpn.com-' + creds[0],
        "password": creds[1],
        "expires_at": expires_at
    }
    write_toml(credentials, 'creds.toml')
    return credentials[serv_name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', "--force-dl-config", action='store_true')
    parser.add_argument("server", nargs="?")
    args = parser.parse_args()
    name = None
    if args.server:
        name = process.extractOne(
            args.server, serv_paths.keys(), score_cutoff=50)
        name = name and name[0]

    creds = create_account(name, force_dl=args.force_dl_config)
    if creds:
        print("Created account:")
        print(creds)
        # for k, v in creds:
        #     print(k.capitalize().replace('_', ' '), v, sep=': ')
    else:
        print("Failed to create account")


if __name__ == '__main__':
    main()
