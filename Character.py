import pyautogui, pydirectinput, threading, os
from datetime import datetime
from enum import Enum
from time import sleep, time
from pynput import keyboard
import numpy as np
from threading import Thread, Lock
from Maputil import *


class Character(object):
	"""Base class for character"""

	# address that character own
	MINIMAP_X_ADDRESS_LIST = [0x400000 + 0x007ED788, 0x648, 0x24, 0x640, 0x24, 0x5D4]  # address in minimap, use this address
	MINIMAP_Y_ADDRESS_LIST = [0x400000 + 0x007ED788, 0x648, 0x24, 0x640, 0x24, 0x5D8]  # address in minimap, use this address
	X_ADDRESS_LIST = [0xBEBF98, 0x3124] # true coor without minimap. warning: this value will reset to zero when entering map
	Y_ADDRESS_LIST = [0xBEBF98, 0x3128] # true coor without minimap. warning: this value will reset to zero when entering map
	BUFF_COUNT_ADDRESS_LIST = [0xBF4AD4]
	STATE_ADDRESS_LIST = [0xBEBF98, 0x64]
	DEBUFF_COUNT_ADDRESS_LIST = [0x400000 + 0X7EBF98, 0x2A68, 0x8]
	HUGER_ADDRESS_LIST = [0x400000 + 0x007F6860, 0x14, 0x10, 0xAC]
	BREATH_ADDRESS_LIST = [0x400000 + 0x007EBF98, 0x56c]
	MAPID_ADDRESS_LIST = [0x00BED788, 0x668]
	NEARBY_PPLS_COUNT_LIST = [0xBEBFA8, 0x18]
	ATTACK_COUNT_ADDRESS_LIST = [0xBEBF98, 0x2B88]


	MOB_X_OFFSET = [0x14, 0x120, 0x24, 0x60]
	MOB_Y_OFFSET = [0x14, 0x120, 0x24, 0x64]

	EQUIMENT_FULL_CHEAK_LIST = [0x400000 + 0x7F3CD8, 0x44b, 0x4 + 0x300] # 0x300 = (0x8) * (0x10 * 0x6) = offset * (total number of eqp)
	# use mob only when mob_count is 1

	DROP_COUNT_LIST = [0xBED6AC, 0x28]
	DROP_START_LIST = [0xBED6AC, 0x28+0x4]
	DROP_END_LIST = [0xBED6AC, 0x28+0x8]

	CURRENT_OFFSET = [0x4] # this should be plus or minus 0x1c * n to get other item, i think the off set should be in the start and end value. may be the same with mob
	# test all 0x8 +- (0x1c * n) value, if it's 0x18 then countinue. 
	NEXT_ITEM_OFFSET = [0x4-0x10, 0x14]
	NEXT_NEXT_ITEM_OFFSET = [0x4-0x10, 0x4, 0x14]
	NEXT_NEXT_NEXT_ITEM_OFFSET = [0x4-0x10, 0x4, 0x4, 0x14]
	ITEM_OR_NOT = [0x30] 
	ITEM_ID = [0x34]
	ITEM_X = [0x38, 0x5c]
	ITEM_Y = [0x38, 0x60]
	
	


	DIRECTION_SET = ["left", "right"]
	VERTICAL_DIRECTION_SET = ["up", "down"]

	# some constant won't change between character
	KEY_DELAY = 0.01 # autohotkey 的键盘每次按键之间的延迟
	JUMP_ROPE_CLIMB_TIME = 0.5 # 跳上绳子后先爬0.5s到达安全位置
	JUMP_ROPE_CLIMB_DISTANCE = 50 # 50 移速爬0.5秒绳子大概y移动这么多距离
	MAP_IN_CHECK_TOLERANCE = 20
	CLOSE_TO_ROPE_DINSTANCE = 70
	JUMP_ROPE_AWAY_DISTNACE = 55 # 距离绳子大概40-50 之后才能比较好的跳到绳子上.
	TOUCH_MOVE_DISTANCE = 90 # 被怪touch 之后移动的距离
	ACTION_DELAY = 2 # 每次一个大的组建运行结束后的sleep时间或者转到下一个图需要的延迟
	BUFF_SPELL_TIME = 1 #释放buff后sleep的时间
	MAX_CONNECTION_TIME = 5 # we can only be in connecting area in 20s or we are in some error, implemented later
	HORIZONTAL_MOVE_IN_CHECK_DISTANCE = 10 # the tolerance for moving to some dest x
	HORIZONTAL_MOVE_NEARBY_DISTANCE = 100
	DIRECT_JUMP_TO_ROPE_TOLERANCE = 10

	# thread property
	stopped = True

	# some inner property charater own
	x = y = hunger = buff_count = nearby_ppls = mapid = attack_count = movement_lock = None
	HP = maxHP = MP = maxMP = 1000
	EXP = None
	direction = "right"
	tab_press_count = 0
	f10_press_count = 0
	current_state = State.RESTING
	warning_state = None
	

	def __init__(self, game_process, mapinfo, jump_key, attack_key, buff_key, buff_interval, pet_potion_key, attack_range=190, attack_interval=0.5, max_attack_count_permob = 3, debug=False):
		self.game_process = game_process
		self.mapinfo = mapinfo
		# property involved
		self.jump_key = jump_key
		self.attack_key = attack_key
		self.buff_key = buff_key
		self.buff_interval = buff_interval
		self.pet_potion_key = pet_potion_key
		self.inititalize_pointer()
		self.movement_lock = threading.Lock()
		self.property_lock = threading.Lock()
		self.attack_interval = attack_interval
		self.attack_range = attack_range
		self.debug = debug
		self.target_mob_add = None

		# listener involved
		pydirectinput.FAILSAFE = True # 使得你鼠标移到左上角的时候 程序强制退出
		listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
		listener.start()


	def attack_target_mob(self):
		attack_count = 0
		while not self.mob_is_alive(self.target_mob_add):
			pydirectinput.press(self.attack_key, _pause=False)
			sleep(self.attack_interval)
			attack_count += 1
			if attack_count > self.max_attack_count_permob:
				if self.debug:
					print("max attack count reach")
					break

	def search_and_move(self):
		while True:
			self.property_lock.acquire()
			self.target_mob_add, self.target_mob_coor = self.mapinfo.get_the_closest_mob()
			self.property_lock.release()
			self.mapinfo.path_finding(self.x, self.y, *self.target_mob_coor)
			traverse_success = self.traverse_path(self.mapinfo)
			if traverse_success:
				break

	def face_to_x(self, x):
		self.update()
		old_dir = self.direction
		self.set_moving_dir(x)
		if old_dir != self.direction:
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(self.KEY_DELAY * 3)
			pydirectinput.keyUp(self.direction, _pause=False)  # let the character face to the direction if pervious direction is oppsite


	def auto_hunt(self):
		while not self.stopped:
			self.search_and_move()
			self.update()
			while not (abs(mob_coor(self.target_mob_add)[0] - self.x) <= self.attack_range):
				self.horizonal_move(mob_coor(self.target_mob_add)[0], self.attack_range + self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
			self.face_to_x(mob_coor(self.target_mob_add)[0])
			self.attack_target_mob()

	def start(self):
		print("start the action of character")
		self.property_lock.acquire()
		self.stopped = False
		pet_caring_thread = threading.Thread(target=self.feed_pet_thread, args=())
		pet_caring_thread.start()
		farm_thread = threading.Thread(target=self.auto_hunt, args=())
		farm_thread.start()
		self.property_lock.release()


	def stop(self):
		print("stop the action of character")
		self.property_lock.acquire()
		self.stopped = True
		self.property_lock.release()


	def mob_is_alive(self, mob_add):
    	return (self.game_process.read_signed_value_by_address_list([mob_add + 0x4]) == 0x8f8f)


    def mob_coor(self, mob_add):
    	mob_x = self.game_process.read_signed_value_by_address_list(list(chain([mob_add + self.MOB_X_OFFSET[0]], self.MOB_X_OFFSET[1:])))
		mob_y = self.game_process.read_signed_value_by_address_list(list(chain([mob_add + self.MOB_Y_OFFSET[0]], self.MOB_Y_OFFSET[1:])))
		return (mob_x, mob_y)


	def feed_pet_thread(self):
		no_feed_count = 0
		while not self.stopped:
			if ((self.get_pointer_singed_value(self.hunger_ptr) <= 70) and no_feed_count >= 10) or no_feed_count >= 20:
				self.hunger = self.get_pointer_singed_value(self.hunger_ptr)
				print("pet hunger is {}, feed pet".format(self.hunger))
				self.movement_lock.acquire()
				sleep(self.ACTION_DELAY)
				pydirectinput.press(self.pet_potion_key)
				self.movement_lock.release()
				no_feed_count = 0
			sleep(60)
			no_feed_count += 1


	def get_pointer_singed_value(self, ptr):
		# get the unsigned int value at prt address from process 
		return self.game_process.get_pointer_singed_value(ptr)


	def inititalize_pointer(self):
		self.x_ptr = self.game_process.get_pointer_by_address_list(self.MINIMAP_X_ADDRESS_LIST)
		self.y_ptr = self.game_process.get_pointer_by_address_list(self.MINIMAP_Y_ADDRESS_LIST)
		self.hunger_ptr = self.game_process.get_pointer_by_address_list(self.HUGER_ADDRESS_LIST)
		self.buff_count_ptr = self.game_process.get_pointer_by_address_list(self.BUFF_COUNT_ADDRESS_LIST)
		self.mapid_ptr = self.game_process.get_pointer_by_address_list(self.MAPID_ADDRESS_LIST)
		self.ft_state_ptr = self.game_process.get_pointer_by_address_list(self.STATE_ADDRESS_LIST)
		
	def get_mapid(self):
		return self.get_pointer_singed_value(self.mapid_ptr)

	def movement_lock_decorator(self, func):
		def function_wrapper():
			self.movement_lock.acquire()
			func()
			self.movement_lock.release()
		return function_wrapper

	def update(self):
		"""
		update character stats
		"""
		self.property_lock.acquire()
		self.x = self.get_pointer_singed_value(self.x_ptr)
		self.y = self.get_pointer_singed_value(self.y_ptr)
		# self.hunger = self.get_pointer_singed_value(self.hunger_ptr)
		self.buff_count = self.get_pointer_singed_value(self.buff_count_ptr)
		self.ft_state = self.get_pointer_singed_value(self.ft_state_ptr)
		self.property_lock.release()

	def on_press(self, key):
		# only deal with quit event
		if key == keyboard.Key.f12:
			print("f12 press stop farm")
			self.stop()
		elif key == keyboard.Key.f8:
			print("f8 press exit script")
			self.current_state = State.EXIT_SCRIPT
			print("exit whole script")
			os.kill(os.getpid(), 9)


	def on_release(self, key):
		pass

	def horizonal_move(self, destination_x, tolerance):
	# move nearby the destination
	# 移动到x 正负 tolerance之间的位置, 因为程序执行会有延迟 很难到达真正的x, 所以到达大概的位置之后进行后续操作.	
		self.movement_lock.acquire()
		print("horizonal_move now")
		self.set_moving_dir(destination_x)
		self.update()
		while abs(self.x - destination_x) > tolerance:
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(self.KEY_DELAY)
			self.update()
			if self.x > destination_x and self.direction == self.DIRECTION_SET[1]:
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = self.DIRECTION_SET[0]
			elif self.x <= destination_x and self.direction == self.DIRECTION_SET[0]:
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = self.DIRECTION_SET[1]
		pydirectinput.keyUp(self.direction, _pause=False)
		self.movement_lock.release()


	def jump_to_rope(self, rope_x, lower_floor_y):
		# jump to the rope 
		# 跳到绳子上并爬一定时间到达安全位置
		self.update()
		if abs(self.x - rope_x) <= self.JUMP_ROPE_AWAY_DISTNACE:
			# move far away from rope to jump to rope
			self.horizonal_move(rope_x + np.sign(self.x - rope_x) * self.JUMP_ROPE_AWAY_DISTNACE, 10)
			pydirectinput.keyDown(self.DIRECTION_SET[int(np.sign(rope_x - self.x) + 1 / 2)], _pause=False)
			sleep(self.KEY_DELAY * 10)  # turn ur head back, don't need keyup cuz u want down next, 1s to get jump catch the rope
		if self.y <= lower_floor_y + self.JUMP_ROPE_CLIMB_DISTANCE:
			self.movement_lock.acquire()
			self.set_moving_dir(rope_x)
			pydirectinput.keyDown(self.direction, _pause=False)
			pydirectinput.keyDown(self.VERTICAL_DIRECTION_SET[0], _pause=False)
			sleep(self.KEY_DELAY)
			self.press_jump()
			pydirectinput.keyUp(self.direction, _pause=False)
			sleep(0.1) # time for jumpping on rope
			sleep(self.JUMP_ROPE_CLIMB_TIME)
			pydirectinput.keyUp(self.VERTICAL_DIRECTION_SET[0])
			self.update()
			self.movement_lock.release()

	def jump_vertical_to_rope(self, rope_x, lower_floor_y):
		self.update()
		self.movement_lock.acquire()
		while abs(self.x - rope_x) > self.DIRECT_JUMP_TO_ROPE_TOLERANCE:
			self.set_moving_dir(rope_x)
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(self.KEY_DELAY * 2)
			pydirectinput.keyUp(self.direction, _pause=False)
			self.update()
		if self.y <= lower_floor_y + self.JUMP_ROPE_CLIMB_DISTANCE:
			# if this is not true u r on the wrong area for jump
			pydirectinput.keyDown(self.VERTICAL_DIRECTION_SET[0], _pause=False)
			sleep(self.KEY_DELAY)
			self.press_jump()
			sleep(0.1) # time for jumpping on rope
			sleep(self.JUMP_ROPE_CLIMB_TIME)
			pydirectinput.keyUp(self.VERTICAL_DIRECTION_SET[0])
			self.update()
		self.movement_lock.release()


	def jump_down_rope(self, dest_x):
		# jump down from the rope towards dest x
		self.movement_lock.acquire()
		self.set_moving_dir(dest_x)
		pydirectinput.keyDown(self.direction, _pause=False)
		sleep(self.KEY_DELAY)
		self.press_jump()
		pydirectinput.keyUp(self.direction, _pause=False)
		self.movement_lock.release()



	def climb_rope(self):
		self.update()
		self.movement_lock.acquire()
		while self.on_rope_check() or self.on_ladder_check():
			pydirectinput.keyDown(self.VERTICAL_DIRECTION_SET[0], _pause=False)
			sleep(self.KEY_DELAY * 10)
		pydirectinput.keyUp(self.VERTICAL_DIRECTION_SET[0], _pause=False)
		self.movement_lock.release()



	def jump_to_low_floor(self, lower_floor_y):
		# jump to the lower floor
		# 下跳到下一层
		print("jump to the low floor")
		self.movement_lock.acquire()
		self.update()
		start_time = time()
		while True:
			if self.y > lower_floor_y - self.MAP_IN_CHECK_TOLERANCE:
				# if there are some obstable in between
				break
			if True:
				pydirectinput.keyDown("down", _pause=False)
				sleep(self.KEY_DELAY * 2)
				pydirectinput.press(self.jump_key , _pause=False)
				pydirectinput.keyUp("down", _pause=False)
			else:  # for reversed direction
				pydirectinput.press(self.jump_key , _pause=False)
			self.update()
			while self.on_air_check():
				# character is falling now
				sleep(self.KEY_DELAY * 10)
				self.update()

			if self.on_rope_check()	or self.on_ladder_check():
				# lower jump at rope postion
				self.jump_down_rope(self.direction)
				while self.on_air_check():
					sleep(self.KEY_DELAY * 10)
			if time() - start_time > self.MAX_CONNECTION_TIME:
				print("jump_to_low_floor error")
				break
		print("jump done")
		self.movement_lock.release()



	def quit_game(self):
		self.movement_lock.acquire()
		sleep(10)
		pydirectinput.press("esc", _pause=False)
		pydirectinput.press("up", _pause=False)
		pydirectinput.press("enter", _pause=False)
		sleep(self.MAX_CONNECTION_TIME)
		pydirectinput.moveTo(1014, 10, duration=2)
		pydirectinput.doubleClick() # double click to close the game windows
		self.movement_lock.release()
		print("quit time is", datetime.utcfromtimestamp(time()).strftime('%Y-%m-%d_%H:%M:%S'))

	def change_next_channel(self):
		self.movement_lock.acquire()
		sleep(10)
		pydirectinput.press("esc", _pause=False)
		sleep(self.KEY_DELAY)
		pydirectinput.press("enter", _pause=False)
		sleep(self.KEY_DELAY)
		pydirectinput.press("right", _pause=False)
		sleep(self.KEY_DELAY)
		pydirectinput.press("enter", _pause=False)
		self.movement_lock.release()


	def attack():
		pass
		
	def on_air_check(self):
		self.update()
		if self.ft_state == 0x630:
			return True
		else:
			return False

	def on_ground_check(self):
		self.update()
		if self.ft_state == 0x650:
			return True
		else:
			return False

	def on_rope_check(self):
		self.update()
		if self.ft_state == 0x6a0:
			return True
		else:
			return False

	def on_ladder_check(self):
		self.update()
		if self.ft_state == 0x6c0:
			return True
		else:
			return False


	def set_moving_dir(self, dest_x):
		self.update()
		if self.x > dest_x:
			self.direction = self.DIRECTION_SET[0]
		else:
			self.direction = self.DIRECTION_SET[1]

	def press_jump(self):
		if True:
			pydirectinput.press(self.jump_key, _pause=False)
		else:
			# when u direction are inversed
			pydirectinput.keyDown("down", _pause=False)
			sleep(self.KEY_DELAY)
			pydirectinput.press(self.jump_key, _pause=False)
			pydirectinput.keyUp("down", _pause=False)

	def jump_to_dest_x(self, dest_x):
		self.update()
		self.set_moving_dir(dest_x)
		if self.x > dest_x:
			pydirectinput.keyDown(self.direction, _pause=False)
			self.press_jump()
			while self.x > dest_x:
				pydirectinput.keyDown(self.direction, _pause=False)
				sleep(self.KEY_DELAY)
				self.update()
			pydirectinput.keyUp(self.direction, _pause=False)
		else:
			pydirectinput.keyDown(self.direction, _pause=False)
			self.press_jump()
			while self.x < dest_x:
				pydirectinput.keyDown(self.direction, _pause=False)
				sleep(self.KEY_DELAY)
				self.update()
			pydirectinput.keyUp(self.direction, _pause=False)


	def move_to(self, dest_x):
		# move near around dest x at current ft
		self.horizonal_move(dest_x, self.HORIZONTAL_MOVE_NEARBY_DISTANCE)

	def traverse_edge(self, edge):
		self.debug:
			print(edge)
		if isinstance(edge, LowerJumpArea):
			self.update()
			end_point = np.array(edge.jump_seg_list).flatten()
			idx = np.argmin(end_point - self.x)
			if not (edge.jump_seg_list[idx // 2][0] < self.x < edge.jump_seg_list[idx // 2][0]):
				self.move_to(end_point[idx])
			self.movement_lock.acquire()
			self.set_moving_dir(end_point[idx])
			while not (edge.jump_seg_list[idx // 2][0] < self.x < edge.jump_seg_list[idx // 2][0]):
				pydirectinput.keyDown(self.direction, _pause=False)
				sleep(self.KEY_DELAY)
				self.update()
				if self.x > edge.jump_seg_list[idx // 2][0] and self.direction == self.DIRECTION_SET[1]:
					# incase when u cross the lower jump area
					pydirectinput.keyUp(self.direction, _pause=False)
					self.direction = self.DIRECTION_SET[0]
				elif self.x <= edge.jump_seg_list[idx // 2][0] and self.direction == self.DIRECTION_SET[0]:
					pydirectinput.keyUp(self.direction, _pause=False)
					self.direction = self.DIRECTION_SET[1]
			self.movement_lock.release()
			self.jump_to_low_floor(edge.dest_area.y_at_location_x(self.x))

		elif isinstance(edge, FallingArea):
			self.update()
			if edge.falling_dir == "left":
				dest_x = edge.start_area.left_x - 1 # ensure the right direction obtained
				self.move_to(dest_x)
				self.movement_lock.acquire()
				self.set_moving_dir(dest_x)
				while self.x > dest_x:
					pydirectinput.keyDown(self.direction, _pause=False)
					sleep(self.KEY_DELAY)
					self.update()
			else:
				dest_x = edge.start_area.right_x + 1 
				self.move_to(dest_x)
				self.movement_lock.acquire()
				self.set_moving_dir(dest_x)
				while self.x < dest_x:
					pydirectinput.keyDown(self.direction, _pause=False)
					sleep(self.KEY_DELAY)
					self.update()
			while self.on_air_check():
				sleep(self.KEY_DELAY)
				# done when u reach ground
			self.movement_lock.release()

		elif isinstance(edge, ForwardJumpArea):
			self.update()
			if edge.jump_dir == "left":
				dest_x = edge.start_area.left_x
				self.move_to(dest_x)
				self.set_moving_dir(dest_x)
				# self.horizonal_move(dest_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				dest_x = edge.dest_area.right_x - 1
				self.jump_to_dest_x(dest_x)
			else:
				dest_x = edge.start_area.right_x
				self.move_to(dest_x)
				self.set_moving_dir(dest_x)
				# self.horizonal_move(dest_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				dest_x = edge.dest_area.left_x + 1
				self.jump_to_dest_x(dest_x)

		elif isinstance(edge, DirectJumpArea):
			self.update()
			if edge.jump_dir == "straight":
				if self.x > edge.dest_x.right_x:
					dest_x = edge.dest_x.right_x
				else:
					dest_x =  edge.dest_x.left_x ## if it's equal direction is right
				self.move_to(dest_x)
				self.movement_lock.acquire()
				self.set_moving_dir(dest_x)
				while not (edge.dest_x.left_x < self.x < edge.dest_x.right_x):
					self.keyDown(self.direction, _pause=False)
					sleep(self.KEY_DELAY)
					if self.x > edge.dest_x.right_x and self.direction == self.DIRECTION_SET[1]:
					# incase when u cross the lower jump area
						pydirectinput.keyUp(self.direction, _pause=False)
						self.direction = self.DIRECTION_SET[0]
					elif self.x <= edge.dest_x.left_x and self.direction == self.DIRECTION_SET[0]:
						pydirectinput.keyUp(self.direction, _pause=False)
						self.direction = self.DIRECTION_SET[1]
					self.update()
				self.press_jump()
				self.movement_lock.release()
			elif edge.jump_dir == "left":
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.right_x)
				dest_y = direct_jump.dest_area.right_y  ## ultimate dest
				x_shift = round(x_shift_by_forward_jump(np.array([dest_y - start_y]))[0])
				dest_x = (direct_jump.dest_area.right_x + x_shift) ## temporal dest
				# self.horizonal_move(dest_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.move_to(dest_x)
				dest_x = edge.dest_area.right_x - 1 ## ultimate dest
				self.set_moving_dir(dest_x)
				self.jump_to_dest_x(dest_x)
			elif edge.jump_dir == "right":
				start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.left_x)
				dest_y = direct_jump.dest_area.left_y
				x_shift = round(x_shift_by_forward_jump(np.array([dest_y - start_y]))[0])
				dest_x = (direct_jump.dest_area.left_x - x_shift)
				# self.horizonal_move(dest_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.move_to(dest_x)
				dest_x = edge.dest_area.left_x + 1 ## ultimate dest
				self.set_moving_dir(dest_x)
				self.jump_to_dest_x(dest_x)

		elif isinstance(edge, LadderArea):
			if edge.jump_dir == "straight":
				self.move_to(edge.x)
				self.jump_vertical_to_rope(edge.x, edge.start_area.y_at_location_x(edge.x))
				self.climb_rope()
			elif edge.jump_dir == "both":
				self.move_to(edge.x)
				self.jump_to_rope(edge.x, edge.start_area.y_at_location_x(edge.x))
				self.climb_rope()
			elif edge.jump_dir == "left":
				# move to left and jump
				self.move_to(edge.x)
				self.horizonal_move(edge.x - self.JUMP_ROPE_AWAY_DISTNACE, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.jump_to_rope(edge.x, edge.start_area.y_at_location_x(edge.x))
				self.climb_rope()
			elif edge.jump_dir == "right":
				# move to right and jump
				self.move_to(edge.x)
				self.horizonal_move(edge.x + self.JUMP_ROPE_AWAY_DISTNACE, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.jump_to_rope(edge.x, edge.start_area.y_at_location_x(edge.x))
				self.climb_rope()


	def traverse_path(self, mapinfo):
		traverse_success = True
		for edgeidx in mapinfo.ft_changing_edgeidx:
			ft_changing_edge = mapinfo.traverse_edge[edgeidx]
			traverse_area = mapinfo.edge_dict[ft_changing_edge[0]][ft_changing_edge[1]] # get the traverse area/edge
			self.traverse_edge(traverse_area)
			ground_check_count = 0
			self.update()
			while not self.on_ground_check():
				sleep(self.KEY_DELAY * 10)
				self.update()
				ground_check_count += 1
				if ground_check_count >= 20:
					if self.debug:
						print("2s elapsed and character is still not on ground")
					break
			if self.on_ground_check():
				if not traverse_area.dest_area.point_in_ft((self.x, self.y)):
					if self.debug:
						print("character don't reach the correct ft after traverse")
					traverse_success = False
					break  # break loop if not on the correct area.
		return traverse_success
			




