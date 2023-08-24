from pythonosc import dispatcher, osc_server, udp_client
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port, check_if_tcp_port_open, check_if_udp_port_open
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from json import load
import sys
import os
from threading import Thread, Lock
import time


def get_absolute_path(relative_path, script_path=__file__) -> str:
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(script_path)))
    return os.path.join(base_path, relative_path)


def print_padded(parameter, value):
    if isinstance(value, float):
        value = f"{value:.4f}"
    print(f"{parameter.ljust(23, ' ')}\t{value}")


def wait_get_oscquery_client():
    service_info = None
    while service_info is None:
        print("Waiting for VRChat to be discovered...")
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    print("VRChat discovered!")
    client = OSCQueryClient(service_info)
    while client.query_node(osc_avatar_change) is None:
        print("Waiting for VRChat to be ready...")
        time.sleep(2)
    return OSCQueryClient(service_info)


def reset_params():
    global params, curr_avatar, config

    curr_avatar = qclient.query_node(osc_avatar_change).value[0]
    print_padded("Current Avatar:", curr_avatar)
    for param in config["parameters"]:
        addr = osc_parameter_prefix + param
        try:
            params[addr] = qclient.query_node(addr).value[0]
            print_padded(param, params[addr])
        except:
            print_padded(param, None)

def set_avatar_change(addr, value):
    global params, osc_client, avatar_changed, curr_avatar
    avatar_changed = curr_avatar != value
    if not avatar_changed:
        print("Avatar Reset, clearing parameters")
        reset_params()
        return

    curr_avatar = value
    print("Avatar changed, resending parameters:")
    for key, val in params.items():
        if val is None:
            continue
        print_padded(key[key.rindex("/") + 1:], val)
        osc_client.send_message(key, val)


def receive_message(addr, value):
    global params, avatar_changed

    time.sleep(0.5)
    if avatar_changed:
        time.sleep(1)
        avatar_changed = False
        return
    global params
    params[addr] = value
    print(f"Received message: {addr} {value}")


def osc_server_serve():
    print(f"Starting OSC client on {osc_server_ip}:{osc_server_port}:{http_port}")
    server.serve_forever(2)


config: dict = load(open(get_absolute_path("config.json", __file__)))
osc_parameter_prefix = "/avatar/parameters/"
osc_avatar_change = "/avatar/change"

qclient = wait_get_oscquery_client()

params = {}
reset_params()
avatar_changed = False

osc_server_ip = config["ip"]
osc_server_port = config["server_port"]
http_port = config["http_port"]
if osc_server_port != 9001:
    print("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
    if osc_server_port <= 0 or not check_if_udp_port_open(osc_server_port):
        osc_server_port = get_open_udp_port()
    if http_port <= 0 or not check_if_tcp_port_open(http_port):
        http_port = osc_server_port if check_if_tcp_port_open(osc_server_port) else get_open_tcp_port()
else:
    print("OSC Server port is default.")

osc_client = udp_client.SimpleUDPClient(osc_server_ip, config["port"])

disp = dispatcher.Dispatcher()
disp.map(osc_avatar_change, set_avatar_change)
for param in config["parameters"]:
    disp.map(osc_parameter_prefix + param, receive_message)
server = osc_server.ThreadingOSCUDPServer((osc_server_ip, osc_server_port), disp)
Thread(target=osc_server_serve, daemon=True).start()

oscqs = OSCQueryService("AvatarParameterSync", http_port, osc_server_port)
oscqs.advertise_endpoint(osc_avatar_change, access="readwrite")
for param in config["parameters"]:
    oscqs.advertise_endpoint(osc_parameter_prefix + param, access="readwrite")

while True:
    time.sleep(1)