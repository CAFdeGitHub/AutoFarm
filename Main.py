import os, requests
# from ReadWriteMemory import ReadWriteMemory
# from Mage import Mage
from MapInfo import MapInfo
from Visualization import MapVisualization
from GameMemeoryManager import GameMemeoryManager
from time import sleep



# rwm = ReadWriteMemory()
# process = rwm.get_process_by_name('WingsMS.exe')
# process.open()


if __name__ == "__main__":
	# character = Mage(jump_key="c", attack_key="b", buff_key="d", buff_interval=450, pet_potion_key="l", teleport_key="v", hs_key="j", hs_location_list=[(-58, 998)], door_key="u", farm_mapid=240040511, fast_tc=False, enable_relocate=True, relocate_fail_method="lower_jump")
	# mapid = 103000200
	# character.get_mapid()
	game_process = GameMemeoryManager("WingsMS.exe")
	character = Character(game_process, jump_key="c", attack_key="z", buff_key="d", buff_interval=450, pet_potion_key="l", debug=True)
	mapid = character.get_mapid()
	if not os.path.exists(f"{mapid}.img.xml"):
		print("map not in directory")
		url = f"https://raw.githubusercontent.com/ronancpl/HeavenMS/master/wz/Map.wz/Map/Map{mapid // 10 ** 8}/{mapid}.img.xml"
		r = requests.get(url, allow_redirects=True)
		open(f"{mapid}.img.xml", "wb").write(r.content)
	mapinfo = MapInfo(mapid, game_process, refresh_time=1, debug=True)
	mapinfo.start()
	mapvisual = MapVisualization(mapinfo.flist, mapinfo.ladderlist, mapinfo.mob_count + 10, refresh_time=1)
	mapvisual.start()
	# mapvisual.initialize_map()
	# chara_coor = (974, 260)
	# mob_coor_list = [(-305, 323), (-205, 323), (-105, 323), (-5, 323), (20, 323), (120, 323), (220, 323)]
	# mapvisual.plot_map(mapinfo.character_coor, mapinfo.all_mob_coor)
	sleep(10)
	while True:
		mapvisual.update_mapinfo(mapinfo)
		sleep(1)
	# for i in range(10):
		# mapvisual.plot_map((974+i*100, 260), mob_coor_list)
		# sleep(1)
		# chara_coor[0] = chara_coor[0] + 10
		# mob_coor_list = [(mobx + 10, moby) for mobx, moby in mob_coor_list]
	# mapvisual.plot_ladder(mapinfo.edge_dict["ladder_edge"])



	