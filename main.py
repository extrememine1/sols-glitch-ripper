# glitch ripper

import os
import asyncio
import threading
import requests
import json
import time
from pygame import mixer
import re

from ttkbootstrap import *
from windows_toasts import *
data = {}
template = {
    'Webhooks': {},
    'Server': '',
    'Biome Stats': {
        'WINDY': 0,
        'RAINY': 0,
        'SNOWY': 0,
        'SAND STORM': 0,
        'HELL': 0,
        'STARFALL': 0,
        'CORRUPTION': 0,
        'NULL': 0,
        'GLITCHED': 0,
        'DREAMSPACE': 0,
    },
    'Rare Biome Sound': 'sounds/realglitchnotif.mp3',
    'PresetData': 'https://raw.githubusercontent.com/extrememine1/presetdata/refs/heads/main/fixedData.json',
}

mixer.init()

macroName = 'glitch-ripper-v1.1'

url_pattern = re.compile(r'https?://[^\s]+')
game_pattern = r"https:\/\/www\.roblox\.com\/games\/(\d+)\/[^?]+\?privateServerLinkCode=(\d+)"
share_pattern = r"https:\/\/www\.roblox\.com\/share\?code=([a-f0-9]+)&type=([A-Za-z]+)"

try:
    with open('configs.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    data = template

def saveConfig():
    global data

    data.update({k: v for k, v in template.items() if k not in data})

    with open('configs.json', 'w') as file:
        json.dump(data, file)

saveConfig()

# class ----------------------------------------------------
class LogSniper:
    # main methods
    def __init__(self, data):
        self.path = os.path.join(os.getenv('LOCALAPPDATA'), 'Roblox', 'logs')

        self.webhooks = data['Webhooks'].values
        self.pslink = data['Server']

        self.data = requests.get(data['PresetData'])

        # temp vars
        self.last_biome = None
        self.active = True

        self.blacklisted_files = []

        self.prev_file = None

    def event(self, coro):
        self.events[coro.__name__] = coro
        return coro

    # method
    def get_latest_log_file(self):
        files = [os.path.join(self.path, f) for f in os.listdir(self.path) if f.endswith('.log')]
        latest_file = max(files, key=os.path.getmtime)
        return latest_file

    def convert_roblox_link(self): # credits to dan and yeswe
        url = self.pslink
        match_game = re.match(game_pattern, url)

        if match_game:
            place_id = match_game.group(1)
            link_code = match_game.group(2)
            if place_id != "15532962292":
                return None
            link_code = ''.join(filter(str.isdigit, link_code))
            return f"roblox://placeID={place_id}&linkCode={link_code}"

        match_share = re.match(share_pattern, url)
        if match_share:
            code = match_share.group(1)
            share_type = match_share.group(2)
            if "Server" in share_type:
                share_type = "Server"
            elif "ExperienceInvite" in share_type:
                share_type = "ExperienceInvite"
            return f"roblox://navigation/share_links?code={code}&type={share_type}"
        return None

    def read_logfile(self, filepath):
        if self.prev_file != filepath:
            self.last_position = 0

        self.prev_file = self.get_latest_log_file()

        if not os.path.exists(filepath):
            print('DEBUG: File not found')
            return []

        with open(filepath, 'r', errors='ignore') as file:
            if hasattr(self, 'last_position'):
                file.seek(self.last_position)

            lines = file.readlines()
            self.last_position = file.tell()

            return lines

    def on_shutdown(self):
        timestamp = int(time.time())
        discord_time = f"<t:{timestamp}:R>"

        payload = {
            'embeds': [{
                'title': f'Macro Ended',
                'description': 'Macro has been stopped',
                'footer': {'text': macroName},
                'color': 0xFF0000
            }]
        }

        for webhook in self.webhooks:
            requests.post(webhook, json=payload)

        print('Logger is shutting down...')

        saveConfig()

        return

    async def check_biome(self): # this function calls read logs and get latest already
        logpath = self.get_latest_log_file()
        log_lines = self.read_logfile(logpath)

        for line in reversed(log_lines):
            for biome in self.data.keys():
                if biome in line:
                    await self.biomedetected(biome)

                    return

    # async methods
    async def biomedetected(self, biome): # type(str)
        rare_biome = biome in (self.data['glitch_keywords'] + self.data['dream_keywords'])
        valid = False
        updateCounter = False

        payload = {
            'username': 'Macro Notification',
            'content': '@everyone' if rare_biome else ''
        }

        embeds = []
        embed1 = {}

        timestamp = int(time.time())
        discord_time = f"<t:{timestamp}:R>"

        # code goes here
        title = ''
        description = ''

        if rare_biome:
            updateCounter = True
            embed1['title'] = f'# Rare Biome Detected: {biome}'
            embed1['description'] = f'Private Server Link:\n{data["Server"]}'

            fields = [
                {
                    'name': 'Biome Found at',
                    'value': discord_time,
                    'inline': True
                },
                {
                    'name': 'Biome Ending in',
                    'value': f'<t:{timestamp + self.data[biome]["duration"]}:R>',
                    'inline': True
                }
            ]

            embed1['fields'] = fields
            self.last_biome = biome

            valid = True

            if os.path.isfile(self.glitchnotif):
                mixer.music.load(self.glitchnotif)
                mixer.music.play()
            else:
                print("⚠️ Sound file not found.")

        elif self.last_biome:
            embed1['title'] = f'{self.last_biome} has ended'
            embed1['description'] = ''

            self.last_biome = None
            valid = True

        elif biome == 'NORMAL':
            pass

        else:
            updateCounter = True
            embed1['title'] = f'Biome Detected: {biome}'
            embed1['description'] = f'Terminating current instance...'

            valid = True

            os.startfile(self.convert_roblox_link())

        if valid:
            embed1['footer']: {'text': macroName}

            embeds.append(embed1)
            payload['embeds'] = embeds

            for hook in self.webhooks:
                res = requests.post(hook, json=payload)
                print(res.status_code)

            valid = False

            populate(biome, updateCounter)

    # main loop
    async def run(self):
        timestamp = int(time.time())
        discord_time = f"<t:{timestamp}:R>"

        if 'RobloxPlayerBeta.exe' not in [proc.info['name'] for proc in psutil.process_iter(['pid', 'name'])]:
            self.blacklisted_files.append(self.get_latest_log_file())

        payload = {
            'username': 'Macro Bot',
            'embeds': [
                {
                    'title': f'Macro Started',
                    'description': 'The macro has started running!',
                    'footer': {'text': macroName},
                    'color': 0x00FF00
                }
            ]
        }

        for webhook in self.webhooks:
            requests.post(webhook, json=payload)

        while self.active:
            await self.check_biome()
            await asyncio.sleep(1)

# Functions -------------------------------------------------
def startMacro():
    global startButton

    logger.webhooks = [hook for hook in data['Webhooks'].values()]
    logger.pslink = data['Server']

    startButton['state'] = 'disabled'
    statusLabel.config(text='Status: Running', bootstyle='success')

    def run_logger():
        try:
            asyncio.run(logger.run())
        except Exception as e:
            print(f"[Logger Error] {e}")

    threading.Thread(target=run_logger, daemon=True).start()

def populate(biome, add):
    populates['biomeLabel'].config(text=f'Biome: {biome}')

    if add:
        if biome in data['Biome Stats']:
            data['Biome Stats'][biome] += 1
        elif biome != 'NORMAL':
            data['Biome Stats'][biome] = 1  # fallback in case biome is missing

    if biome in populates['biomeLabels']:
        populates['biomeLabels'][biome].config(text=f"{biome}: {data['Biome Stats'][biome]}")

    populates['totalNum'].config(text=f'Total Biomes: {sum(data["Biome Stats"].values())}')

    saveConfig()


# ALL UI -------------------------------------------------------------------------
# create root
root = Window(
    themename='darkly',
    title=macroName,
)

logger = LogSniper(data)

def shutdown_handler():
    logger.on_shutdown()
    root.destroy()

root.wm_protocol('WM_DELETE_WINDOW', shutdown_handler)

populates = {}

# toast notifier
toaster = WindowsToaster('Macro')
newToast = Toast()

# notebook
notebook = Notebook(root)
notebook.grid(row=0, column=0, padx=5, pady=5)

# main settings ----------------------------------------------
configsWin = Frame(notebook)
notebook.add(configsWin, text='Configs')

# private server link frame ------------------------------------------------
def psSave():
    link = psEntry.get()
    data['Server'] = link

    newToast.text_fields = [f'Server link saved as {link}']
    toaster.show_toast(newToast)

    saveConfig()

frame2 = LabelFrame(configsWin, text='Private Server')
frame2.grid(row=0, column=0, pady=10, padx=10, sticky='ew')

lbl3 = Label(frame2, text='Private Server Link', font=('Arial', 15, 'bold'), anchor='w')
lbl3.grid(row=0, column=0, padx=10, pady=5, sticky='w')

lbl4 = Label(frame2, text='Insert your private server link in here for the webhook to send.', anchor='w')
lbl4.grid(row=1, column=0, padx=10, sticky='w')

psFrame = Frame(frame2)
psFrame.grid(row=2, column=0, sticky='ew')

psEntry = Entry(psFrame, width=60)
psEntry.grid(row=0, column=0, padx=10, pady=5, sticky='ew')
psEntry.insert(0, data.get('Server', ''))

psButton = Button(psFrame, text='Save', command=psSave)
psButton.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')

# Webhook Frame -----------------------------------------------------------------
def webhookSave():
    hook = hookEntry.get()
    data['Webhooks'] = {'placeholder': hook}

    newToast.text_fields = [f'Webhook saved as {hook}']
    toaster.show_toast(newToast)

    saveConfig()

frame3 = LabelFrame(configsWin, text='Webhook')
frame3.grid(row=1, column=0, pady=10, padx=10, sticky='ew')

lbl5 = Label(frame3, text='Webhook Link', font=('Arial', 15, 'bold'), anchor='w')
lbl5.grid(row=0, column=0, padx=10, pady=5, sticky='w')

lbl6 = Label(frame3, text='Insert your webhook link in here.', anchor='w')
lbl6.grid(row=1, column=0, padx=10, sticky='w')

hookFrame = Frame(frame3)
hookFrame.grid(row=2, column=0, sticky='ew')

hookEntry = Entry(hookFrame, width=60)
hookEntry.grid(row=0, column=0, padx=10, pady=5, sticky='ew')
hookEntry.insert(0, data['Webhooks'].get('placeholder', ''))

hookButton = Button(hookFrame, text='Save', command=webhookSave)
hookButton.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')

# Biome frame ------------------------------------------------------------------
biomeFrame = Frame(notebook)
notebook.add(biomeFrame, text='Active Biome')

biomeLabel = Label(biomeFrame, text=f'Waiting to start...', font=('Arial', 30, 'bold'))
biomeLabel.grid(row=0, column=0)
populates['biomeLabel'] = biomeLabel

biomecountFrame = Frame(biomeFrame)
biomecountFrame.grid(row=1, column=0, sticky='nsew')

row, column = 0, 0
populates['biomeLabels'] = {}

for biome, number in data['Biome Stats'].items():
    biom = Label(
        biomecountFrame,
        text=f'{biome}: {number}',
    )
    biom.grid(row=row, column=column, padx=25, pady=25)
    populates['biomeLabels'][biome] = biom

    if row >= 1:
        row = 0
        column += 1
    else:
        row += 1

totalNum = Label(biomeFrame, text=f'Total biomes: {sum(data["Biome Stats"].values())}')
totalNum.grid(row=2, column=0)
populates['totalNum'] = totalNum

# start/stop buttons and status --------------------------------
controlFrame = Frame(root)
controlFrame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)

statusLabel = Label(controlFrame, text='Status: Stopped', bootstyle='danger', font=('Arial', 10))
statusLabel.pack(side='left')

startButton = Button(controlFrame, text='Start', command=startMacro)
startButton.pack(side='right')

# mainloop
root.mainloop()

# saving
saveConfig()
