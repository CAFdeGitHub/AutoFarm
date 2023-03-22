import pyautogui, ctypes, pydirectinput, os
from time import sleep, time
from pynput import keyboard
from playsound import playsound
from datetime import datetime
from random import uniform
from Character import *
from Map import *
import numpy as np


class Mage(Character):
	"""docstring for Mage"""
	# some constant won't change between mage
	SELLING_TIME = 90
	TC_INTERVAL = 0.55 # 每次tc的间隔, 因为瞬移的cd大概是0.6, 但是在程序执行过程中一些if语句会有一些执行时间, 实际游戏tc的间隔会比这个大, 除非直接执行tc
	TELE_INTERVAL = 0.55
	ITEM_FULL_CHECK_INTERVAL = 120
	AREA_CHECK_WAITING_INTERVAL = 0.3
	MAX_CONNECTION_TIME = 5 # we can only be in connecting area in 20s or we are in some error, implemented later
	TELE_DISTANCE = 150
	TC_TO_ROPE_DISTANCE = 150
	VERTICAL_TELEPORT_MIN_DISTANCE = 30 # we must teleport at least this distance if we lower teleport currently
	HORIZONTAL_MOVE_IN_CHECK_DISTANCE = 10
	STUCK_CHECK_INTERVAL = 3

	# some initialized varaible
	tc_timer = None
	warning_clock = time()
	warning_count = 0
	

	def __init__(self, jump_key, attack_key, buff_key, buff_interval, pet_potion_key, teleport_key, farm_mapid=None, fast_tc=False, enable_relocate=False, relocate_fail_method=None):
		# fast tc is to fast tc without movement
		# we should get a maipid check thread
		super(Mage, self).__init__(jump_key, attack_key, buff_key, buff_interval, pet_potion_key)
		self.teleport_key = teleport_key
		self.tc_timer = time()
		self.direction = "right"
		if farm_mapid == None:
			# if none, farm at current map
			self.farm_mapid = self.get_pointer_singed_value(process, self.mapid_ptr)
		else:
			self.farm_mapid = farm_mapid
		self.fast_tc = fast_tc
		self.enable_relocate = enable_relocate
		self.relocate_fail_method = relocate_fail_method
		if self.enable_relocate and self.relocate_fail_method is None:
			raise Exception("relocate_fail_method should be specified")
		# self.buff_adding_thread = threading.Thread(target=self.buff_adding, args=())  # some map should start this thread while some not, attacker need this

		
	def mapid_check(self):
		while not self.stopped:
			if (self.get_pointer_singed_value(process, self.mapid_ptr) != self.farm_mapid):
				print("mapid check error happen stop the mage")
				self.stop()
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
			sleep(10)

	def get_mapid(self):
		return self.get_pointer_singed_value(process, self.mapid_ptr)

	def hp_check(self):
		while not self.stopped:
			if self.HP <= 1000:
				print("Hp less than 1000")
				pydirectinput.press("y", _pause=False)
			if self.HP == 0:
				print("dead and stop farm")
				self.stop()
				self.property_lock.acquire()
				self.current_state = State.EXIT_SCRIPT
				self.property_lock.release()
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
			sleep(1)

	def buff_adding(self):
		start_time = time()
		while not self.stopped:
			if time() - start_time >= self.buff_interval and self.current_state != State.DEAL_WARNING:
				# only add buff when state is not deal warning
				print("buff adding")
				self.movement_lock.acquire()
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
				sleep(5)
				pydirectinput.press(self.buff_key, _pause=False)
				sleep(self.BUFF_SPELL_TIME)
				# pydirectinput.press("r", _pause=False)
				self.movement_lock.release()
				start_time = time()
			sleep(30)

	def stucked_check(self):
		stuck_count = 0
		print("stucked_check start")
		self.update()
		old_x = self.x
		old_y = self.y
		while not self.stopped:
			if self.farm_mapid == 240010600:
				pydirectinput.keyUp("left", _pause=False)
				pydirectinput.keyUp("right", _pause=False)
				sleep(10)
				continue
			self.update()
			# print("old_x, old_y", old_x, old_y)
			# print("x, y", self.x, self.y)
			if abs(old_x - self.x) <= self.TOUCH_MOVE_DISTANCE and abs(old_y - self.y) <= self.TOUCH_MOVE_DISTANCE:
				stuck_count += 1
				# print("start stuck with stuck_count ", stuck_count)
			else:
				stuck_count = 0
			if stuck_count >= 3 and not self.fast_tc:
				print("deal with fast tc stuck")
				pydirectinput.keyUp("left", _pause=False)
				pydirectinput.keyUp("right", _pause=False)
				if (stuck_count + 5) % 10 == 0:
					print("try pause the char to deal with stuck")
					self.movement_lock.acquire()
					sleep(self.STUCK_CHECK_INTERVAL)
					self.movement_lock.release()
			if stuck_count >= 30:
				print("unexpected bug happen the character stucked, quit_game and kill program")
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
				# self.quit_game()
				print("stucked quit and recognize hp is", self.HP)
				print("stucked quit time is", datetime.utcfromtimestamp(time()).strftime('%Y-%m-%d_%H:%M:%S'))		
				os.kill(os.getpid(), 9)
			old_x = self.x
			old_y = self.y
			sleep(self.STUCK_CHECK_INTERVAL)
		# print("check over")


	def inititalize_pointer(self):
		super(Mage, self).inititalize_pointer()
		self.nearby_ppls_ptr = process.get_pointer(self.NEARBY_PPLS_COUNT_LIST[0], self.NEARBY_PPLS_COUNT_LIST[1:])
		self.eqp_full_cheak_ptr = process.get_pointer(self.EQUIMENT_FULL_CHEAK_LIST[0], self.EQUIMENT_FULL_CHEAK_LIST[1:])

	def start(self):
		super(Mage, self).start()
		mapid_check_thread = threading.Thread(target=self.mapid_check, args=())
		mapid_check_thread.start()
		hp_adding_thread = threading.Thread(target=self.hp_check, args=())  # some map should start this thread while some not, attacker need this
		hp_adding_thread.start()
		stucked_check_thread = threading.Thread(target=self.stucked_check, args=())
		stucked_check_thread.start()


	def on_press(self, key):
		# overwrite the parant method, for none fast tc case
		super(Mage, self).on_press(key) # deal with pasue and exit action
		if key == keyboard.Key.f10:
			if self.current_state == State.WARNING and self.f10_press_count == 0:
				print("deal warning")
				self.property_lock.acquire()
				self.current_state = State.DEAL_WARNING
				self.f10_press_count += 1
				self.property_lock.release()
			elif self.current_state == State.DEAL_WARNING:
				print("warning deal done")
				self.property_lock.acquire()
				self.current_state = State.ATTACKING
				self.f10_press_count = 0
				self.property_lock.release()
		elif key == keyboard.Key.tab:
			self.tab_press_count += 1
			self.tab_press_count = self.tab_press_count % 2
			if self.tab_press_count == 1:
				self.movement_lock.acquire()
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
				print("mage pause the script")
			else:
				self.movement_lock.release()
				print("mage resume the script")

	def direction_to_destination(self, destination):
		self.update()
		if self.x > destination:
			self.direction = "left"
		else:
			self.direction = "right"

	def tc(self, direction):
		# tc once towards direction 往一个方向tc 一次, 这里如果 _pause默认是true 这样每次按键有0.1s延迟, tc一定不成功
		# print("x, y is ({}, {}) tc at {}".format(self.x, self.y, direction))
		self.movement_lock.acquire()
		if not self.fast_tc:
			if direction != self.direction:
				# if not fast_tc and call tc outside the attack horizonal. let the key up
				pydirectinput.keyUp(self.direction, _pause=False)
		sleep(max(0, self.TC_INTERVAL + uniform(0, 0.1) - (time() - self.tc_timer)))
		pydirectinput.keyDown(direction, _pause=False)
		sleep(self.KEY_DELAY * 2) # multiply by 2 to get character head turned
		pydirectinput.keyDown(self.teleport_key, _pause=False)
		pydirectinput.keyDown(self.attack_key, _pause=False)
		sleep(self.KEY_DELAY)
		pydirectinput.keyUp(self.attack_key, _pause=False)
		pydirectinput.keyUp(self.teleport_key, _pause=False)
		if self.fast_tc:
			pydirectinput.keyUp(direction, _pause=False)
		self.tc_timer = time() 
		sleep(0.1) # this is for load the new x value 
		self.update()
		if not self.fast_tc:
			if direction != self.direction:
				# release the direction key or will cause some issue
				pydirectinput.keyUp(direction, _pause=False)
		self.movement_lock.release()
		
	def teleport(self, direction):
		# used to move long distance in major city, it's useless cuz like a robot play
		self.movement_lock.acquire()
		sleep(max(0, self.TC_INTERVAL - (time() - self.tc_timer)))
		pydirectinput.keyDown(direction, _pause=False)
		sleep(self.KEY_DELAY * 10) # keep direction down to tele
		pydirectinput.press(self.teleport_key, _pause=False)
		pydirectinput.keyUp(direction, _pause=False)
		self.tc_timer = time()
		self.movement_lock.release()

	def teleport_horizontal_to_dest(self, destination_x):
		# teleport to the nearby x of destination
		self.movement_lock.acquire()
		self.update()
		if self.x > destination_x:
			self.direction = "left"
		else:
			self.direction = "right"
		while abs(self.x - destination_x) > 200:
			pydirectinput.keyDown(self.direction, _pause=False)
			pydirectinput.press(self.teleport_key)
			sleep(self.TELE_INTERVAL)
			self.update()
			if self.x > destination_x and self.direction == "right":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "left"
			elif self.x <= destination_x and self.direction == "left":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "right"
		pydirectinput.keyUp(self.direction, _pause=False)
		self.movement_lock.release()

	@staticmethod
	def click_on_tp(mouse_x, mouse_y):
		# open item and click on the the mouse position (mouse_x, mouse_y) move down and double click
		pydirectinput.press("i")
		pydirectinput.moveTo(mouse_x, mouse_y, duration=2)
		pydirectinput.click() # click on the use tab
		pydirectinput.move(0, 25, duration=1) # move to the tp scroll (put it exactly below the use tab)
		pydirectinput.doubleClick() # double click to return
		sleep(6)

	@staticmethod
	def click_on_position(mouse_x, mouse_y):
		# double click the mouse postion (mouse_x, mouse_y)
		pydirectinput.moveTo(mouse_x, mouse_y, duration=2)
		pydirectinput.click()
		sleep(6)

	def sell_equip(self, mouse_x, mouse_y):
		# move mouse to (mouse_x, mouse_y) and keep double clicking and press y
		pydirectinput.moveTo(mouse_x, mouse_y, duration=2)
		start_time = time()
		while (time() - start_time) <= self.SELLING_TIME:
			# 75 second to sell all item
			if self.get_pointer_singed_value(process, self.eqp_full_cheak_ptr) == 0:
				# selling done if the last eqp is sold
				break
			pydirectinput.doubleClick()
			pydirectinput.press("y", _pause=False)
		pydirectinput.moveTo(459, 264, duration=2)
		pydirectinput.doubleClick() # quit the merchant diagolue
		sleep(self.ACTION_DELAY)

	def tele_floor(self, tele_loc_x, next_floor_y):
		# 记忆图需要的函数, 因为记忆图可以从1层按上传送到3层, 不需要爬梯子
		self.horizonal_move(tele_loc_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
		print("teleporting to next floor")
		self.update()
		self.movement_lock.acquire()
		if self.x > tele_loc_x:
			self.direction = "left"
		else:
			self.direction = "right"
		start_time = time()
		while abs(self.y - next_floor_y) >= self.VERTICAL_TELEPORT_MIN_DISTANCE:
			pydirectinput.keyDown("up", _pause=False)
			pydirectinput.keyDown(self.direction, _pause=False)
			sleep(self.KEY_DELAY * 10)
			self.update()
			if self.x > tele_loc_x and self.direction == "right":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "left"
			elif self.x <= tele_loc_x and self.direction == "left":
				pydirectinput.keyUp(self.direction, _pause=False)
				self.direction = "right"
			if time() - start_time > self.MAX_CONNECTION_TIME * 3:
				print("tele_floor fail")
				break
			# self.update()
		pydirectinput.keyUp(self.direction, _pause=False)
		pydirectinput.keyUp("up", _pause=False)
		self.movement_lock.release()
		print("teleport successed")

	def tele_next_map(self, tele_loc_x, next_mapid, current_mapid=None):
		self.update()
		if current_mapid == None:
			current_mapid = self.get_pointer_singed_value(process, self.mapid_ptr)
		self.teleport_horizontal_to_dest(tele_loc_x)
		start_time = time()
		fail_time = 0
		while self.get_pointer_singed_value(process, self.mapid_ptr)!= next_mapid:
			print("curr mapid is", self.get_pointer_singed_value(process, self.mapid_ptr))
			if self.get_pointer_singed_value(process, self.mapid_ptr) != current_mapid and self.get_pointer_singed_value(process, self.mapid_ptr) != next_mapid:
				print("unexpected error happen while tele_next_map")
				self.quit_game()
				pydirectinput.press("f8", _pause=False)
			self.horizonal_move(tele_loc_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
			pydirectinput.press("up")
			sleep(self.ACTION_DELAY * 2) # waiting for the next map loaded
			if fail_time >= 2:
				print("tele to mapid {} error and break, fail_time {}".format(next_mapid, fail_time))
				break
			fail_time += 1
			# self.update()
		if fail_time < 2:
			print("tele to mapid {} done".format(next_mapid))

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

	def deal_with_chat(self):
		# deal with chat method
		if self.current_state == State.ATTACKING or self.current_state == State.RESTING:
			#print("nothing happen")
			pass
		elif self.current_state == State.WARNING:
			# alter sound when warning 
			if self.warning_state == State.GM_CHAT_WARNING:
				print("gm warning")
				playsound("gmwenhua.wav")
			elif self.warning_state == State.TO_ALL_CHAT_WARNING:
				print("wanjia warning")
				playsound("wanjiawenhua.wav")
			else:
				print("siliao warning")
				playsound("siliao.wav")
			self.property_lock.acquire()
			self.warning_count += 1
			if self.warning_count == 1:
				self.warning_clock = time()
			else:
				if time() - self.warning_clock > 60:
					print("60 s pass quit game")
					if not self.fast_tc:
						# key up of direction key to climb rope or something
						pydirectinput.keyUp(self.direction, _pause=False)
					self.property_lock.release()
					self.quit_game()		
					os.kill(os.getpid(), 9)
					self.property_lock.acquire()
			self.property_lock.release()
		else:
			self.property_lock.acquire()
			self.warning_count = 0
			self.property_lock.release()
			print("deal WARNING")

	def check_eqp_full(self):
		if self.get_pointer_singed_value(process, self.eqp_full_cheak_ptr) == 0:
			return False
		else:
			return True

	def update(self):
		super(Mage, self).update()
		self.nearby_ppls = self.get_pointer_singed_value(process, self.nearby_ppls_ptr)

	def attack(self):
		self.tc(self.direction)

	def attack_horizontal(self, x_min, x_max):
		# tc with x coordinate between x_min and x_max and return the direction for further use
		# 在 x_min x_max 之间tc, 如果超过则改变方向且把方向输出
		self.update()
		if self.x > x_max:
			if self.direction == "right":
				pydirectinput.keyUp(self.direction, _pause=False)
			self.direction = "left"
			pydirectinput.keyDown(self.direction, _pause=False)
		elif self.x < x_min:
			if self.direction == "left":
				pydirectinput.keyUp(self.direction, _pause=False)
			self.direction = "right"
			pydirectinput.keyDown(self.direction, _pause=False)
		self.attack()
		self.update()

	def attack_in_area_once(self, standing_area, debug=False):
		# be used by connecting area
		if isinstance(standing_area, StandingCastArea):
			if not (standing_area.attack_area_left_x <= self.x <= standing_area.attack_area_right_x):
				self.attack_horizontal(standing_area.attack_area_left_x, standing_area.attack_area_right_x)
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
			self.movement_lock.acquire()
			pydirectinput.press(self.attack_key, _pause=False)
			sleep(self.TC_INTERVAL)
			self.movement_lock.release()
		elif isinstance(standing_area, DoubleCloseFlatform):
			# print("self.x is ", self.x)
			if standing_area.tc_upper_left_x <= self.x <= standing_area.tc_upper_right_x:
				# print("should be up? ", self.y, "upper_y", standing_area.upper_y)
				if self.y >= standing_area.upper_y:
					print("tc up")
					self.tc(standing_area.tc_dir)
			self.attack_horizontal(standing_area.attack_area_left_x, standing_area.attack_area_right_x)
		elif isinstance(standing_area, FlatPlatform):
			self.attack_horizontal(standing_area.attack_area_left_x, standing_area.attack_area_right_x)
		else:
			raise Exception("undefined standing_area action")

	def attack_in_area(self, standing_area, debug=False):
		"""
		define the attack action of standing_area. 
		check mapid only in attack in area 
		"""
		assert isinstance(standing_area, StandingArea)
		if debug:
			print("attacking in {}".format(standing_area))
		if not standing_area.whether_attack:
			assert standing_area.attack_time == 0
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
			self.attack_in_area_once(standing_area, debug)
		if not self.fast_tc:
			# key up of direction key to climb rope or something
			pydirectinput.keyUp(self.direction, _pause=False)

	def transport(self, connecting_area, tc_direction_before_jump=None, debug=False):
		"""
		define the action of connecting_area. 
		"""
		assert isinstance(connecting_area,ConnectingArea)
		if debug:
			print("transporting in {}".format(connecting_area))
		if isinstance(connecting_area, LowerJumpArea):
			self.update()
			while not (connecting_area.left_x <= self.x <= connecting_area.right_x):
					# jump when not nearby the rope is perfered
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			if tc_direction_before_jump is not None:
				print("tc the not None tc_direction_before_jump")
				self.tc(tc_direction_before_jump)
			self.jump_to_low_floor(connecting_area.lower_floor_y)
			sleep(self.AREA_CHECK_WAITING_INTERVAL)
		elif isinstance(connecting_area, MoveToFallArea):
			# fall to the lower area by horizonal movement
			self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			if connecting_area.move_dir == "left":
				self.direction_to_destination(connecting_area.left_x)
				while abs(self.x - connecting_area.current_standing_area.attack_area_left_x) >= self.TC_TO_ROPE_DISTANCE:
					self.attack_in_area_once(connecting_area.current_standing_area, debug)
					self.update()
				self.horizonal_move(connecting_area.left_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
			else:
				self.direction_to_destination(connecting_area.right_x)
				while abs(self.x - connecting_area.current_standing_area.attack_area_right_x) >= self.TC_TO_ROPE_DISTANCE:
					self.attack_in_area_once(connecting_area.current_standing_area, debug)
					self.update()
				self.horizonal_move(connecting_area.right_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
		elif isinstance(connecting_area, HorizontalTCConnectingArea):
			self.horizonal_move(connecting_area.tc_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
			self.tc(connecting_area.tc_dir)
			sleep(self.AREA_CHECK_WAITING_INTERVAL)
		elif isinstance(connecting_area, VerticalTCConnectingArea):
			self.update()
			while not (connecting_area.left_x <= self.x <= connecting_area.right_x):
				# print("x, y is {}, {}, VerticalTCConnectingArea is {} tc attack".format(self.x, self.y, connecting_area))
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			start_time = time()	
			self.update()
			old_y = self.y
			vertical_tc_fail_count = 0
			# max_y = max(connecting_area.next_standing_area.centroid_y, connecting_area.current_standing_area.centroid_y)
			# min_y = min(connecting_area.next_standing_area.centroid_y, connecting_area.current_standing_area.centroid_y)
			while not connecting_area.next_standing_area.in_check(self.x, self.y):
				# if not in the next area tc to it
				if time() - start_time > self.MAX_CONNECTION_TIME: # or not connecting_area.current_standing_area.in_check(self.x, self.y) or not (min_y <= self.y <= max_y)
					print("vertical_tc_fail_count is", vertical_tc_fail_count)
					print("some unexpected error happen in VerticalTCConnectingArea")
					break
				if vertical_tc_fail_count >= 2:
					print("vertical_tc_fail_count greater than 2, error happen in VerticalTCConnectingArea")
					break
				if connecting_area.tc_dir == "up":
					# we can tc in up direction but not the down
					self.tc(connecting_area.tc_dir)
					if self.y <= connecting_area.next_standing_area.centroid_y - self.VERTICAL_TELEPORT_MIN_DISTANCE:
						# unexpexted error make char upper than next_standing_area
						break
				else:
					self.teleport(connecting_area.tc_dir)
					if self.y >= connecting_area.next_standing_area.centroid_y + self.VERTICAL_TELEPORT_MIN_DISTANCE:
						# unexpexted error make char lower than next_standing_area
						break
				sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
				if abs(old_y - self.y) <= self.VERTICAL_TELEPORT_MIN_DISTANCE:
					vertical_tc_fail_count += 1
				old_y = self.y
		elif isinstance(connecting_area, UpperTeleportFloorArea):
			while not (connecting_area.left_x <= self.x <= connecting_area.right_x):
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			print("upper teleporting to next floor")
			self.update()
			self.movement_lock.acquire()
			while self.y > connecting_area.next_standing_area.centroid_y:
				# tc up to the upper area if being touched down 
				self.movement_lock.release()
				self.tc("up")
				self.horizonal_move(connecting_area.tele_loc_x, self.HORIZONTAL_MOVE_IN_CHECK_DISTANCE)
				self.movement_lock.acquire()
				while connecting_area.in_check(self.x, self.y):
					if self.y <= connecting_area.next_standing_area.centroid_y:
						break
					pydirectinput.keyDown("up", _pause=False)
					pydirectinput.keyDown(self.direction, _pause=False)
					sleep(self.KEY_DELAY * 10)
					self.update()
					if self.x > connecting_area.tele_loc_x and self.direction == "right":
						pydirectinput.keyUp(self.direction, _pause=False)
						self.direction = "left"
					elif self.x <= connecting_area.tele_loc_x and self.direction == "left":
						pydirectinput.keyUp(self.direction, _pause=False)
						self.direction = "right"
				pydirectinput.keyUp(self.direction, _pause=False)
				pydirectinput.keyUp("up", _pause=False)
			self.movement_lock.release()
			print("upper teleport successed")
		elif isinstance(connecting_area, UpperFootHoldRope):
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
				if connecting_area.connecting_area_y + connecting_area.in_check_tolerance <= self.y <= connecting_area.connecting_area_y + self.TELE_DISTANCE:
					# u must be close to connecting_area.connecting_area_y to tc up
					self.tc("up")
					sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
				while connecting_area.in_check(self.x, self.y):
					if self.y <= connecting_area.upper_floor_y:
						break
					if connecting_area.jump_dir is not None:
						if connecting_area.jump_dir == "right":
							if self.x > connecting_area.rope_x:
								self.horizonal_move(connecting_area.rope_x - 20, 10)
						else:
							if self.x <= connecting_area.rope_x:
								self.horizonal_move(connecting_area.rope_x + 20, 10)
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
						self.climb_floor(connecting_area.upper_floor_y)
				# sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
			print("upperhold climb ", climb_state)
		elif isinstance(connecting_area, TeleportFloorArea):
			while abs(self.x - connecting_area.tele_loc_x) > 100:
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			self.tele_floor(connecting_area.tele_loc_x, connecting_area.next_floor_y)
			if connecting_area.whether_buff:
				pydirectinput.press(self.buff_key)
				sleep(self.BUFF_SPELL_TIME)
			sleep(1)
		elif isinstance(connecting_area, Rope):
			self.direction_to_destination(connecting_area.rope_x)
			while abs(self.x - connecting_area.rope_x) > self.TC_TO_ROPE_DISTANCE:
					# 如果你离绳子很远不tc过来显得不像是人在玩
				self.attack_in_area_once(connecting_area.current_standing_area, debug)
				self.update()
			if not self.fast_tc:
				# key up of direction key to climb rope or something
				pydirectinput.keyUp(self.direction, _pause=False)
			if connecting_area.jump_dir is not None:
				while self.y > connecting_area.upper_floor_y:
					self.direction_to_destination(connecting_area.rope_x)
					if connecting_area.jump_dir == "right":
						while self.x > connecting_area.rope_x:
								# 如果你离绳子很远不tc过来显得不像是人在玩
							self.attack_in_area_once(connecting_area.current_standing_area, debug)
							sleep(self.AREA_CHECK_WAITING_INTERVAL)
							self.update()
						# self.horizonal_move(connecting_area.rope_x - self.JUMP_ROPE_AWAY_DISTNACE, self.JUMP_ROPE_AWAY_DISTNACE - 1)
					else:
						while self.x  < connecting_area.rope_x:
							# 如果你离绳子很远不tc过来显得不像是人在玩
							self.attack_in_area_once(connecting_area.current_standing_area, debug)
							sleep(self.AREA_CHECK_WAITING_INTERVAL)
							self.update()
						# self.horizonal_move(connecting_area.rope_x + self.JUMP_ROPE_AWAY_DISTNACE, self.JUMP_ROPE_AWAY_DISTNACE - 1) # move to right part let jump to rope to do the rest
					if not self.fast_tc:
						# key up of direction key to climb rope or something
						pydirectinput.keyUp(self.direction, _pause=False)
					if abs(self.x - connecting_area.rope_x) <= self.CLOSE_TO_ROPE_DINSTANCE:
						self.horizonal_move(connecting_area.rope_x, self.JUMP_ROPE_CLIMB_DISTANCE - 1)
					else:
						self.horizonal_move(connecting_area.rope_x, self.CLOSE_TO_ROPE_DINSTANCE)
					if self.y > connecting_area.lower_floor_y + self.JUMP_ROPE_CLIMB_DISTANCE:
						# the character must be touched down to the lower floor
						break
					self.jump_to_rope(connecting_area.rope_x, connecting_area.lower_floor_y)
					self.update()
					if(self.y < connecting_area.lower_floor_y - self.JUMP_ROPE_CLIMB_DISTANCE):
						if connecting_area.whether_buff:
							pydirectinput.press(self.buff_key)
							sleep(self.BUFF_SPELL_TIME)
						self.climb_floor(connecting_area.upper_floor_y)
			else:
				self.climb_to_high_floor(*(connecting_area.get_param()))
		else:
			raise Exception("undefined connecting_area action")

	def loop_farm(self, standing_area_list, connecting_area_list, total_loop, tc_direction_before_jump_list=None, debug=False):
		assert len(standing_area_list) == len(connecting_area_list)
		for i in range(len(standing_area_list)):
			assert standing_area_list[i] is connecting_area_list[i].current_standing_area
			assert standing_area_list[(i + 1) % len(standing_area_list)] is connecting_area_list[i].next_standing_area # when i reach the last elem, (i + 1) % len will reach to 0
		# assert the farm loop
		if tc_direction_before_jump_list is None:
			tc_direction_before_jump_list = [None] * len(connecting_area_list)
		else:
			assert len(tc_direction_before_jump_list) == len(connecting_area_list)
		loop = 0
		self.update()
		while loop <= total_loop and not self.stopped:
			print("current farm loop is ", loop)
			loop += 1
			i = 0
			while i < len(standing_area_list):
				self.attack_in_area(standing_area_list[i], debug)
				if self.stopped:
					break
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
				if self.enable_relocate:
					sleep(self.AREA_CHECK_WAITING_INTERVAL)
					self.update()
					relocate_succeed = False
					if not standing_area_list[i].in_check(self.x, self.y):
						for j in range(len(standing_area_list)):
							print("x, y is ", self.x, self.y)
							if standing_area_list[j].in_check(self.x, self.y):
								i = j
								relocate_succeed = True
								break # relocate and exit
						if not relocate_succeed:
							self.act_after_relocate_fail(standing_area_list[0])
							i = 0
							print("no match found move to the very first standing_area")
						continue # continue the attack in the new relocate area.
				self.transport(connecting_area_list[i], tc_direction_before_jump_list[i], debug)
				if self.enable_relocate:
					sleep(self.AREA_CHECK_WAITING_INTERVAL)
					self.update()
					if not connecting_area_list[i].next_standing_area.in_check(self.x, self.y):
						print("some unexpected accident happen relocate character standing_area")
						if not self.fast_tc:
							pydirectinput.keyUp(self.direction, _pause=False)
						if self.stopped:
							break
						old_y = self.y - 1 # make it enter the while loop at least once
						while old_y != self.y:
							# check whether the character is landing on a stable platform
							old_y = self.y
							sleep(self.KEY_DELAY * 10) # sleep 0.1 s
							self.update()
						relocate_succeed = False
						for j in range(len(standing_area_list)):
							if standing_area_list[j].in_check(self.x, self.y):
								# find the correct landing area
								print("{} th standing_area matched".format(j))
								i = j
								relocate_succeed = True
								break
						if not relocate_succeed:
							self.act_after_relocate_fail(standing_area_list[0])
							i = 0
							print("no match found move to the very first standing_area")
					else:
						i += 1
				else:
					i += 1
			# if self.check_eqp_full():
			# 	print("equipment full, stop farming")
			# 	break
		print("loop farm done")
		self.stop()

	# @staticmethod
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
		print("path is", path)
		temp_connect_list = []
		for i in range(len(path) - 1):
			for j in range(len(connecting_area_list)):
				if connecting_area_list[j].current_standing_area is path[i] and connecting_area_list[j].next_standing_area is path[i + 1]:
					temp_connect_list.append(connecting_area_list[j])
					break
		i = 0
		relocate_succeed = False
		while i < len(temp_connect_list):
			self.transport(temp_connect_list[i], None, debug)
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


	def loop_main_farm(self, standing_area_list, connecting_area_list, main_loop_list, total_loop, tc_direction_before_jump_list=None, debug=False):
		# standing_area_list contain all the map element, main_loop_list contain the element character mainly loop in.
		for standing_area in main_loop_list:
			assert standing_area in standing_area_list
		assert self.enable_relocate
		if tc_direction_before_jump_list is None:
			tc_direction_before_jump_list = [None] * len(connecting_area_list)
		connect_graph = dict()
		for i in range(len(connecting_area_list)):
			connect_graph.setdefault(connecting_area_list[i].current_standing_area, list())
			connect_graph[connecting_area_list[i].current_standing_area].append(connecting_area_list[i].next_standing_area)

		main_loop_connecting_list = []
		main_loop_tc_direction_before_jump_list = []
		for i in range(len(main_loop_list)):
			for j in range(len(connecting_area_list)):
				if connecting_area_list[j].current_standing_area is main_loop_list[i] and connecting_area_list[j].next_standing_area is main_loop_list[(i + 1) % len(main_loop_list)]:
					main_loop_connecting_list.append(connecting_area_list[j])
					main_loop_tc_direction_before_jump_list.append(tc_direction_before_jump_list[j])
					break
		print("main_loop_connecting_list is ")
		for i in main_loop_connecting_list:
			print(i)
		loop = 0
		self.update()
		while loop <= total_loop and not self.stopped:
			print("current farm loop is ", loop)
			loop += 1
			main_loop_i = 0
			while main_loop_i < len(main_loop_list):
				self.attack_in_area(main_loop_list[main_loop_i], debug)
				if self.stopped:
					break
				if not self.fast_tc:
					# key up of direction key to climb rope or something
					pydirectinput.keyUp(self.direction, _pause=False)
				sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
				if not main_loop_list[main_loop_i].in_check(self.x, self.y):
					if self.stopped:
						break
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
					self.come_to_destination_with_relocate(connect_graph, standing_area_list, connecting_area_list, standing_area_list[j], main_loop_list[0], debug)
					main_loop_i = 0
					continue
				self.transport(main_loop_connecting_list[main_loop_i], main_loop_tc_direction_before_jump_list[main_loop_i], debug)
				sleep(self.AREA_CHECK_WAITING_INTERVAL)
				self.update()
				if not main_loop_connecting_list[main_loop_i].next_standing_area.in_check(self.x, self.y):
					print("some unexpected accident happen relocate character standing_area")
					if not self.fast_tc:
						pydirectinput.keyUp(self.direction, _pause=False)
					if self.stopped:
						break
					old_y = self.y - 1 # make it enter the while loop at least once
					while old_y != self.y:
						# check whether the character is landing on a stable platform
						old_y = self.y
						sleep(self.KEY_DELAY * 10) # sleep 0.1 s
						self.update()
					relocate_succeed = False
					for j in range(len(standing_area_list)):
						if standing_area_list[j].in_check(self.x, self.y):
							# find the correct landing area
							if standing_area_list[j] in main_loop_list:
								main_loop_i = main_loop_list.index(standing_area_list[j])
							else:
								self.come_to_destination_with_relocate(connect_graph, standing_area_list, connecting_area_list, standing_area_list[j], main_loop_list[0], debug)
								main_loop_i = 0
							relocate_succeed = True
							break
					if not relocate_succeed:
						self.act_after_relocate_fail(standing_area_list[0])
						print("no match found move to the very first standing_area and start to go to the main loop list")
						self.come_to_destination_with_relocate(connect_graph, standing_area_list, connecting_area_list, standing_area_list[0], main_loop_list[0], debug)
						main_loop_i = 0
				else:
					main_loop_i += 1
			# if self.check_eqp_full():
			#	print("equipment full, stop farming")
			#	break
		print("loop farm done")
		self.stop()

















