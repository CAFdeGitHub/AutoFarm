import xml.etree.ElementTree as ET
from itertools import chain, tee
from threading import Thread, Lock
from Maputil import *
import igraph as ig
import pandas as pd


DIRECT_JUMP_COST = 50
FALLING_COST = 50
LOWER_JUMP_COST = 100
FORWARD_JUMP_COST = 50
LADDER_COST = 50

## cost for each action of such.

class MapInfo:

	MINIMAP_X_ADDRESS_LIST = [0x400000 + 0x007ED788, 0x648, 0x24, 0x640, 0x24, 0x5D4]  # address in minimap, use this address
	MINIMAP_Y_ADDRESS_LIST = [0x400000 + 0x007ED788, 0x648, 0x24, 0x640, 0x24, 0x5D8]  # address in minimap, use this address

	X_ADDRESS_LIST = [0xBEBF98, 0x3124] # true coor without minimap. warning: this value will reset to zero when entering map
	Y_ADDRESS_LIST = [0xBEBF98, 0x3128] # true coor without minimap. warning: this value will reset to zero when entering map

	MOB_COUNT_LIST = [0xBEBFA4, 0x24]
	MOB_X_LIST = [0xBEBFA4, 0x28, 0x4, 0x120, 0x24, 0x60]  # this is x of one of all mob. to find other, we should add or minus n * (0x1c) in the third offset
	MOB_Y_LIST = [0xBEBFA4, 0x28, 0x4, 0x120, 0x24, 0x64]  # 0x28 -> 0x2c is start verus end?.  check 0x8 is 0x18

	MOB_LINK_LIST_ADDRESS_LIST1 = [0xBEBFA4, 0x28, -0x10]
	MOB_LINK_LIST_ADDRESS_LIST2 = [0xBEBFA4, 0x2c, -0x10]
	MOB_X_OFFSET = [0x14, 0x120, 0x24, 0x60]
	MOB_Y_OFFSET = [0x14, 0x120, 0x24, 0x64]


	def __init__(self, mapid, game_process, refresh_time=1, debug=False):
		self.mapid = mapid
		self.game_process = game_process
		self.debug = debug
		self.refresh_time = refresh_time
		self.life_property_lock = Lock()


	def start(self):
		self.stopped = False
		self.generate_all_mapinfo()
		t = Thread(target=self.update_life_info)
        t.start()


	def update_life_info(self):
		while not self.stopped:
			self.generate_life_coor()
			sleep(self.update_interval)


	def stop(self):
		self.stopped = True



	def get_the_closest_mob(self):
		self.life_property_lock.acquire()
		mob_cor = np.array(self.all_mob_coor)
		diff = mob_cor - np.array(self.character_coor)
		dist = np.abs(diff[0]) + 2 * np.abs(diff[1]) ## dist heuritic
		self.target_mob_idx = np.argsort(dist)
		self.target_mob_add = self.mob_add_list[self.target_mob_idx]
		self.target_mob_coor = self.all_mob_coor[self.target_mob_idx]
		self.life_property_lock.release()
		return self.target_mob_add, self.target_mob_coor



	def generate_map(self):
		tree = ET.parse(f'{self.mapid}.img.xml')
		root = tree.getroot()

		foothold = root.findall(".//*[@name='foothold']/")
		ladder = root.findall(".//*[@name='ladderRope']/")
		# generate simplified footholds list
		flist = [] # footholds list
		for r in foothold:
			ellist = []
			nodelist = []
			for el in r.findall("./imgdir/imgdir"):
				if el.find(".//*[@name='x1']") is not None:
					x1 = int(el.find(".//*[@name='x1']").attrib["value"])
					y1 = int(el.find(".//*[@name='y1']").attrib["value"])
					x2 = int(el.find(".//*[@name='x2']").attrib["value"])
					y2 = int(el.find(".//*[@name='y2']").attrib["value"])
					ellist.append([x1, x2, y1, y2, int(el.attrib["name"]), 
								   int(el.find(".//*[@name='prev']").attrib["value"]), int(el.find(".//*[@name='next']").attrib["value"])])
			arr = np.array(ellist)
			arr = arr[np.argsort(arr[:, 4]), :] # sort arr by the id of the name
			idtoidxdict = dict(zip(arr[:, 4], np.arange(arr.shape[0])))
			whether_wall = np.where((abs(arr[:, 2] - arr[:, 3])  >= abs(arr[:, 0] - arr[:, 1])))[0]  # ydiff larger than xdiff regarded as wall
			# the last column represent whether it's connective component
			wallid = set(arr[whether_wall, 4])
			wallid.add(0)
			visited = np.zeros(arr.shape[0]).astype(int)
			j=0
			while np.sum(visited[whether_wall]) < whether_wall.shape[0]: # search from wall first
				next_wall_idx = whether_wall[np.where(visited[whether_wall] == 0)[0][0]]
				visited[next_wall_idx] = 1
		#			 print("wall id ", next_wall_idx)
				if arr[next_wall_idx, 5] not in wallid:
		#				 print("processing", arr[next_wall_idx, 5] - idxshift)
					subnodelist = []
					generate_node(idtoidxdict[arr[next_wall_idx, 5]], arr[:, 4:], wallid, visited, subnodelist, idtoidxdict)
					if len(subnodelist) > 0:
						nodelist.append(subnodelist)
				if arr[next_wall_idx, 6] not in wallid:
		#				 print("processing", arr[next_wall_idx, 6] - idxshift)
					subnodelist = []
					generate_node(idtoidxdict[arr[next_wall_idx, 6]], arr[:, 4:], wallid, visited, subnodelist, idtoidxdict)
					if len(subnodelist) > 0:
						nodelist.append(subnodelist)
			while np.sum(visited) < arr.shape[0]: # seach other footholds
		#		 print("search ", np.where(visited == 0)[0][0])
				subnodelist = []
				generate_node(np.where(visited == 0)[0][0], arr[:, 4:], wallid, visited, subnodelist, idtoidxdict)
				if len(subnodelist) > 0:
					nodelist.append(subnodelist)
			for sublist in nodelist:
				subarr = arr[sublist, :]
				left_idx = np.argmin(subarr[:, :2])
				right_idx = np.argmax(subarr[:, :2])
				flist.append(Footholds(subarr[left_idx // 2, left_idx % 2], subarr[left_idx // 2, left_idx % 2 + 2], subarr[right_idx // 2, right_idx % 2],   subarr[right_idx // 2, right_idx % 2 + 2]))


		# merge some ft if it's too close
		mergelist = []
		for i in range(len(flist)):
			ft = flist[i]
			if ft.slope:
				for j in range(len(flist)):
					ft2 = flist[j]
					if ft2.slope:
						continue
					if twoline_intersect(ft.get_left_point(), ft.get_right_point(), ft2.get_left_point(), ft2.get_right_point()):
						mergelist.append((i, j))
		# merge them and append it to flist
		if len(mergelist) != 0:
			mergelist = np.array(mergelist)
			for nonslopeidx in np.unique(mergelist[:, 1]):
			#	 print(nonslopeidx)
				mernode = copy.deepcopy(flist[nonslopeidx])
				inner = []
				left_x, right_x = None, None
				for i in mergelist[mergelist[:, 1] == nonslopeidx, 0]:
					if flist[i].left_x < mernode.left_x:
						if self.debug:
							print(f"flist {i} to be merged")
						left_x = flist[i].left_x
						left_y = flist[i].left_y
						inner.append((mernode.left_x, mernode.left_y))
					if flist[i].right_x > mernode.right_x:
						if self.debug:
							print(f"flist {i} to be merged")
						right_x = flist[i].right_x
						right_y = flist[i].right_y
						inner.append((mernode.right_x, mernode.right_y))
				if left_x is None:
					left_x, left_y = mernode.left_x, mernode.left_y
				if right_x is None:
					right_x, right_y = mernode.right_x, mernode.right_y
				flist.append(MergedFootholds(left_x, left_y, right_x, right_y, sorted(inner, key=lambda x: x[0])))
			# delete the intersected node	
			for idx in np.sort(np.unique(mergelist))[::-1]:
				del flist[idx]
			
		## merge two component if it's close
		leftp = np.array([ft.get_left_point() for ft in flist])
		rightp = np.array([ft.get_right_point() for ft in flist])
		length = len(flist)
		mergeidx = []
		for i in range(length):
			ft = flist[i]
			for j in range(i + 1, length):
		#		 print(i, j)
				ft2 = flist[j]
				if np.all(np.abs(np.array(ft.get_left_point()) - np.array(ft2.get_right_point())) < MIN_GAP_TO_MERGE) and isinstance(ft, Footholds) and isinstance(ft2, Footholds):
					flist.append(MergedFootholds(*ft2.get_left_point(), *ft.get_right_point(), 
												[tuple((np.array(ft.get_left_point()) + np.array(ft2.get_right_point())) / 2)]))
					if self.debug:
						print(f"flist {i} {j} to be merged")
					mergeidx.append((i, j))
				if np.all(np.abs(np.array(ft.get_right_point()) - np.array(ft2.get_left_point())) < MIN_GAP_TO_MERGE) and isinstance(ft, Footholds) and isinstance(ft2, Footholds):
					flist.append(MergedFootholds(*ft.get_left_point(), *ft2.get_right_point(), 
												[tuple((np.array(ft.get_right_point()) + np.array(ft2.get_left_point())) / 2)]))
					if self.debug:
						print(f"flist {i} {j} to be merged")
					mergeidx.append((i, j))


		for idx in np.sort(np.array(mergeidx).flatten())[::-1]:
			del flist[idx]


		ladderlist = []
		for el in ladder:
			if el.find(".//*[@name='x']") is not None:
				x = int(el.find(".//*[@name='x']").attrib["value"])
				y1 = int(el.find(".//*[@name='y1']").attrib["value"])
				y2 = int(el.find(".//*[@name='y2']").attrib["value"])
				is_ladder = int(el.find(".//*[@name='l']").attrib["value"])
				ladderlist.append(Ladder(x, max(y1, y2), min(y1, y2), is_ladder))

		self.flist = sorted(flist, key = lambda ft: ft.lower_y)  ## higher y first.
		self.ladderlist = ladderlist


	def generate_lower_jump_edge(self, edge_dict):
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)
		floor_lower_y = np.array([ft.lower_y for ft in flist])
		lower_jump_edge = []
		edge_dict["lower_jump_edge"] = lower_jump_edge
		for ft in flist:
			diff = floor_lower_y - ft.lower_y
			retseg, _ = find_overlaps([flist[idx].get_plot_point()[0] for idx in np.where(np.logical_and(diff < 20, diff > 0))[0]], [ft.get_plot_point()[0]])
			if len(retseg) > 0:
				continue
			candidate = np.where(np.logical_and(LOWER_JUMP_Y_MIN_DIFF <= diff, diff<= LOWER_JUMP_Y_MAX_DIFF))[0]
			candidate = candidate[np.argsort(floor_lower_y[candidate])] # get sorted candidate. lower y first
			lineseg = [(ft.left_x, ft.right_x)]
			for idx in candidate:
				overlaps_list, overlaps_idx = find_overlaps(lineseg, [(flist[idx].left_x, flist[idx].right_x)])
				if len(overlaps_list) > 0:
					lower_jump_edge.append(LowerJumpArea(ft, flist[idx], 
														 [overlap for overlap in overlaps_list if overlap[1] - overlap[0] >= MIMIMUM_JUMP_AREA_WIDTH]))
					# only jump if the jump area is wide enough
					for i, overidx in enumerate(overlaps_idx):
						# add the nonoverlap area
						left = lineseg[overidx[0]][0]
						right = lineseg[overidx[0]][1]
						# discard area if it's short
						if 10 < overlaps_list[i][0] - left:						
							lineseg.append((left, overlaps_list[i][0]))
						if right - overlaps_list[i][1] > 10:
							lineseg.append((overlaps_list[i][1], right))
					for overidx in sorted(overlaps_idx, key=lambda x: x[0], reverse=True):
						# delete the area which is overlaped
						del lineseg[overidx[0]]
					lineseg = sorted(lineseg, key=lambda x: x[0])


	def generate_falling_edge(self, edge_dict):
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)
		left_x_arr = np.array([ft.left_x for ft in flist])
		right_x_arr = np.array([ft.right_x for ft in flist])
		falling_edge = []
		edge_dict["falling_edge"] = (falling_edge)
		for i, ft in enumerate(flist):
			candidate = np.where(np.logical_and(left_x_arr <= ft.left_x - MIN_GAP_TO_FALLING, ft.left_x <= right_x_arr))[0]
			# include MINGAP to exclude some scenario where two ft is the same at left and right
			# we should exclude the first candidate since it's ft it self.
			candidateidx = 0
			if len(candidate) > 0:
				while candidateidx < len(candidate):
					if ft.left_y <= flist[candidate[candidateidx]].y_at_location_x(ft.left_x):
						falling_edge.append(FallingArea(ft, flist[candidate[candidateidx]], "left"))
						break
					candidateidx += 1
			candidate = np.where(np.logical_and(left_x_arr <= ft.right_x, ft.right_x <= right_x_arr - MIN_GAP_TO_FALLING))[0]
			# we should exclude the first candidate since it's ft it self.
			candidateidx = 0
			if len(candidate) > 0:
				while candidateidx < len(candidate):
					if ft.right_y <= flist[candidate[candidateidx]].y_at_location_x(ft.right_x):
						falling_edge.append(FallingArea(ft, flist[candidate[candidateidx]], "right"))
						break
					candidateidx += 1


	def generate_forward_jump_edge(self, edge_dict):
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)
		leftp_arr = np.array([ft.get_left_point() for ft in flist])
		rightp_arr = np.array([ft.get_right_point() for ft in flist])
		forward_jump_edge = []
		edge_dict["forward_jump_edge"] = (forward_jump_edge)
		for i, ft in enumerate(flist):
			candidate = np.where(np.logical_and(
				ft.left_x > rightp_arr[:, 0], 
				rightp_arr[:, 0] + x_shift_by_forward_jump(rightp_arr[:, 1] - ft.left_y) >= ft.left_x))[0]
			# left forward jump only if our left is on the right side of other right and can reach the right by falling
			candidateidx = 0
			if candidate.shape[0] > 0: 
				## if there are multiple qualified candidate use the highest y which is the 0 elem cuz we sort flist
		#		 while candidateidx < candidate.shape[0]:
		#		 while candidateidx < 1:
				intersect = False
				for j in range(i+1, candidate[candidateidx]):
					ft2 = flist[j]
					if twoline_intersect((ft.left_x - JUMP_WIDTH//2, ft.left_y - JUMP_HEIGHT), 
										 (ft.left_x - x_shift_by_forward_jump(np.array([rightp_arr[candidate[candidateidx], 1] - ft.left_y])), flist[candidate[candidateidx]].right_y),
										 ft2.get_left_point(), ft2.get_right_point()
										):
						intersect = True
		#				 print("intersect on lj")
				if not intersect:
					forward_jump_edge.append(ForwardJumpArea(ft, flist[candidate[0]], "left"))
		#			 break
				candidateidx += 1
		#	 if candidate.shape[0] > 0: 
		#		 forward_jump_edge.append(ForwardJumpArea(ft, flist[candidate[0]], "left"))
				
			candidate = np.where(np.logical_and(
				ft.right_x < leftp_arr[:, 0], 
				leftp_arr[:, 0] <= ft.right_x + x_shift_by_forward_jump(leftp_arr[:, 1] - ft.right_y)))[0]
			# right forward jump only if our right is on the left side of other left and can reach the left by falling
			candidateidx = 0
			if candidate.shape[0] > 0: 
				## if there are multiple qualified candidate use the highest y which is the 0 elem cuz we sort flist
		#		 while candidateidx < candidate.shape[0]:
		#		 while candidateidx < 1:
					# if candidate dropping track intersect with other component delete it 
				intersect = False
				for j in range(i+1, candidate[candidateidx]):
					ft2 = flist[j]
					if twoline_intersect((ft.right_x + JUMP_WIDTH//2, ft.right_y - JUMP_HEIGHT), 
										 (ft.right_x + x_shift_by_forward_jump(np.array([leftp_arr[candidate[candidateidx], 1] - ft.right_y])), flist[candidate[candidateidx]].left_y),
										 ft2.get_left_point(), ft2.get_right_point()
										):
						intersect = True
		#				 print(f"intersect on rj, {candidateidx}, {candidate[candidateidx]}, {flist.index(ft)}, {j}")
				if not intersect:
					forward_jump_edge.append(ForwardJumpArea(ft, flist[candidate[0]], "right"))
		#			 break
				candidateidx += 1
		#	 if candidate.shape[0] > 0: 
		#		 ## if there are some qualified candidate use the highest y which is the 0 elem cuz we sort flist
		#		 forward_jump_edge.append(ForwardJumpArea(ft, flist[candidate[0]], "right"))
			

	def generate_direct_jump_edge(self, edge_dict):
		## include equal here cuz forward don;t include it.
		## if there are multiple valid candidate for direct jump only select that in the upper ground
		flist = sorted(self.flist, key = lambda ft: ft.lower_y, reverse=True)
		floor_lower_y = np.array([ft.lower_y for ft in flist])
		floor_upper_y = np.array([ft.lower_y for ft in flist])
		direct_jump_edge = []
		edge_dict["direct_jump_edge"] = (direct_jump_edge)
		for i, ft in enumerate(flist):
			diff = floor_lower_y - ft.upper_y
			candidate = np.where(np.logical_and(diff <= 0, diff >= -JUMP_HEIGHT))[0] 
			# search for area which got lower y smaller than ur upper_y + jump hieght and higher than u
			# also area beneath (upper y lower than ur lower y) should be excluded)
			candidate = candidate[np.argsort(floor_lower_y[candidate])] # get sorted candidate. smaller y first higher first
			for idx in candidate:
				intersect = False
				if idx == i:
					continue
				if flist[idx].left_x <= ft.left_x and ft.right_x <= flist[idx].right_x:
					# check straight first
					if ft.left_y - JUMP_HEIGHT <= flist[idx].y_at_location_x(ft.left_x) and ft.right_y - JUMP_HEIGHT <= flist[idx].y_at_location_x(ft.right_x):
						# straight jump if two end point can reach higher ground.
						direct_jump_edge.append(DirectJumpArea(ft, flist[idx], "straight"))
						break
				if ft.left_x <= flist[idx].left_x <= ft.right_x:
					if ft.y_at_location_x(flist[idx].left_x) - JUMP_HEIGHT <= flist[idx].left_y:
						x_shift = x_shift_by_forward_jump(np.array([flist[idx].left_y - ft.right_y]))
						if flist[idx].left_x - x_shift < ft.left_x: # jumping at point not in ft is not valid
							if self.debug:
								print("the starting jumpping point exceed start area")
							break
						for c in candidate:
							if twoline_intersect((flist[idx].left_x, flist[idx].left_y),
		#						 (flist[idx].left_x - x_shift, ft.right_y),
												 (flist[idx].left_x - JUMP_WIDTH // 2, flist[idx].left_y - JUMP_HEIGHT),
												 flist[c].get_left_point(), flist[c].get_right_point()
							):  # check if falling curve intersect with other line
								intersect = True
								if self.debug:
									print("right direct jump  intersect")
								break 
						if not intersect:
							direct_jump_edge.append(DirectJumpArea(ft, flist[idx], "right"))
				if ft.left_x <= flist[idx].right_x <= ft.right_x:
					if ft.y_at_location_x(flist[idx].right_x) - JUMP_HEIGHT <= flist[idx].right_y:
						x_shift = x_shift_by_forward_jump(np.array([flist[idx].right_y - ft.left_y]))
						if flist[idx].right_x + x_shift > ft.right_x: # jumping at point not in ft is not valid
							if self.debug:
								print("the starting jumpping point exceed start area")
							break
						for c in candidate:
							if twoline_intersect((flist[idx].right_x, flist[idx].right_y),
		#						 (flist[idx].right_x + x_shift, ft.left_y), # this is for bounding check
												 (flist[idx].right_x + JUMP_WIDTH // 2, flist[idx].right_y - JUMP_HEIGHT),
												 flist[c].get_left_point(), flist[c].get_right_point()
							):
								intersect = True
								if self.debug:
									print("left direct jump intersect")
								break 
						if not intersect:
							direct_jump_edge.append(DirectJumpArea(ft, flist[idx], "left"))
					

	def generate_ladder_edge(self, edge_dict):
		ladder_edge = []
		edge_dict["ladder_edge"] = ladder_edge
		i = 0
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)  ## higher y first.
		for ladder in self.ladderlist:
				x = ladder.x
				is_ladder = ladder.is_ladder
		#		 fig.add_artist(lines.Line2D([x1, y1], [x2, y2]))
				lower_y = ladder.lower_y
				upper_y = ladder.upper_y
				start_area = None
				end_area = None
				for ft in flist:
					if ft.left_x <= x <= ft.right_x:
						if upper_y - ROPE_END_POINT_TOLERANCE <= ft.y_at_location_x(x) <= lower_y:
							if self.debug:
								print(f"end ladder {i} in {flist.index(ft)}")
							end_area = ft
							break
				for ft in flist:
					if ft.left_x <= x <= ft.right_x:
						if lower_y <= ft.y_at_location_x(x) <= lower_y + JUMP_HEIGHT:
							if self.debug:
								print(f"start ladder {i} in {flist.index(ft)}")
							start_area = ft
							break
				if start_area is None or end_area is None:
					print("rope not for connecting")
				else:
					jumpdir = []
					if start_area.left_x <= x - JUMP_ROPE_AWAY_DISTNACE:
						jumpdir.append("left")
					if start_area.right_x >= x + JUMP_ROPE_AWAY_DISTNACE:
						jumpdir.append("right")
					if len(jumpdir) == 0:
						jumpdir = "straight"
					elif len(jumpdir) == 1:
						jumpdir = jumpdir[0]
					else:
						jumpdir = "both"
					ladder_edge.append(LadderArea(start_area, end_area, x, lower_y, upper_y, is_ladder, jumpdir))
				i += 1


	def redundant_edge_remove(self, edge_dict):
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)  ## higher y first.
		lower_jump_edge = edge_dict["lower_jump_edge"]
		falling_edge = edge_dict["falling_edge"]
		fall = []
		lower_jump_edge_arr = np.array([[flist.index(lower_jump.start_area), flist.index(lower_jump.dest_area)] 
										for lower_jump in lower_jump_edge])
		falling_edge_arr = np.array([[flist.index(falling.start_area), flist.index(falling.dest_area)] 
										for falling in falling_edge])
		remove_idx = []

		for i in range(falling_edge_arr.shape[0]):
			if np.sum(np.sum(np.abs(falling_edge_arr[i, :] - lower_jump_edge_arr), axis=1) == 0):
				remove_idx.append(i)
		for i in sorted(remove_idx, reverse=True):
			del edge_dict["falling_edge"][i]


	def generate_connecting_edge(self):
		self.edge_dict = {}
		self.generate_lower_jump_edge(self.edge_dict)
		self.generate_falling_edge(self.edge_dict)
		self.generate_forward_jump_edge(self.edge_dict)
		self.generate_direct_jump_edge(self.edge_dict)
		self.generate_ladder_edge(self.edge_dict)
		if self.debug:
			for key in edge_dict:
				print(key, "get", len(edge_dict[key]), "edges")
		self.redundant_edge_remove(self.edge_dict)
		if self.debug:
			print("after redundant_edge_remove")
			for key in edge_dict:
				print(key, "get", len(edge_dict[key]), "edges")


	def generate_directed_graph(self):
		edge_dict = self.edge_dict
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)  ## higher y first.
		point_in_ft = {}  
		for idx in range(len(flist)):
			point_in_ft[idx] = [] 
			
		minimap_graph = ig.Graph(directed=True)

		for i, lower_jump in enumerate(edge_dict["lower_jump_edge"]):
			for point in lower_jump.jump_seg_list:
				start_y = lower_jump.start_area.y_at_location_x(point[0])
				dest_y = lower_jump.dest_area.y_at_location_x(point[0])
				point_in_ft[flist.index(lower_jump.start_area)].append((point[0], start_y))
				point_in_ft[flist.index(lower_jump.dest_area)].append((point[0], dest_y))
				minimap_graph.add_vertices([str((point[0], start_y)), str((point[0], dest_y))])
				minimap_graph.add_edge(str((point[0], start_y)), str((point[0], dest_y)), 
									   weight=LOWER_JUMP_COST+dest_y-start_y, name=f"lower_jump_edge,{i}")
				start_y = lower_jump.start_area.y_at_location_x(point[1])
				dest_y = lower_jump.dest_area.y_at_location_x(point[1])
				point_in_ft[flist.index(lower_jump.start_area)].append((point[1], start_y))
				point_in_ft[flist.index(lower_jump.dest_area)].append((point[1], dest_y))
				minimap_graph.add_vertices([str((point[1], start_y)), str((point[1], dest_y))])
				minimap_graph.add_edge(str((point[1], start_y)), str((point[1], dest_y)),
									  weight=LOWER_JUMP_COST+dest_y-start_y, name=f"lower_jump_edge,{i}")
				

		for i, falling in enumerate(edge_dict["falling_edge"]):
			if falling.falling_dir == "left":
				start_y = falling.start_area.left_y
				dest_y = falling.dest_area.y_at_location_x(falling.start_area.left_x)
				point_in_ft[flist.index(falling.start_area)].append((falling.start_area.left_x, start_y))
				point_in_ft[flist.index(falling.dest_area)].append((falling.start_area.left_x, dest_y))
				minimap_graph.add_vertices([str((falling.start_area.left_x, start_y)), str((falling.start_area.left_x, dest_y))])
				minimap_graph.add_edge(str((falling.start_area.left_x, start_y)), str((falling.start_area.left_x, dest_y)),
									  weight=FALLING_COST+dest_y-start_y, name=f"falling_edge,{i}")
			else:
				start_y = falling.start_area.right_y
				dest_y = falling.dest_area.y_at_location_x(falling.start_area.right_x)
				point_in_ft[flist.index(falling.start_area)].append((falling.start_area.right_x, start_y))
				point_in_ft[flist.index(falling.dest_area)].append((falling.start_area.right_x, dest_y))
				minimap_graph.add_vertices([str((falling.start_area.right_x, start_y)), str((falling.start_area.right_x, dest_y))])
				minimap_graph.add_edge(str((falling.start_area.right_x, start_y)), str((falling.start_area.right_x, dest_y)),
									  weight=FALLING_COST+dest_y-start_y, name=f"falling_edge,{i}")
				

		
		for i, forward_jump in enumerate(edge_dict["forward_jump_edge"]):
			if forward_jump.jump_dir == "left":
				start_y = forward_jump.start_area.left_y
				x_shift = round(x_shift_by_forward_jump(np.array([forward_jump.dest_area.right_y - start_y]))[0])
				dest_x = max(forward_jump.start_area.left_x - x_shift, forward_jump.dest_area.left_x)
				dest_y = forward_jump.dest_area.y_at_location_x(dest_x)
				point_in_ft[flist.index(forward_jump.start_area)].append((forward_jump.start_area.left_x, start_y))
				point_in_ft[flist.index(forward_jump.dest_area)].append((dest_x, dest_y))
				minimap_graph.add_vertices([str((forward_jump.start_area.left_x, start_y)), 
											str((dest_x, dest_y))])
				minimap_graph.add_edge(str((forward_jump.start_area.left_x, start_y)), str((dest_x, dest_y)),
									  weight=FORWARD_JUMP_COST+x_shift, name=f"forward_jump_edge,{i}")
			else:
				start_y = forward_jump.start_area.right_y
				x_shift = round(x_shift_by_forward_jump(np.array([forward_jump.dest_area.left_y - start_y]))[0])
				dest_x = min(forward_jump.start_area.right_x + x_shift, forward_jump.dest_area.right_x)
				dest_y = forward_jump.dest_area.y_at_location_x(dest_x)
				point_in_ft[flist.index(forward_jump.start_area)].append((forward_jump.start_area.right_x, start_y))
				point_in_ft[flist.index(forward_jump.dest_area)].append((dest_x, dest_y))  
				minimap_graph.add_vertices([str((forward_jump.start_area.right_x, start_y)), 
											str((dest_x, dest_y))])
				minimap_graph.add_edge(str((forward_jump.start_area.right_x, start_y)), str((dest_x, dest_y)),
									  weight=FORWARD_JUMP_COST+x_shift, name=f"forward_jump_edge,{i}")
				


		for i, direct_jump in enumerate(edge_dict["direct_jump_edge"]):
			if direct_jump.jump_dir == "straight":
				start_y = direct_jump.start_area.left_y
				dest_y = direct_jump.dest_area.y_at_location_x(direct_jump.start_area.left_x)
				point_in_ft[flist.index(direct_jump.start_area)].append((direct_jump.start_area.left_x, start_y))
				point_in_ft[flist.index(direct_jump.dest_area)].append((direct_jump.start_area.left_x, dest_y))
				minimap_graph.add_vertices([str((direct_jump.start_area.left_x, start_y)), 
											str((direct_jump.start_area.left_x, dest_y))])
				minimap_graph.add_edge(str((direct_jump.start_area.left_x, start_y)), str((direct_jump.start_area.left_x, dest_y)),
									  weight=DIRECT_JUMP_COST + JUMP_HEIGHT - (start_y - dest_y) // 2, name=f"direct_jump_edge,{i}") 
				# if start is below jump height we need half of the time of one jump if it's equal then full 
				start_y = direct_jump.start_area.right_y
				dest_y = direct_jump.dest_area.y_at_location_x(direct_jump.start_area.right_x)
				point_in_ft[flist.index(direct_jump.start_area)].append((direct_jump.start_area.right_x, start_y))
				point_in_ft[flist.index(direct_jump.dest_area)].append((direct_jump.start_area.right_x, dest_y))
				minimap_graph.add_vertices([str((direct_jump.start_area.right_x, start_y)), 
											str((direct_jump.start_area.right_x, dest_y))])
				minimap_graph.add_edge(str((direct_jump.start_area.right_x, start_y)), str((direct_jump.start_area.right_x, dest_y)),
									  weight=DIRECT_JUMP_COST + JUMP_HEIGHT - (start_y - dest_y) // 2, name=f"direct_jump_edge,{i}")
			elif direct_jump.jump_dir == "left":
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.right_x)
				dest_y = direct_jump.dest_area.right_y
				x_shift = round(x_shift_by_forward_jump(np.array([dest_y - start_y]))[0])
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.right_x + x_shift)
				point_in_ft[flist.index(direct_jump.start_area)].append((direct_jump.dest_area.right_x + x_shift, start_y))
				point_in_ft[flist.index(direct_jump.dest_area)].append((direct_jump.dest_area.right_x, dest_y))
				minimap_graph.add_vertices([str((direct_jump.dest_area.right_x + x_shift, start_y)), 
											str((direct_jump.dest_area.right_x, dest_y))])
				minimap_graph.add_edge(str((direct_jump.dest_area.right_x + x_shift, start_y)), str((direct_jump.dest_area.right_x, dest_y)),
									  weight=DIRECT_JUMP_COST+x_shift, name=f"direct_jump_edge,{i}")
			elif direct_jump.jump_dir == "right":
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.left_x)
				dest_y = direct_jump.dest_area.left_y
				x_shift = round(x_shift_by_forward_jump(np.array([dest_y - start_y]))[0])
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.left_x - x_shift)
				point_in_ft[flist.index(direct_jump.start_area)].append((direct_jump.dest_area.left_x - x_shift, start_y))
				point_in_ft[flist.index(direct_jump.dest_area)].append((direct_jump.dest_area.left_x, dest_y)) 
				minimap_graph.add_vertices([str((direct_jump.dest_area.left_x - x_shift, start_y)), 
											str((direct_jump.dest_area.left_x, dest_y))])
				minimap_graph.add_edge(str((direct_jump.dest_area.left_x - x_shift, start_y)), str((direct_jump.dest_area.left_x, dest_y)),
									  weight=DIRECT_JUMP_COST+x_shift, name=f"direct_jump_edge,{i}")

		for i, ladder in enumerate(edge_dict["ladder_edge"]):
			start_y = ladder.start_area.y_at_location_x(ladder.x)
			dest_y = ladder.dest_area.y_at_location_x(ladder.x)
			point_in_ft[flist.index(ladder.start_area)].append((ladder.x, start_y))
			point_in_ft[flist.index(ladder.dest_area)].append((ladder.x, dest_y))
			minimap_graph.add_vertices([str((ladder.x, start_y)), 
										str((ladder.x, dest_y))])
			minimap_graph.add_edge(str((ladder.x, start_y)), str((ladder.x, dest_y)),
								  weight=LADDER_COST+start_y-dest_y, name=f"ladder_edge,{i}")

		### map the vertice with the same name to the same group.
		name_map = dict(zip(np.unique(np.array(minimap_graph.vs["name"])), 
							range(np.unique(np.array(minimap_graph.vs["name"])).shape[0])))

		minimap_graph.contract_vertices([name_map[vname] for vname in minimap_graph.vs["name"]], combine_attrs="first")


		## add connectivity inside ft
		for key in point_in_ft:
			point_in_ft[key] = list(pd.DataFrame(point_in_ft[key]).drop_duplicates().sort_values(by=0).itertuples(index=False, name=None))
			# sort inner ft point by its x value at ascending order while removing redundant element
		vsnum = 0
		for key in point_in_ft:
			vsnum+=len(point_in_ft[key])

		point_in_ft_x = {}
		for key in point_in_ft:
			point_in_ft_x[key] = np.array([p[0] for p in point_in_ft[key]])

		assert vsnum == len(minimap_graph.vs)  ## vsnum at point in ft should be the same as minimap graph

		for key in point_in_ft:
			a, b = tee(point_in_ft[key])
			next(b, None)
			for lp, rp in zip(a, b):
				# we can move back and forth
				minimap_graph.add_edge(str(lp), str(rp), weight=rp[0] - lp[0], name="horizontal_move,-1")
				minimap_graph.add_edge(str(rp), str(lp), weight=rp[0] - lp[0], name="horizontal_move,-1")

		self.minimap_graph = minimap_graph
		self.point_in_ft = point_in_ft
		self.point_in_ft_x = point_in_ft_x


	def generate_all_mapinfo(self):
		self.generate_map()
		self.generate_connecting_edge()
		self.generate_directed_graph()


	def generate_all_mob_address(self):
		self.life_property_lock.acquire()
		first_start_add = self.game_process.get_pointer_by_address_list(self.MOB_LINK_LIST_ADDRESS_LIST1)
		first_set = self.game_process.get_address_of_linked_list(first_start_add, 0x4, 0x8)
		second_start_add = self.game_process.get_pointer_by_address_list(self.MOB_LINK_LIST_ADDRESS_LIST2)
		second_set = self.game_process.get_address_of_linked_list(second_start_add, 0x4, 0x8)
		self.mob_add_list = list(first_set.union(second_set))
		self.life_property_lock.release()


	def generate_all_mob_coor(self):
		self.generate_all_mob_address()
		self.life_property_lock.acquire()
		self.all_mob_coor = []
		# self.all_mob_isalive = []

		for mob_add in self.mob_add_list:
			mob_x = self.game_process.read_signed_value_by_address_list(list(chain([mob_add + self.MOB_X_OFFSET[0]], self.MOB_X_OFFSET[1:])))
			mob_y = self.game_process.read_signed_value_by_address_list(list(chain([mob_add + self.MOB_Y_OFFSET[0]], self.MOB_Y_OFFSET[1:])))
			# is_alive = (self.game_process.read_signed_value_by_address_list([mob_add + 0x4]) == 0x8f8f)  ## check the deadth 
			self.all_mob_coor.append((mob_x, mob_y))
			if self.debug:
				print(f"mob coor is {mob_x}, {mob_y},")
		self.mob_count = self.game_process.read_signed_value_by_address_list(self.MOB_COUNT_LIST)
		self.life_property_lock.release()


	def generate_character_coor(self):
		self.life_property_lock.acquire()
		chara_x = self.game_process.read_signed_value_by_address_list(self.MINIMAP_X_ADDRESS_LIST)
		chara_y = self.game_process.read_signed_value_by_address_list(self.MINIMAP_Y_ADDRESS_LIST)
		self.character_coor = (chara_x, chara_y)
		self.life_property_lock.release()


	def generate_character_true_coor(self):
		self.life_property_lock.acquire()
		chara_x = self.game_process.read_signed_value_by_address_list(self.X_ADDRESS_LIST)
		chara_y = self.game_process.read_signed_value_by_address_list(self.Y_ADDRESS_LIST)
		self.character_true_coor = (chara_x, chara_y)
		self.life_property_lock.release()


	def generate_life_coor(self):
		self.generate_all_mob_coor()
		self.generate_character_coor()


	def path_finding(self, chara_x, chara_y, mob_x, mob_y):
		flist = sorted(self.flist, key = lambda ft: ft.lower_y)  ## higher y first.
		point_in_ft = self.point_in_ft
		point_in_ft_x = self.point_in_ft_x
		minimap_graph = self.minimap_graph  # rename


		lower_y_arr = np.array([ft.lower_y for ft in flist])
		left_x_arr = np.array([ft.left_x for ft in flist])
		right_x_arr = np.array([ft.right_x for ft in flist])
		candidate = np.where(np.logical_and(left_x_arr <= mob_x, mob_x <= right_x_arr))[0]
		candidate = candidate[np.argsort(np.abs(lower_y_arr[candidate] - mob_y))] # sort candidate by lower_y gap
		mob_ft_idx = None
		for idx in candidate:
			if flist[idx].point_in_ft((mob_x, mob_y)):
				mob_ft_idx = idx
				break

		if mob_ft_id is None:
			if self.debug:
				print("no suitable mob_ft_id found")
			minimum_dist = np.inf
			for i, point_list in enumerate(point_in_ft):
				if len(point_list) > 0:
					dist = np.sum(np.abs(np.array(point_list) - np.array((mob_x, mob_y))), axis=1)
					if np.min(dist) < minimum_dist:
						minimum_dist = np.min(dist)
						mob_ft_idx = i


		candidate = np.where(np.logical_and(left_x_arr <= chara_x, chara_x <= right_x_arr))[0]
		candidate = candidate[np.argsort(np.abs(lower_y_arr[candidate] - chara_y))] # sort candidate by lower_y gap
		chara_ft_idx = None
		for idx in candidate:
			if flist[idx].point_in_ft((chara_x, chara_y)):
				chara_ft_idx = idx
				break

		if chara_ft_idx is None:
			if self.debug:
				print("No suitable chara_ft_idx found")
			minimum_dist = np.inf
			for i, point_list in enumerate(point_in_ft):
				if len(point_list) > 0:
					dist = np.sum(np.abs(np.array(point_list) - np.array((chara_x, chara_y))), axis=1)
					if np.min(dist) < minimum_dist:
						minimum_dist = np.min(dist)
						chara_ft_idx = i

		start_vertice_idx = np.argmin(np.abs(point_in_ft_x[chara_ft_idx] - chara_x))
		dest_vertice_idx = np.argmin(np.abs(point_in_ft_x[mob_ft_idx] - mob_x))
		path = minimap_graph.get_shortest_paths(str(point_in_ft[chara_ft_idx][start_vertice_idx]), 
												str(point_in_ft[mob_ft_idx][dest_vertice_idx]),
												weights=minimap_graph.es["weight"])
		path_point_list = [ast.literal_eval(minimap_graph.vs[p]["name"]) for p in path[0]]

		traverse_edge = []
		for nodeidx in range(1, len(path[0])):
			former_nodeidx = nodeidx - 1
			edgename = minimap_graph.es[minimap_graph.get_eid(path[0][former_nodeidx], path[0][nodeidx])]["name"]
			edgename = str.split(edgename, ",")
			edgename[1] = int(edgename[1])
			traverse_edge.append(edgename)

		ft_changing_edgeidx = []
		for i, edge in enumerate(traverse_edge):
			if edge[0] != 'horizontal_move':
				ft_changing_edgeidx.append(i)

		if self.debug:
			for edgeidx in ft_changing_edgeidx:
				print(f"moving to {minimap_graph.vs[path[0][edgeidx]]['name']}")
				print(f"changing ft via {traverse_edge[edgeidx]}")

		self.path = path
		self.traverse_edge = traverse_edge
		self.ft_changing_edgeidx = ft_changing_edgeidx

		# return path, traverse_edge, ft_changing_edge











	















