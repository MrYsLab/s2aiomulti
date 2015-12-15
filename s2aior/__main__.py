import asyncio
import configparser
import os
import signal
import subprocess
import sys

import aiohttp
from aiohttp import web


# noinspection PyMethodMayBeStatic,PyShadowingNames
class S2AIOR:
    def __init__(self):
        path = sys.path

        # get the prefix
        prefix = sys.prefix
        for p in path:
            # make sure the prefix is in the path to avoid false positives
            if prefix in p:
                # look for the configuration directory
                s_path = p + '/s2aior/configuration'
                if os.path.isdir(s_path):
                    # found it, set the base path
                    self.base_path = p + '/s2aior'

        if not self.base_path:
            print('Cannot locate s2aio configuration directory.')
            sys.exit(0)

        print('\n\n!!!!!! The Configuration File is located at: ' + self.base_path + ' !!!!!!\n\n')

        # grab the config file and get it ready for parsing
        config = configparser.ConfigParser()
        config_file_path = str(self.base_path + '/configuration/configuration.cfg')
        config.read(config_file_path, encoding="utf8")

        # parse the file and place the translation information into the appropriate variable
        self.ln_languages = config.get('translation_lists', 'ln_languages').split(',')
        self.ln_ENABLE = config.get('translation_lists', 'ln_ENABLE').split(',')
        self.ln_DISABLE = config.get('translation_lists', 'ln_DISABLE').split(',')
        self.ln_INPUT = config.get('translation_lists', 'ln_INPUT').split(',')
        self.ln_OUTPUT = config.get('translation_lists', 'ln_OUTPUT').split(',')
        self.ln_PWM = config.get('translation_lists', 'ln_PWM').split(',')
        self.ln_SERVO = config.get('translation_lists', 'ln_SERVO').split(',')
        self.ln_TONE = config.get('translation_lists', 'ln_TONE').split(',')
        self.ln_SONAR = config.get('translation_lists', 'ln_SONAR').split(',')
        self.ln_OFF = config.get('translation_lists', 'ln_OFF').split(',')
        self.ln_ON = config.get('translation_lists', 'ln_ON').split(',')

        # build the arduino routing map
        self.route_map = []
        self.connections = []

        self.poll_reply = ""

        # board numbers range from 1 to 10
        for board_number in range(1, 11):
            # create the section name
            board_string = 'board' + str(board_number)
            # create a dictionary for this section
            items = dict(config.items(board_string))
            # add it to the route map
            self.route_map.append(items)

        loop = asyncio.get_event_loop()
        self.client = aiohttp.ClientSession(loop=loop)

    async def fetch_page(self, url):
        # x = urllib.request.urlopen(url)
        # x.read()
        async with self.client.get(url) as response:
            return await response.read()

    async def setup_digital_pin(self, request):
        command = "digital_pin_mode"
        board = request.match_info.get('board')
        enable = request.match_info.get('enable')
        pin = request.match_info.get('pin')
        mode = request.match_info.get('mode')
        # server_addr = "127.0.0.1"
        # server_port = "50214"
        command_string = command + '/' + enable + '/' + pin + "/" + mode
        await self.route_command(board, command_string)
        # loop = asyncio.get_event_loop()
        # client = aiohttp.ClientSession(loop=loop)
        # content = await self.fetch_page(client, rstring)
        # async with aiohttp.request('GET', rstring) as resp:
        # assert resp.status == 200
        #     print(resp.status)
        # print(await resp.text())
        # print(content)

        return web.Response(body="ok".encode('utf-8'))

    async def setup_analog_pin(self, request):
        command = "analog_pin_mode"
        board = request.match_info.get('board')
        enable = request.match_info.get('enable')
        pin = request.match_info.get('pin')
        command_string = command + '/' + enable + '/' + pin
        await self.route_command(board, command_string)
        return web.Response(body="ok".encode('utf-8'))

    async def digital_write(self, request):
        command = "digital_write"
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')
        value = request.match_info.get('value')
        command_string = command + '/' + pin + '/' + value
        await self.route_command(board, command_string)
        return web.Response(body="ok".encode('utf-8'))

    async def play_tone(self, request):
        command = 'play_tone'
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')
        freq = request.match_info.get('frequency')
        duration = request.match_info.get('duration')
        command_string = command + '/' + pin + '/' + freq + '/' + duration
        await self.route_command(board, command_string)
        return web.Response(body="ok".encode('utf-8'))

    async def tone_off(self, request):
        command = 'tone_off'
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')

        command_string = command + '/' + pin
        await self.route_command(board, command_string)
        return web.Response(body="ok".encode('utf-8'))

    async def set_servo_position(self, request):
        command = 'set_servo_position'
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')
        position = request.match_info.get('position')

        command_string = command + '/' + pin + '/' + position
        await self.route_command(board, command_string)
        return web.Response(body="ok".encode('utf-8'))

    # noinspection PyUnusedLocal
    async def poll(self, request):
        # save the reply to a temporary variable
        total_reply = self.poll_reply

        # clear the poll reply string for the next reply set
        self.poll_reply = ""
        return web.Response(headers={"Access-Control-Allow-Origin": "*"},
                            content_type="text/html", charset="ISO-8859-1", text=total_reply)

    async def got_analog_report(self, request):
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')
        value = request.match_info.get('value')
        self.poll_reply += 'analog_read/' + board + '/' + pin + ' ' + value + '\n'
        # print(request)        # print('aa')
        return web.Response(body="ok".encode('utf-8'))

    async def got_digital_report(self, request):
        board = request.match_info.get('board')
        pin = request.match_info.get('pin')
        value = request.match_info.get('value')
        self.poll_reply += 'digital_read/' + board + '/' + pin + ' ' + value + '\n'
        # print(request)        # print('aa')
        return web.Response(body="ok".encode('utf-8'))

    async def got_problem_report(self, request):
        board = request.match_info.get('board')
        problem = request.match_info.get('problem')
        self.poll_reply += 'problem/' + board + ' ' + problem + '\n'
        return web.Response(body="ok".encode('utf-8'))

    async def route_command(self, board, command):
        # get http server address and port for the board
        route = self.route_map[int(board) - 1]
        server_addr = route['http_server_address']
        server_port = route['http_server_port']

        url = "http://" + server_addr + ":" + server_port + '/' + command
        await self.fetch_page(url)

    # noinspection PyShadowingNames
    async def init(self, loop):
        app = web.Application(loop=loop)
        app.router.add_route('GET', '/digital_pin_mode/{board}/{enable}/{pin}/{mode}', self.setup_digital_pin)
        app.router.add_route('GET', '/analog_pin_mode/{board}/{enable}/{pin}', self.setup_analog_pin)
        app.router.add_route('GET', '/digital_write/{board}/{pin}/{value}', self.digital_write)
        # app.router.add_route('GET', '/poll', self.poll)
        app.router.add_route('Get', '/analog_read/{board}/{pin}/{value}', self.got_analog_report)
        app.router.add_route('Get', '/digital_read/{board}/{pin}/{value}', self.got_digital_report)
        app.router.add_route('GET', '/play_tone/{board}/{pin}/{frequency}/{duration}', self.play_tone)

        app.router.add_route('Get', '/problem/{board}/{problem}', self.got_problem_report)
        app.router.add_route('GET', '/set_servo_position/{board}/{pin}/{position}', self.set_servo_position)
        app.router.add_route('GET', '/tone_off/{board}/{pin}', self.tone_off)

        srv = await loop.create_server(app.make_handler(), '127.0.0.1', 50208)

        # instantiate all of the arduino servers
        for x in self.route_map:
            if x['active'] == 'yes':
                #         # usb connected device
                board_id = x['board_id']
                com_port = x['com_port']
                server_address = x['http_server_address']
                server_port = x['http_server_port']
                arduino_ip_address = x['arduino_ip_address']
                arduino_ip_port = x['arduino_ip_port']
                router_ip_address = x['router_address']
                router_ip_port = x['router_port']
                if com_port != 'None':
                    new_s2aios = ['s2aios', '-p', com_port, '-sa', server_address, '-sp', server_port, '-b', board_id,
                                  '-ra', router_ip_address, '-rp', router_ip_port]
                else:
                    new_s2aios = ['s2aios', '-aa', arduino_ip_address, '-ap', arduino_ip_port, '-sa',
                                  server_address, '-sp', server_port, '-b', board_id,
                                  '-ra', router_ip_address, '-rp', router_ip_port]

                print('starting: ' + str(new_s2aios))
                x = subprocess.Popen(new_s2aios)
                self.connections.append(x)
                await asyncio.sleep(5)
        print("Arduino Servers Configured")
        app.router.add_route('GET', '/poll', self.poll)
        await self.keep_alive()

        return srv

    async def keep_alive(self):
        """
        This method is used to keep the server up and running when not connected to Scratch
        :return:
        """
        while True:
            await asyncio.sleep(1)


def main():
    # noinspection PyShadowingNames
    loop = asyncio.get_event_loop()
    s2aior = S2AIOR()

    # noinspection PyBroadException
    try:
        loop.run_until_complete(s2aior.init(loop))
    except:
        # noinspection PyShadowingNames
        loop = asyncio.get_event_loop()

        sys.exit(0)

    # signal handler function called when Control-C occurs
    # noinspection PyShadowingNames,PyUnusedLocal,PyUnusedLocal
    def signal_handler(signal, frame):
        print("Control-C detected. See you soon.")
        s2aior.client.close()

        for x in s2aior.connections:
            x.kill()

        for t in asyncio.Task.all_tasks(loop):
            # noinspection PyBroadException
            try:
                t.cancel()
                loop.run_until_complete(asyncio.sleep(.1))
                loop.stop()
                loop.close()
            except:
                pass

        sys.exit(0)

    # listen for SIGINT
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:

        sys.exit(0)

    loop = asyncio.get_event_loop()

    # noinspection PyBroadException
    try:
        loop.run_forever()
        loop.stop()
        loop.close()
    except:
        pass