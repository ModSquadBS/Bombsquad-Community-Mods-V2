# ba_meta require api 6
# Made By: AwesomeLogic

import urllib
import json
import os

import ba

REPO = 'ModSquadBS/Bombsquad-Community-Mods-V2'
BRANCH = 'master'
DL = 'https://raw.githubusercontent.com/{}/{}/{}/{}'
INDEX_URL = DL.format(REPO, BRANCH,'' ,'index.json')

mods_dir = ba.app.python_directory_user

def get_index():
	index = json.loads(urllib.request.urlopen(INDEX_URL).read().decode())
	local_mods = os.listdir(mods_dir)
	for mod, data in index.items():
		mod = mod+'.py'
		if mod not in local_mods:
			print('\'{}\' not in local_mods. Downloading...'.format(mod))
			download(mod,data['category']) #looks so ez

def download(name,category):
	data = urllib.request.urlopen(DL.format(REPO,BRANCH,category,name)).read().decode()
	open(name,'w').write(datas)

# ba_meta export plugin
class Enable_Me(ba.Plugin):
    def on_app_launch(self):
        get_index()