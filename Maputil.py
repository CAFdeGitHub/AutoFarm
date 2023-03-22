from itertools import chain, tee
import copy
import numpy as np

IN_CHECK_TOLERANCE = 10
MIN_GAP_TO_MERGE = 5

LOWER_JUMP_Y_MAX_DIFF = 600
LOWER_JUMP_Y_MIN_DIFF = 20
MIMIMUM_JUMP_AREA_WIDTH = 50

MIN_GAP_TO_FALLING = 5


JUMP_HEIGHT = 78
JUMP_WIDTH = 74 # the width if u jump at horizon area


JUMP_ROPE_AWAY_DISTNACE = 55
ROPE_END_POINT_TOLERANCE = 5  # u can reach the next area even if u y are 5 distance from it
# Some utility function 
# Return true if line segments AB and CD intersect
def twoline_intersect(A,B,C,D):
	def ccw(A,B,C):
		return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
	return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)


def generate_node(startidx, arr, wallid, visited, nodelist, idtoidxdict):
	"""
	startidx: the node generating starting idx in arr
	arr: the last three element of arr matrix 
	wallid: id name of wall and 0
	visited: idx of foothold we have visited
	nodelist: the list of foothold idx which is connected
	idtoidxdict: convert idname of foothold to idx of foothold. 
	"""
	if visited[startidx] == 1:
		# return if we have visited this point
		return
	visited[startidx] = 1
	nodelist.append(startidx)
	if not (arr[startidx, 1] in wallid or visited[idtoidxdict[arr[startidx, 1]]] == 1):
		generate_node(idtoidxdict[arr[startidx, 1]], arr, wallid, visited, nodelist, idtoidxdict)
	if not (arr[startidx, 2] in wallid or visited[idtoidxdict[arr[startidx, 2]]] == 1):
		generate_node(idtoidxdict[arr[startidx, 2]], arr, wallid, visited, nodelist, idtoidxdict)


# function find overlap between lines segement
def overlapping_segment(a, b):
	# given two seg a = (a[0], a[1]), b = (b[0], b[1]). a overlap with b if x < y. 
	x = max(a[0], b[0])
	y = min(a[1], b[1])
	return x,y


def find_overlaps(r, b):
	# r b is list of line segment [(x1, x2), (x3, x4), ...]. segment between (x1, x2) (x3, x4)...
	retseg = []
	retidx = []
	ri = 0
	bi = 0
	while (ri < len(r)) and (bi < len(b)): 
		s = overlapping_segment(r[ri], b[bi])
		if s[0] < s[1]:
			retseg.append((s[0], s[1]))
			retidx.append((ri, bi))
		if r[ri][1] == s[1]:
			ri = ri + 1
		if b[bi][1] == s[1]:
			bi = bi + 1
	return retseg, retidx


# function for jumping distance calculation
def y_shift_by_x(x_diff):
	return -0.057 * x_diff ** 2 + 4.2162 * x_diff

def x_shift_by_forward_jump(y_diff):
	## y diff is the difference between next area y and current as numpy array
	## (156/37)/(2 * 78/1369) + np.sqrt((156/37)**2 + 4 * 78/1369 * y_diff) / (2 * 78/1369)
	## it's solution of a x **2 + b x - y_diff == 0. with JUMP_HEIGHT = 78. JUMP_WIDTH = 74
	## 4.21 = (156/37)
	ret = - np.ones_like(y_diff) * 1000  ## large number for non jumpable area
	suitableidx = np.where(y_diff >= -78) # next area is excluded if 78 higher than current
	ret[suitableidx] = np.array(4.216/0.114 + np.sqrt(17.7768 + 0.2279 * y_diff[suitableidx]) / 0.11395)
	return ret


# some foothold and map component based on foothold
class Footholds:
	def __init__(self, left_x, left_y, right_x, right_y):
		## upper y <= lower y
		self.left_x = left_x
		self.right_x = right_x
		self.left_y = left_y
		self.right_y = right_y
		self.lower_y = max(left_y, right_y)
		self.upper_y = min(left_y, right_y)
		self.slope = (self.right_y - self.left_y) / (self.right_x - self.left_x)
			
	def get_params(self):
		return {
			"left_x": self.left_x,
			"right_x": self.right_x,
			"left_y": self.left_y,
			"right_y": self.right_y
		}
	
	@staticmethod
	def y_at_location_x_inline(x, left_p, right_p):
		slope = (right_p[1] - left_p[1]) / (right_p[0] - left_p[0])
		if not(left_p[0] <= x <= right_p[0]):
			print(f"{x} not in line seg")
		return round(left_p[1] + slope * (x - left_p[0]))
#		 return (left_p[1] + slope * (x - left_p[0]))
	
	@staticmethod
	def point_in_line_seg(check_p, left_p, right_p):
		# check if a point in the line segment leftp -> rightp
		slope = (right_p[1] - left_p[1]) / (right_p[0] - left_p[0])
		if left_p[0] <= check_p[0] <= right_p[0]:
			return abs(check_p[1] - left_p[1] + slope * (check_p[0] - left_p[0])) <= IN_CHECK_TOLERANCE
		return False
	
	def point_in_ft(self, p):
		# check if a point in the footholds
		if self.left_x <= p[0] <= self.right_x:
			return abs(p[1] - self.left_y + self.slope * (p[0] - self.left_x)) <= IN_CHECK_TOLERANCE
		return False
	
	def y_at_location_x(self, x):
		if not (self.left_x <= x <= self.right_x):
			print(f"{x} not in area")
		return round(self.left_y + self.slope * (x - self.left_x))
#		 return (self.left_y + self.slope * (x - self.left_x))
	
	def get_plot_point(self):
		return (self.left_x, self.right_x), (self.left_y, self.right_y)
	
	def get_left_point(self):
		return (self.left_x, self.left_y)
	
	def get_right_point(self):
		return (self.right_x, self.right_y)
	
	def __str__(self):
		return f"left_x is {self.left_x}, right_x is {self.right_x}, lower_y is {self.lower_y}, upper is {self.upper_y}"
	

class MergedFootholds(Footholds):
	def __init__(self, left_x, left_y, right_x, right_y, inner_point_list):
		super().__init__(left_x, left_y, right_x, right_y)
		self.inner_point_list = copy.deepcopy(inner_point_list)
		self.upper_y = min(np.min(np.array(self.inner_point_list)[:, 1]), self.upper_y)
		self.lower_y = max(np.max(np.array(self.inner_point_list)[:, 1]), self.lower_y)
		
	def point_in_ft(self, p):
		a, b = tee(chain([(self.left_x, self.left_y)], self.inner_point_list, [(self.right_x,self.right_y)]))
		next(b, None)
		for lp, rp in zip(a, b): ## it's pairwise in 3.11
			if super().point_in_line_seg(p, lp, rp):
				return True
		return False
		
	def y_at_location_x(self, x):
		a, b = tee(chain([(self.left_x, self.left_y)], self.inner_point_list, [(self.right_x,self.right_y)]))
		next(b, None)
		for lp, rp in zip(a, b): ## it's pairwise in 3.11
			if lp[0] <= x <= rp[0]:
				return super().y_at_location_x_inline(x, lp, rp)
		print(f"{x} not in area")
		if x <= self.left_x:
			return super().y_at_location_x_inline(x, self.get_left_point(), self.inner_point_list[0])
		else:
			return super().y_at_location_x_inline(x, self.inner_point_list[-1],  self.get_right_point())
#		 return False
	
	def get_plot_point(self):
		xlist = [self.left_x]
		ylist = [self.left_y]
		for p in self.inner_point_list:
			xlist.append(p[0])
			ylist.append(p[1])
		xlist.append(self.right_x)
		ylist.append(self.right_y)
		return xlist, ylist
	
	def __str__(self):
		return f"left_x is {self.left_x}, right_x is {self.right_x}, lower_y is {self.lower_y}, upper is {self.upper_y}, {self.inner_point_list}"


class Ladder:
	def __init__(self, x, lower_y, upper_y, is_ladder):
		self.x = x
		self.lower_y = lower_y
		self.upper_y = upper_y
		self.is_ladder = is_ladder
		
	def get_plot_point(self):
		xlist = [self.x, self.x]
		ylist = [self.lower_y, self.upper_y]
		return xlist, ylist

	def __str__(self):
		return f"x is {self.x}, lower_y is {self.lower_y}, upper is {self.upper_y}"
		

# User defined class for traverse the foothold
class LowerJumpArea():
	def __init__(self, start_area, dest_area, jump_seg_list):
		# start area is upper one ande dest is lower
		self.start_area = start_area
		self.dest_area = dest_area
		self.jump_seg_list = jump_seg_list
	
	def __str__(self):
		return f"upper area y is {self.start_area.lower_y}, lower area y is {self.dest_area.lower_y}, jump list is {self.jump_seg_list}"
	

class FallingArea():
	def __init__(self, start_area, dest_area, falling_dir):
		self.start_area = start_area
		self.dest_area = dest_area
		self.falling_dir = falling_dir
	
	def __str__(self):
		return f"upper area y is {self.start_area.lower_y}, lower area y is {self.dest_area.lower_y}, falling_dir is {self.falling_dir}"

	
class ForwardJumpArea():
	def __init__(self, start_area, dest_area, jump_dir):
		self.start_area = start_area
		self.dest_area = dest_area
		self.jump_dir = jump_dir
	
	def __str__(self):
		return f"start area y is {self.start_area.lower_y}, dest area y is {self.dest_area.lower_y}, jump dir is {self.jump_dir}"
	

class DirectJumpArea():
	def __init__(self, start_area, dest_area, jump_dir):
		self.start_area = start_area
		self.dest_area = dest_area
		self.jump_dir = jump_dir
	
	def __str__(self):
		return f"start area y is {self.start_area.lower_y}, dest area y is {self.dest_area.lower_y}, jump dir is {self.jump_dir}"
	

class LadderArea:
	def __init__(self, start_area, dest_area, x, lower_y, upper_y, is_ladder, jump_dir):
		self.start_area = start_area
		self.dest_area = dest_area
		self.x = x
		self.lower_y = lower_y
		self.upper_y = upper_y  ## upper y < lower y 
		self.is_ladder = is_ladder ## whether it's rope or ladder
		self.jump_dir = jump_dir
		
	def __str__(self):
		return f"x is {self.x}, lower y is {self.lower_y}, upper y is {self.upper_y}"


