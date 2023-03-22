import pyautogui, ctypes, pydirectinput
from time import sleep, time
from pynput import keyboard
import numpy as np
from Character import *
from Map import *

class Attacker(Character):
	"""docstring for Attacker"""

	STOP_ATTACK_TIME = 0.1 # stop attack to clear debuff or something
	AREA_CHECK_WAITING_INTERVAL = 0.3
	MAX_CONNECTION_TIME = 5 # we can only be in connecting area in 20s or we are in some error, implemented later

	CLOSE_TO_ROPE_DINSTANCE = 90 # change it to this? cuz spd is 140 all the times

	TELEPORT_DISTANCE = 150

	attacking_direction = None
	boss_address_old = None
	exp_old = None
	exp_bigchange_threshold = 5 * (10 ** 5) # stage change of a boss if exp diff greater than 0.5 m
	stage_change = False
	
	def __init__(self, jump_key, attack_key, buff_key, buff_interval, pet_potion_key, att_potion_key, att_potion_interval, hp_potion, acp_potion, enable_relocate=False, relocate_fail_method=None, mage_teleport_key=None, sair_boat_key=None, is_bm=False):
		super(Attacker, self).__init__(jump_key, attack_key, buff_key, buff_interval, pet_potion_key)
		self.att_potion_key = att_potion_key
		self.att_potion_interval = att_potion_interval
		self.hp_potion = hp_potion
		self.acp_potion = acp_potion
		self.boss_x = None
		self.mage_teleport_key = mage_teleport_key
		self.sair_boat_key = sair_boat_key
		self.is_bm = is_bm
		self.buff_timer = time()
		self.att_potion_timer = time() 

		self.enable_relocate = enable_relocate
		self.relocate_fail_method = relocate_fail_method
		if self.enable_relocate and self.relocate_fail_method is None:
			raise Exception("relocate_fail_method should be specified")

		self.detect_exp_bigchange_thread = threading.Thread(target=self.detect_exp_bigchange, args=())
		# detect_exp_bigchange_thread.start()
		self.detect_single_boss_change = threading.Thread(target=self.detect_single_boss_stage_change, args=())
		# detect_single_boss_change.start()
		self.debuff_dispel_thread = threading.Thread(target=self.debuff_dispel, args=())

		self.mobcount_thread = threading.Thread(target=self.detect_mobcount_change, args=())
		self.sair_boat_check_thread = threading.Thread(target=self.sair_boat_check, args=())
		super(Attacker, self).start() # start pet 
		if self.sair_boat_key is not None:
			self.sair_boat_check_thread.start()

	def inititalize_pointer(self):
		super(Attacker, self).inititalize_pointer()
		self.attack_count_ptr = process.get_pointer(self.ATTACK_COUNT_ADDRESS_LIST[0], self.ATTACK_COUNT_ADDRESS_LIST[1:])
		self.debuff_count_ptr = process.get_pointer(self.DEBUFF_COUNT_ADDRESS_LIST[0], self.DEBUFF_COUNT_ADDRESS_LIST[1:])
		self.attack_count_ptr = process.get_pointer(self.ATTACK_COUNT_ADDRESS_LIST[0], self.ATTACK_COUNT_ADDRESS_LIST[1:])
		self.x_true_ptr = process.get_pointer(self.X_ADDRESS_LIST[0], self.X_ADDRESS_LIST[1:])
		self.y_true_ptr = process.get_pointer(self.Y_ADDRESS_LIST[0], self.Y_ADDRESS_LIST[1:])
	
	def detect_exp_bigchange(self):
		print("no longer support exp detect.")
		return 0
		while self.exp_old is None:
			if self.EXP is not None:
				self.property_lock.acquire()
				self.exp_old = self.EXP
				self.property_lock.release()
				print("initialize_exp done, exp is ", self.exp_old)
			sleep(10)
		while not self.stopped:
			if abs(self.exp_old - self.EXP) >= self.exp_bigchange_threshold:
				print("stage change in boss, big diff is ", abs(self.exp_old - self.EXP))
				self.property_lock.acquire()
				self.stage_change = True
				self.exp_old = self.EXP
				self.property_lock.release()
			sleep(1)

	def detect_mobcount_change(self):
		mobcount_ptr = process.get_pointer(self.MOB_COUNT_LIST[0], self.MOB_COUNT_LIST[1:])
		mobcount = self.get_pointer_singed_value(process, mobcount_ptr)
		print("detect_mobcount_change initial mob count is ", mobcount)
		old_mobcount = mobcount
		while not self.stopped:
			if old_mobcount != mobcount:
				print("new mobcount is ", mobcount)
				old_mobcount = mobcount
			mobcount = self.get_pointer_singed_value(process, mobcount_ptr)
			sleep(1)

	def debuff_dispel(self):
		while not self.stopped:
			if self.get_pointer_singed_value(process, self.debuff_count_ptr) >= 1:
				print("get debuff dispel it by acp")
				self.movement_lock.acquire()
				pydirectinput.keyUp(self.attack_key, _pause=False)
				sleep(self.STOP_ATTACK_TIME)
				pydirectinput.press(self.acp_potion, _pause=False)
				pydirectinput.press(self.hp_potion, _pause=False)
				self.movement_lock.release()
			sleep(2)

	def sair_boat_check(self):
		old_buff_count = self.get_pointer_singed_value(process, self.buff_count_ptr)
		while not self.stopped:
			self.movement_lock.acquire()
			if self.get_pointer_singed_value(process, self.buff_count_ptr) < old_buff_count:
				print("boat boom")
				pydirectinput.keyUp(self.attack_key, _pause=False)
				sleep(0.5)
				old_buff_count = self.get_pointer_singed_value(process, self.buff_count_ptr)
				pydirectinput.press(self.sair_boat_key, _pause=False)
				sleep(1)
				if self.get_pointer_singed_value(process, self.buff_count_ptr) == old_buff_count:
					# boat in cd
					print("boat in cd")
					sleep(10) # cd of boat
					pydirectinput.keyUp(self.attack_key, _pause=False)
					sleep(0.5)
					pydirectinput.press(self.sair_boat_key, _pause=False)
				elif self.get_pointer_singed_value(process, self.buff_count_ptr) > old_buff_count:
					# boating completed
					print("boat complete")
					pass
				else:
					# some buff expire not boat
					print("some buff expire but not boat")
					pydirectinput.press(self.sair_boat_key, _pause=False)
				old_buff_count = self.get_pointer_singed_value(process, self.buff_count_ptr)
			elif self.get_pointer_singed_value(process, self.buff_count_ptr) > old_buff_count:
				print("some buff addded")
				old_buff_count = self.get_pointer_singed_value(process, self.buff_count_ptr)
			self.movement_lock.release()
			sleep(1)


	def detect_single_boss_stage_change(self):
		while self.boss_address_old is None:
			boss_address = self.get_pointer_singed_value(process, process.get_pointer(self.MOB_X_LIST[0], self.MOB_X_LIST[1:2]))
			if boss_address != 0:
				self.property_lock.acquire()
				self.boss_address_old = boss_address
				self.property_lock.release()
				print("initialize boss add done, boss address is ", hex(self.boss_address_old))
			sleep(10)
		while not self.stopped:
			boss_address = self.get_pointer_singed_value(process, process.get_pointer(self.MOB_X_LIST[0], self.MOB_X_LIST[1:2]))
			if self.boss_address_old != boss_address:
				print("stage change in boss address, new add is", hex(boss_address))
				self.property_lock.acquire()
				self.stage_change = True
				self.boss_address_old = boss_address
				self.property_lock.release()
			sleep(1)

	def update(self):
		"""
		update character stats
		"""
		super(Attacker, self).update()
		self.attack_count = self.get_pointer_singed_value(process, self.attack_count_ptr)
		self.x_true = self.get_pointer_singed_value(process, self.x_true_ptr)  # use for toad or nebergan.
		self.y_true = self.get_pointer_singed_value(process, self.y_true_ptr)  # use for toad or nebergan.

	def update_boss_x(self, x):
		self.property_lock.acquire()
		self.boss_x = x
		self.property_lock.release()

	def on_press(self, key):
		# overwrite the parant method, for none fast tc case
		super(Attacker, self).on_press(key) # deal with exit action
		if self.f10_press_count == 1:
			if key == keyboard.Key.right:
				print("right attacking direction determined")
				self.property_lock.acquire()
				self.attacking_direction = "right"
				self.f10_press_count = 0
				self.property_lock.release()
			elif key == keyboard.Key.left:
				print("left attacking direction determined")
				self.property_lock.acquire()
				self.attacking_direction = "left"
				self.f10_press_count = 0
				self.property_lock.release()
			else:
				print("unknown attacking direction")
		if key == keyboard.Key.tab:
			self.tab_press_count += 1
			self.tab_press_count = self.tab_press_count % 2
			if self.tab_press_count == 1:
				self.movement_lock.acquire()
				pydirectinput.keyUp(self.attack_key, _pause=False)
				print("pause the script")
			else:
				self.movement_lock.release()
				print("resume the script")
		elif key == keyboard.Key.f10:
			if self.boss_x is None:  # only determine direction by hand when boss_x not specified
				if self.f10_press_count == 0:
					self.property_lock.acquire()
					self.f10_press_count += 1
					self.property_lock.release()
					print("determine the attack direction")
		elif key == keyboard.Key.f7:
			print("stage changet test")
			self.property_lock.acquire()
			self.stage_change = True	
			self.property_lock.release()

	def attack_horizontal(self, x_min, x_max):
		self.attack()
		self.update()
		if self.x >= x_max:
			if not self.is_bm:
				pydirectinput.keyUp(self.attack_key, _pause=False)
			if self.mage_teleport_key is not None:
				# if abs(self.x - x_max) >= self.TELEPORT_DISTANCE:
				while self.x - x_min > self.TELEPORT_DISTANCE:
					# print("left tele")
					pydirectinput.keyDown("left", _pause=False)
					# sleep(self.KEY_DELAY)
					pydirectinput.keyDown(self.mage_teleport_key, _pause=False)
					pydirectinput.keyUp(self.mage_teleport_key, _pause=False)
					# pydirectinput.press(self.mage_teleport_key, _pause=False)
					# sleep(self.KEY_DELAY)
					sleep(self.KEY_DELAY)
					self.update()
				pydirectinput.keyUp("left", _pause=False)
				self.horizonal_move(x_min, self.TELEPORT_DISTANCE)
			else:
				self.horizonal_move(x_min, self.TOUCH_MOVE_DISTANCE)  # 30 may sometimes cause error. 40 or 45 is tested by se with 140 movespeed. can be less if speed is less, 
			# 45 is just as good to move near 10 to the dest, cuz some delay, 40 is the minimum tolerance of 140
		if self.x <= x_min:
			if not self.is_bm:
				pydirectinput.keyUp(self.attack_key, _pause=False)
			if self.mage_teleport_key is not None:
				# if abs(self.x - x_min) >= self.TELEPORT_DISTANCE:
				while x_max - self.x > self.TELEPORT_DISTANCE:
					# print("right tele")
					pydirectinput.keyDown("right", _pause=False)
					# sleep(self.KEY_DELAY)
					# pydirectinput.press(self.mage_teleport_key, _pause=False)
					pydirectinput.keyDown(self.mage_teleport_key, _pause=False)
					pydirectinput.keyUp(self.mage_teleport_key, _pause=False)
					# sleep(self.KEY_DELAY)
					sleep(self.KEY_DELAY)
					self.update()
				pydirectinput.keyUp("right", _pause=False)
				self.horizonal_move(x_max, self.TELEPORT_DISTANCE)
			else:
				self.horizonal_move(x_max, self.TOUCH_MOVE_DISTANCE)  # 30 may sometimes cause error. 40 or 45 is tested by se with 140 movespeed. can be less if speed is less, 
			# 45 is just as good to move near 10 to the dest, cuz some delay, 40 is the minimum tolerance of 140

	def horizonal_move(self, destination_x, tolerance):
		# move nearby the destination and face to the boss
		# 移动到x 正负 tolerance之间的位置, 因为程序执行会有延迟 很难到达真正的x, 所以到达大概的位置之后进行后续操作.	
		self.movement_lock.acquire()
		print("horizonal_move now")
		if self.get_pointer_singed_value(process, self.x_ptr) > destination_x:
			self.direction = "left"
		else:
			self.direction = "right"
		self.update()
		while abs(self.x - destination_x) > tolerance:
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(self.KEY_DELAY)
			self.update()
			if self.x > destination_x and self.direction == "right":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "left"
			elif self.x <= destination_x and self.direction == "left":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "right"
		pydirectinput.keyUp(self.direction, _pause=False)
		self.face_to_boss()
		self.movement_lock.release()

	def horizonal_move_by_true_x(self, destination_x, tolerance):
		# move nearby the destination and face to boss
		# 移动到x 正负 tolerance之间的位置, 因为程序执行会有延迟 很难到达真正的x, 所以到达大概的位置之后进行后续操作.
		self.movement_lock.acquire()
		print("horizonal_move by true x now")
		if self.get_pointer_singed_value(process, self.x_true_ptr) > destination_x:
			self.direction = "left"
		else:
			self.direction = "right"
		self.update()
		while abs(self.x_true - destination_x) > tolerance:
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(0.01)
			self.update()
			if self.x_true > destination_x and self.direction == "right":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "left"
			elif self.x_true <= destination_x and self.direction == "left":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "right"
		pydirectinput.keyUp(self.direction, _pause=False)
		if self.boss_x is not None:
			self.attacking_direction = self.DIRECTION_SET[int((np.sign(self.boss_x - self.x_true) + 1)/ 2)]  # determine the attacking direction
		if self.attacking_direction is not None: 
			pydirectinput.keyDown(self.attacking_direction, _pause=False)
			sleep(self.KEY_DELAY * 3)
			pydirectinput.keyUp(self.attacking_direction, _pause=False)  # let the character face to the direction
		self.movement_lock.release()

	def jump_to_low_standing_area(self, low_standing_area):
		# jump to the lower floor
		# 下跳到下一层
		print("jump to the low_standing_area")
		self.movement_lock.acquire()
		self.update()
		while self.y <= low_standing_area.centroid_y:
			if low_standing_area.in_check(self.x, self.y):
				break
			pydirectinput.keyDown("down", _pause=False)
			sleep(self.KEY_DELAY * 2)
			pydirectinput.press(self.jump_key , _pause=False)
			pydirectinput.keyUp("down", _pause=False)
			sleep(1) # wait for lower jump to reach the land
			self.update()
		print("jump done")
		self.movement_lock.release()

	def attack_horizontal_by_true_x(self, x_min, x_max):
		# true x is less sensitive when u move, so perfer x rather than true x
		# and thus the tolerance of horizonal_move should be larger.
		self.update()
		if self.x_true >= x_max:
			pydirectinput.keyUp(self.attack_key, _pause=False)
			self.horizonal_move_by_true_x(x_min, self.TOUCH_MOVE_DISTANCE)
		if self.x_true <= x_min:
			pydirectinput.keyUp(self.attack_key, _pause=False)
			self.horizonal_move_by_true_x(x_max, self.TOUCH_MOVE_DISTANCE) 
		#print("before att")
		self.attack()

	def face_to_boss(self):
		# use x to face to boss
		if self.boss_x is not None:
			self.attacking_direction = self.DIRECTION_SET[int((np.sign(self.boss_x - self.x) + 1)/ 2)]  # determine the attacking direction
		if self.attacking_direction is not None: 
			pydirectinput.keyDown(self.attacking_direction, _pause=False)
			sleep(self.KEY_DELAY * 3)
			pydirectinput.keyUp(self.attacking_direction, _pause=False)  # let the character face to the direction

	def attack(self):
		self.movement_lock.acquire()
		# print("attack now")
		pydirectinput.keyDown(self.attack_key, _pause=False)
		sleep(self.KEY_DELAY)
		self.movement_lock.release()


	def attack_in_area(self, standing_area, debug=False):
		"""
		define the attack action of standing_area. 
		check mapid only in attack in area 
		"""
		assert isinstance(standing_area, StandingArea)
		if isinstance(standing_area, FlatPlatform) or isinstance(standing_area, Slope):
			if debug:
				print("attacking in {}".format(standing_area))
			start_time = time()
			while time() - start_time <= standing_area.attack_time:
				if self.stopped:
					break
				self.update()
				if self.enable_relocate:
					# if enable relocate we should locate character's postion
					if not standing_area.in_check(self.x, self.y):
						pydirectinput.keyUp(self.attack_key, _pause=False)
						print("area check error")
						break
				if time() - self.buff_timer >= self.buff_interval or self.get_pointer_singed_value(process, self.buff_count_ptr) < 3:
					# we will get at least 3 buff, if less than 3 we got dp
					# add buff when in attack in area, attack first to make character buff in the right range
					pydirectinput.keyUp(self.attack_key, _pause=False)
					# give buff with character r in the right edge of attack area
					self.horizonal_move(standing_area.attack_area_right_x, self.TOUCH_MOVE_DISTANCE)
					pydirectinput.press(self.buff_key, _pause=False)
					sleep(self.BUFF_SPELL_TIME * 2)
					pydirectinput.press(self.hp_potion, _pause=False)
					self.property_lock.acquire()
					self.buff_timer = time()
					self.property_lock.release()
					print("buff done")
				if time() - self.att_potion_timer >= self.att_potion_interval:
					# att potion add
					print("add att potion")
					pydirectinput.keyUp(self.attack_key, _pause=False)
					pydirectinput.press(self.att_potion_key, _pause=False)
					pydirectinput.press(self.hp_potion, _pause=False)
					self.property_lock.acquire()
					self.att_potion_timer = time()
					self.property_lock.release()
				if self.stage_change:
					pydirectinput.keyUp(self.attack_key, _pause=False)
					print("stage change done")
					if not self.enable_relocate:
						self.property_lock.acquire()
						self.stage_change = False
						self.property_lock.release()
					break
				self.attack_horizontal(standing_area.attack_area_left_x, standing_area.attack_area_right_x)
		else:
			raise Exception("undefined standing_area action")

	def transport(self, connecting_area, debug=False):
		"""
		define the action of connecting_area. 
		"""
		assert isinstance(connecting_area, ConnectingArea)
		if debug:
			print("transporting in {}".format(connecting_area))
		if isinstance(connecting_area, Rope):
			self.update()
			if abs(self.x - connecting_area.rope_x) <= self.CLOSE_TO_ROPE_DINSTANCE:
				self.horizonal_move(connecting_area.rope_x, self.JUMP_ROPE_CLIMB_DISTANCE)
			self.climb_to_high_floor(*(connecting_area.get_param()))
		elif isinstance(connecting_area, LowerJumpArea):
			self.update()
			while not (connecting_area.left_x <= self.x <= connecting_area.right_x):
				if self.x >= connecting_area.right_x:
					if self.direction == "right":
						pydirectinput.keyUp(self.direction, _pause=False)
					self.direction = "left"
				elif self.x <= connecting_area.left_x:
					if self.direction == "left":
						pydirectinput.keyUp(self.direction, _pause=False)
					self.direction = "right"
				pydirectinput.keyDown(self.direction, _pause=False)
				sleep(self.KEY_DELAY)
				self.update()
			pydirectinput.keyUp(self.direction, _pause=False)
			self.jump_to_low_floor(connecting_area.lower_floor_y)
		elif isinstance(connecting_area, JumpArea):
			self.horizonal_move(connecting_area.jump_x, self.JUMP_ROPE_AWAY_DISTNACE)
			pydirectinput.keyDown(connecting_area.jump_dir, _pause=False)
			sleep(self.KEY_DELAY * 10)  # make ur character move jump to jump further
			pydirectinput.press(self.jump_key, _pause=False)
			pydirectinput.keyUp(connecting_area.jump_dir, _pause=False)
			sleep(self.AREA_CHECK_WAITING_INTERVAL)
			self.update()
			# print("in check (x,y) is {}, {}, nex area cen y is {}".format(self.x, self.y, connecting_area.next_standing_area.centroid_y))
			if not connecting_area.next_standing_area.in_check(self.x, self.y):
				# print("(x,y) is {}, {}, nex area cen y is {}".format(self.x, self.y, connecting_area.next_standing_area.centroid_y))
				if self.y <= connecting_area.next_standing_area.centroid_y:
					self.jump_to_low_standing_area(connecting_area.next_standing_area) # jump when there is some obstacle
				else:
					if connecting_area.jump_dir == "up":
						start_time = time()
						while not connecting_area.next_standing_area.in_check(self.x, self.y):
							print("try rejump to reach the next area")
							pydirectinput.press(self.jump_key, _pause=False)
							sleep(self.AREA_CHECK_WAITING_INTERVAL)
							self.update()
							if time() - start_time >= self.MAX_CONNECTION_TIME:
								break
		else:
			raise Exception("undefined connecting_area action")


	def stage_boss_slay(self, standing_area_list, connecting_area_list, boss_x_list, debug=False):
		assert len(standing_area_list) == len(connecting_area_list) + 1
		for i in range(len(connecting_area_list)):
			assert standing_area_list[i] is connecting_area_list[i].current_standing_area
			assert standing_area_list[i+1] is connecting_area_list[i].next_standing_area
		for i in range(len(connecting_area_list)):
			self.update()
			self.update_boss_x(boss_x_list[i])
			self.face_to_boss()
			self.attack_in_area(standing_area_list[i], debug)
			pydirectinput.keyUp(self.attack_key)
			self.transport(connecting_area_list[i], debug)
		self.update()
		self.update_boss_x(boss_x_list[i + 1])
		self.face_to_boss()
		self.attack_in_area(standing_area_list[i + 1], debug)
		pydirectinput.keyUp(self.attack_key, _pause=False)
		self.stop()
		print("stage boss done")
		
	def manual_stage_boss_slay(self, standing_area_list, boss_x_list, debug=False):
		# specify attacking area and move to area manually.
		print("manual_stage_boss_slay start")
		for i in range(len(standing_area_list)):
			print(" {} th stage boss slay".format(i + 1))
			self.update()
			self.update_boss_x(boss_x_list[i])
			self.horizonal_move(standing_area_list[i].attack_area_right_x, self.TOUCH_MOVE_DISTANCE)
			self.face_to_boss()
			self.attack_in_area(standing_area_list[i], debug)
		pydirectinput.keyUp(self.attack_key, _pause=False)
		self.stop()
		print("stage boss done")
		
	def find_all_paths(self, graph, start, end, path=[], max_length=10):
		# graph is a dict with key the start value is a list of dest
		if len(path) >= max_length:
			return []
		path = path + [start]
		if start == end:
			return [path]
		if start not in graph:
			return []
		paths = []
		for node in graph[start]:
			paths += self.find_all_paths(graph, node, end, path, max_length=max_length)
		return paths


	def come_to_destination_with_relocate(self, connect_graph, standing_area_list, connecting_area_list, character_current_area, destination_area, debug=False):
		paths = self.find_all_paths(connect_graph, character_current_area, destination_area)
		paths.sort(key=len)
		path = paths[0] # choose the shortest path
		if debug:
			print("start relocate to the main list")
			print("path is ", path)
		temp_connect_list = []
		for i in range(len(path) - 1):
			for j in range(len(connecting_area_list)):
				if connecting_area_list[j].current_standing_area is path[i] and connecting_area_list[j].next_standing_area is path[i + 1]:
					temp_connect_list.append(connecting_area_list[j])
					break
		i = 0
		relocate_succeed = False
		while i < len(temp_connect_list):
			self.transport(temp_connect_list[i], debug)
			self.update()
			for j in range(len(path)):
				if path[j].in_check(self.x, self.y):
					i = j
					relocate_succeed = True
					break
			if not relocate_succeed:
				# not all the in the path area
				break
		if not relocate_succeed:
			self.act_after_relocate_fail(standing_area_list[0])
			# all fail do the come to destination again
			self.come_to_destination_with_relocate(connect_graph, standing_area_list, connecting_area_list, standing_area_list[0], destination_area, debug)


	def act_after_relocate_fail(self, default_standing_area):
		if self.relocate_fail_method == "right_move":
			while not default_standing_area.in_check(self.x, self.y):
				# if no match found, move to very first standing_area
				self.movement_lock.acquire()
				pydirectinput.keyDown("right", _pause=False)
				sleep(self.KEY_DELAY * 10) # sleep 0.1 s
				self.movement_lock.release()
				self.update()
			pydirectinput.keyUp("right", _pause=False)
		elif self.relocate_fail_method == "lower_jump":
			self.jump_to_low_floor(default_standing_area.centroid_y)
		else:
			raise Exception("undefined action")

	def half_manual_stage_boss_slay(self, standing_area_list, connecting_area_list, main_loop_list, boss_x_list, debug=False):
		# specify attacking area and move to area manually.
		print("half_manual_stage_boss_slay start")
		connect_graph = dict()
		for i in range(len(connecting_area_list)):
			connect_graph.setdefault(connecting_area_list[i].current_standing_area, list())
			connect_graph[connecting_area_list[i].current_standing_area].append(connecting_area_list[i].next_standing_area)
		main_loop_i = 0
		while main_loop_i < len(main_loop_list):
			print(" {} th stage boss slay".format(main_loop_i + 1))
			sleep(self.AREA_CHECK_WAITING_INTERVAL)
			self.update()
			if not main_loop_list[main_loop_i].in_check(self.x, self.y):
				print("{}th check error, x, y is ({}, {})".format(i, self.x, self.y))
				relocate_succeed = False
				for j in range(len(standing_area_list)):
					if standing_area_list[j].in_check(self.x, self.y):
						print("{} th match found and start to go to the main loop list".format(j))
						relocate_succeed = True
						break # relocate and exit
				if not relocate_succeed:
					self.act_after_relocate_fail(standing_area_list[0])
					j = 0 # j is the cuurent element we r in the standing_area
					print("no match found move to the very first standing_area and start to go to the main loop list")
				self.come_to_destination_with_relocate(connect_graph, standing_area_list, connecting_area_list, standing_area_list[j], main_loop_list[main_loop_i], debug)
			self.update_boss_x(boss_x_list[main_loop_i])
			self.horizonal_move(main_loop_list[main_loop_i].attack_area_right_x, self.TOUCH_MOVE_DISTANCE)
			self.face_to_boss()
			self.attack_in_area(main_loop_list[main_loop_i], debug)
			if self.stage_change:
				print("i + 1")
				self.property_lock.acquire()
				self.stage_change = False
				self.property_lock.release()
				main_loop_i += 1
		pydirectinput.keyUp(self.attack_key, _pause=False)
		self.stop()
		print("stage boss done")
	

