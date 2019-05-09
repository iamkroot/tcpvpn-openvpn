# OpenVPN - tcpvpn.com Integrator

This is a program built to automate creation of accounts on [tcpvpn.com](https://tcpvpn.com), followed by connecting via OpenVPN.

## DEPRECATED

tcpvpn.com has recently enforced a CAPTCHA requirement for creating the VPN Account on all of their servers. So this project is pretty much dead. You can still use the openvpn part as long you keep manually updating the credentials and their expiry date.

## Usage Instructions
### Installation
1. Ensure that you have Python 3.6 or higher, with pipenv installed.
2. Run `pipenv install` from project directory to create the virtualenv and install the requirements.

NOTE: The program currently only supports the openvpn client management in Linux. For Windows, once the config file is downloaded and creds are created, you can use the OpenVPN GUI to start the connection.

### First Run
1. Rename the `sample_creds.toml` file to `creds.toml`, and edit the default credentials to your preferred ones. In case those aren't available, the program will generate random creds.
2. Rename the `sample_config.toml` file to `config.toml` and add the necessary info. The names in `serv_priorities` needn't be exact, they will be matched fuzzily with the servers for which details have been stored previously. 
3. The program stores the details for the servers of tcpvpn.com the first time they are encountered. So, to add support for a new server, just use `pipenv run tcpvpn.py` and follow the on-screen menu to navigate to your preferred server. It will download the config, and create an account on that server.
 
- If you want to manually create new accounts, you can use `pipenv run tcpvpn.py <serv_name>`.
- If you want to force re-download the config files for the server, you can pass the `-f` flag to the command: `pipenv run tcpvpn.com <serv_name> -f`.

### Normal Use
The program has been designed to require minimal input during normal use, to support easy scripting. All you have to do is run `pipenv run main.py` and the program will:
1. Select your most preferred server (specified in `config.toml` using `serv_priorities`) and determine the `.ovpn` config file to be used.
2. Check if its credentials have expired. If they have, it will try to create an account on tcpvpn.com for that server automatically.
3. Connect to the server by running OpenVPN client in daemon mode, and exit if successful.
4. If steps 2 or 3 fail, it will continue to you next choice of preferred servers.

To stop the OpenVPN client, run `pipenv run main.py -k`, which will kill the current instance if it is running.

You can manually specify the server to be connected to by passing it as an argument: `pipenv run main.py <serv_name>` (again, the serv_name will be fuzzy-matched, so no need to be exact).

## Author
- Krut Patel
