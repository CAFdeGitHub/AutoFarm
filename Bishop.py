import pyautogui, ctypes, pydirectinput, random
from time import sleep, time
from pynput import keyboard
from Mage import *
from Map import *
import numpy as np


class Bishop(Mage):
	"""docstring for Mage"""
	# some constant won't change between mage
	HS_INTERVAL = 90 # 隔90s加一次hs
	STUCK_CHECK_INTERVAL = 2
	ATTACK_SPAM_THRESHOLD = 60

	def __init__(self, jump_key, attack_key, buff_key, buff_interval, pet_potion_key, teleport_key, hs_key, hs_location_list, door_key, farm_mapid=None, fast_tc=False, enable_relocate=False, relocate_fail_method=None):
		# fast tc is to fast tc without movement
		# we should get a maipid check thread
		# hs_location_list is a list of a two elem tuple consisting of x and y
		super(Bishop, self).__init__(jump_key, attack_key, buff_key, buff_interval, pet_potion_key, teleport_key, farm_mapid, fast_tc, enable_relocate, relocate_fail_method)
		self.hs_key = hs_key
		self.hs_location_list = hs_location_list
		self.door_key = door_key

		self.hs_state = False
		self.hs_check_interval = 10
		self.hs_start_time = time()

	def hs_timer(self):
		if len(self.hs_location_list) > 0:
			while not self.stopped:
				if time() - self.hs_start_time >= self.HS_INTERVAL:
					if self.hs_state:
						# if pervious hs state is true, make it false and check more frequently
						self.property_lock.acquire()
						self.hs_state = False  # need to add hs.
						self.property_lock.release()
				sleep(self.hs_check_interval)
		else:
			self.property_lock.acquire()
			self.hs_state = True  # no need to add hs.
			self.property_lock.release()

	def inititalize_pointer(self):
		super(Bishop, self).inititalize_pointer()
		self.attack_count_ptr = process.get_pointer(self.ATTACK_COUNT_ADDRESS_LIST[0], self.ATTACK_COUNT_ADDRESS_LIST[1:])

	def start(self):
		super(Bishop, self).start()
		hs_timer_thread = threading.Thread(target=self.hs_timer, args=())
		hs_timer_thread.start()

	def hs_in_standing_area(self, standing_area, hs_location, debug=False):
		if isinstance(standing_area, FlatPlatform):
			if debug:
				print("hs in ", standing_area)
			self.update()
			#print("hs and self x is ", self.x)
			while abs(self.x - hs_location[0]) > 100:
				# tc to the x loc
				self.attack_horizontal(standing_area.attack_area_left_x, standing_area.attack_area_right_x)
				self.update()
			if not self.fast_tc:
				# key up of direction key to start hs thread
				pydirectinput.keyUp(self.direction, _pause=False)
			if abs(self.x - hs_location[0]) <= 10:
				#print("x is {}, hs loc is {} less than 10".format(self.x, hs_location[0]))
				sleep(3)
			else:
				self.horizonal_move(hs_location[0], self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
			pydirectinput.press(self.hs_key, _pause=False)
			sleep(self.BUFF_SPELL_TIME * 3) # to get hs properly spell
			self.property_lock.acquire()
			self.hs_state = True
			self.hs_start_time = time()
			self.property_lock.release()
		else:
			raise Exception("undefined standing_area action")

	def check_hs_in_standing_area(self, standing_area):
		if (not self.hs_state):
			# if need to hs to buyer then search for the list
			for hs_location in self.hs_location_list:
				if standing_area.in_check(*(hs_location)):
					if not self.fast_tc:
					# key up of direction key to start hs thread
						pydirectinput.keyUp(self.direction, _pause=False)
					self.hs_in_standing_area(standing_area, hs_location)
					break # break the searching if found
		
	def transport(self, connecting_area, tc_direction_before_jump=None, debug=False):
		assert isinstance(connecting_area,ConnectingArea)
		if isinstance(connecting_area, UpperFootHoldRope):
			if debug:
				print("transporting in {}".format(connecting_area))
			self.direction_to_destination(connecting_area.rope_x)
			while not (connecting_area.left_x <= self.x <= connecting_area.right_x):
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			print("upperhold climb to next floor")
			climb_state = "successed"
			self.update()
			while self.y > connecting_area.upper_floor_y:
				# tc up to the upper area if being touched down 
				if not connecting_area.current_standing_area.in_check(self.x, self.y):
					climb_state = "fail"
					break
				if not (connecting_area.left_x <= self.x <= connecting_area.right_x):
					self.horizonal_move(connecting_area.centroid_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.update()
				if connecting_area.connecting_area_y + connecting_area.in_check_tolerance <= self.y <= connecting_area.connecting_area_y + self.TELE_DISTANCE:
					# u must be close to connecting_area.connecting_area_y to tc up
					self.tc("up")
					sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
				while connecting_area.in_check(self.x, self.y):
					if self.y <= connecting_area.upper_floor_y:
						break
					if abs(self.x - connecting_area.rope_x) <= self.CLOSE_TO_ROPE_DINSTANCE:
						self.horizonal_move(connecting_area.rope_x, self.JUMP_ROPE_CLIMB_DISTANCE - 1)
					else:
						self.horizonal_move(connecting_area.rope_x, self.CLOSE_TO_ROPE_DINSTANCE)
					self.update()
					if self.y > connecting_area.lower_floor_y + self.JUMP_ROPE_CLIMB_DISTANCE:
						# the character must be touched down to the lower floor
						break
					self.jump_to_rope(connecting_area.rope_x, connecting_area.lower_floor_y)
					self.update()
					if(self.y < connecting_area.connecting_area_y - self.JUMP_ROPE_CLIMB_DISTANCE):
						if connecting_area.whether_buff:
							pydirectinput.press(self.buff_key)
							sleep(self.BUFF_SPELL_TIME)
						if not self.hs_state:
							for hs_location in self.hs_location_list:
								if connecting_area.in_check(*(hs_location)):
									print("press hs now")
									pydirectinput.press(self.hs_key)
									sleep(self.BUFF_SPELL_TIME)
									self.property_lock.acquire()
									self.hs_state = True
									self.hs_start_time = time()
									self.property_lock.release()
						self.climb_floor(connecting_area.upper_floor_y)
				# sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
			print("upperhold climb ", climb_state)
		elif isinstance(connecting_area, Rope):
			if debug:
				print("transporting in {}".format(connecting_area))
			self.direction_to_destination(connecting_area.rope_x)
			while abs(self.x - connecting_area.rope_x) > self.TC_TO_ROPE_DISTANCE:
					# 如果你离绳子很远不tc过来显得不像是人在玩
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			self.update()
			while self.y > connecting_area.upper_floor_y:
				if connecting_area.jump_dir is not None:
					self.direction_to_destination(connecting_area.rope_x)
					if connecting_area.jump_dir == "right":
						while self.x > connecting_area.rope_x:
								# 如果你离绳子很远不tc过来显得不像是人在玩
							self.attack_in_area_once(connecting_area.current_standing_area, debug)
							sleep(self.AREA_CHECK_WAITING_INTERVAL)
							self.update()
					else:
						while self.x  < connecting_area.rope_x:
							# 如果你离绳子很远不tc过来显得不像是人在玩
							self.attack_in_area_once(connecting_area.current_standing_area, debug)
							sleep(self.AREA_CHECK_WAITING_INTERVAL)
							self.update()
					if not self.fast_tc:
						# key up of direction key to climb rope or something
						pydirectinput.keyUp(self.direction, _pause=False)
					# make the character head turned
				self.update()
				if self.y > connecting_area.lower_floor_y + self.JUMP_ROPE_CLIMB_DISTANCE:
					# the character must be touched down to the lower floor
					break
				if abs(self.x - connecting_area.rope_x) <= self.CLOSE_TO_ROPE_DINSTANCE:
					self.horizonal_move(connecting_area.rope_x, self.JUMP_ROPE_CLIMB_DISTANCE - 1)
				else:
					self.horizonal_move(connecting_area.rope_x, self.CLOSE_TO_ROPE_DINSTANCE)
				self.jump_to_rope(connecting_area.rope_x, connecting_area.lower_floor_y)
				self.update()
				if(self.y < connecting_area.lower_floor_y - self.JUMP_ROPE_CLIMB_DISTANCE):
					if connecting_area.whether_buff:
						pydirectinput.press(self.buff_key)
						sleep(self.BUFF_SPELL_TIME)
					if not self.hs_state:
						for hs_location in self.hs_location_list:
							if connecting_area.in_check(*(hs_location)):
								pydirectinput.press(self.hs_key)
								sleep(self.BUFF_SPELL_TIME)
								self.property_lock.acquire()
								self.hs_state = True
								self.hs_start_time = time()
								self.property_lock.release()
					self.climb_floor(connecting_area.upper_floor_y)
		else:
			super(Bishop, self).transport(connecting_area, tc_direction_before_jump, debug)

	def attack_in_area_once(self, standing_area, debug=False):
		if isinstance(standing_area, BuffArea):
			pass
		else:
			super(Bishop, self).attack_in_area_once(standing_area, debug)

	def attack_in_area(self, standing_area, debug=False):
		"""
		define the attack action of standing_area. 
		check mapid only in attack in area 
		"""
		assert isinstance(standing_area, StandingArea)
		if debug:
			print("attacking in {}".format(standing_area))
		start_time = time()
		while time() - start_time < standing_area.attack_time:
			if self.stopped:
				break
			self.update()
			if self.enable_relocate:
				# if enable relocate we should locate character's postion
				if not standing_area.in_check(self.x, self.y):
					if not self.fast_tc:
						# key up of direction key to climb rope or something
						pydirectinput.keyUp(self.direction, _pause=False)
					if debug:
						print("area check error")
					break
			if isinstance(standing_area, FlatPlatform):
				self.check_hs_in_standing_area(standing_area)
			self.attack_in_area_once(standing_area, debug)
		if not self.fast_tc:
			# key up of direction key to climb rope or something
			pydirectinput.keyUp(self.direction, _pause=False)
















