import ctypes
from ReadWriteMemory import ReadWriteMemory

class GameMemeoryManager:

	def __init__(self, game_process):
		"game_process should be the name of game or process id"
		if (type(game_process) is int) or (type(game_process) is str):
			self.game_process = game_process
		else:
			raise ValueError('game_process should be process id or name of game')
		self.initialization()


	def initialization(self):
		rwm = ReadWriteMemory()
		if (type(self.game_process) is int):
			self.process = rwm.get_process_by_id(self.game_process)  # if multiple client
		else:
			self.process = rwm.get_process_by_name(self.game_process)
		self.process.open()

	def get_pointer_by_address_list(self, address_list):
		## get the pointer indicated by address list
		return self.process.get_pointer(address_list[0], address_list[1:])


	def read_signed_value_by_address_list(self, address_list):
		## read the value by the pointer indicated by address list
		return self.get_pointer_singed_value(self.get_pointer_by_address_list(address_list))

	# @staticmethod
	def get_pointer_singed_value(self, ptr):
		# get the unsigned int value at prt address from process 
		return ctypes.c_long(self.process.read(ptr) & 0xFFFFFFFF).value


	def recursive_get(self, start_address, first_offset, second_offset, visited, debug):
		firstadd = self.process.read(start_address+first_offset)
		if firstadd not in visited:
			visited.add(firstadd)
			if debug:
				print(f"address {hex(firstadd)} added")
			self.recursive_get(firstadd, first_offset, second_offset, visited, debug)
		secondadd = self.process.read(start_address+second_offset)
		if secondadd not in visited:
			visited.add(secondadd)
			if debug:
				print(f"address {hex(secondadd)} added")
			self.recursive_get(secondadd, first_offset, second_offset, visited, debug)


	def get_address_of_linked_list(self, start_address, first_offset, second_offset, debug):
		visited = set([start_address, 0])
		self.recursive_get(start_address, first_offset, second_offset, visited, debug)
		visited.remove(0)
		if debug:
			print(f"{start_address} find {len(visited)} elements")
		return visited
