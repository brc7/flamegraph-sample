import csv
import sys
import re
import string
from collections import defaultdict

class CallStackNode():
	"""CallStackNode recursively rebuilds the call stack from the output of the sample command"""
	def __init__(self, parent = None):

		self._parent = parent
		self._child_list = []

		self._level = -1
		self._name = 'HEAD'
		self._inclusive_samples = 0
		self._exclusive_samples = 0
		self._module_name = ''

		self._are_exclusives_computed = False

		# Module name / type delimiters.
		self._quote_pairs = {
			"(":")",
			"[":"]",
			"<":">",
		}
		self._pretty_print_chars = "+!:|"
		self._quote_starts = "".join(pair[0] for pair in self._quote_pairs.keys())

	def _parse_line(self, line):
		# Arguments:
		# 	line: A line of sample tool output, including all of the pretty-printed indentation
		# 	(e.g. + ! : |).
		# Returns:
		# 	stack_depth: The call stack depth.
		# 	info: A dict of (field, value) describing the stack trace line.

		# This is hacky, but sample doesn't output pretty-print indentation characters for
		# the first couple lines in the call graph (for some reason). In this case, we have
		# to add the whitespace indentation. Sample uses 2 spaces for each line of indentation.
		prefix_chars = string.whitespace + self._pretty_print_chars
		prefix_size = next(i for i, j in enumerate(line) if j not in prefix_chars)
		stack_depth = prefix_size // 2 - 2
		# End dirty hack.
		tokens = self._quoted_split(line[prefix_size:])

		info = defaultdict(str)
		if not tokens:
			return None
		try:
			# First token is the inclusive samples.
			if tokens[0].isdigit():
				info["inclusive"] = tokens[0]
			# Find the module token, in the format: "(in _____)".
			module_pattern = re.compile(r"\(in .+?\)")
			start_idx = 0
			module = ""
			for start_idx, token in enumerate(tokens):
				match = module_pattern.match(token)
				if match:
					module = match.group(0)[3:-1]
					break
			name = " ".join(tokens[1:start_idx])
			info["module"] = module
			info["name"] = name
		except:
			# Unable to set all parameters of the stack node.
			pass
		return stack_depth, info

	def _quoted_split(self, line):
		# splits the line while not splitting anything within quote-delimited substrings.
		items = []
		quote_depth = 0
		start_tag, end_tag = (None, None)
		buffer = ""
		for c in line:
			if c in self._quote_starts and quote_depth == 0:
				# We are starting a new quote zone.
				start_tag, end_tag = (c, self._quote_pairs[c])
				quote_depth += 1
			elif c == end_tag and quote_depth > 0:
				quote_depth -= 1
				if quote_depth == 0:
					# We just ended a quote zone.
					start_tag, end_tag = (None, None)

			if c in string.whitespace and quote_depth == 0:
				if buffer:
					items.append(buffer)
				buffer = ""
			else:
				buffer += c
		return items

	def setProfileData(self, line):
		data = self._parse_line(line)
		if data is not None:
			level, info = data
			self._level = level
			self._name = info["name"]
			self._module_name = info["module"]
			self._inclusive_samples = int(info["inclusive"])
			self._are_exclusives_computed = False

	def attach(self, node): 
		self._child_list.append(node)

	def computeExclusives(self):
		if self._are_exclusives_computed:
			return self._exclusive_samples
		# Otherwise calculate the number of exclusive samples based 
		# on the number of inclusive samples for each child.
		exclusive_samples = self._inclusive_samples
		for child in self._child_list:
			exclusive_samples = exclusive_samples - child.inclusive

		self._exclusive_samples = exclusive_samples
		for child in self._child_list:
			child.computeExclusives()
		self._are_exclusives_computed = True

	def stackCollapse(self): 
		stacktrace = []
		stacktrace.append(self._name)
		stackwalker = self._parent # recursively go back up the stack trace 
		if stackwalker is not None: # if this is not the very top node, which we don't want anyway (it's the system call to the executable)
			while stackwalker.parent is not None:
				stacktrace.append(stackwalker.name)
				stackwalker = stackwalker.parent
			stacktrace.reverse()

			tracestring = ";".join(stacktrace)
			tracestring = tracestring.replace(' ','')
			print(tracestring,self._exclusive_samples)
		for child in self._child_list: 
			child.stackCollapse()

	@property
	def level(self):
		return self._level

	@level.setter
	def level(self, value):
		self._level = value

	@property
	def name(self):
		return self._name

	@name.setter
	def name(self, value):
		self._name = value

	@property
	def inclusive(self): 
		return self._inclusive_samples

	@inclusive.setter
	def inclusive(self, value): 
		self._inclusive_samples = value

	@property
	def exclusive(self):
		self.computeExclusives()
		return self._exclusive_samples

	@exclusive.setter
	def exclusive(self, value): 
		self._exclusive_samples = value

	@property
	def parent(self):
		return self._parent

	@parent.setter
	def parent(self, parent):
		self._parent = parent


class CallStackTree():
	def __init__(self):
		self.top_node = CallStackNode()
		self.current_node = self.top_node

	def add(self, new_node):
		if new_node.level > self.current_node.level:
			# If next node is deeper.
			if new_node.level == self.current_node.level + 1:
				# Next node should only ever be 1 deeper than the last.
				new_node.parent = self.current_node
				self.current_node.attach(new_node)
			else:
				# This shouldn't happen - next node should never be more
				# than 1 deeper than the last. If this does happen, we
				# add "fake nodes" in between to fill the gap.
				while new_node.level > self.current_node.level + 1:
					# Add a fake node in between.
					fake_node = CallStackNode(self.current_node)
					fake_node.level = self.current_node + 1
					fake_node.name = "UNKNOWN"
					fake_node.exclusive = 0
					self.current_node.attach(fake_node)
					self.current_node = fake_node
				new_node.parent = self.current_node
				self.current_node.attach(new_node)

		elif new_node.level == self.current_node.level:
			# If next node is at the same depth.
			if self.current_node.parent is not None:
				# We aren't at the top of the tree.
				new_node.parent = self.current_node.parent
				self.current_node.parent.attach(new_node)
			else:
				# We are at the top of the tree.
				new_node.parent = self.current_node

		elif new_node.level < self.current_node.level:
			# if the last node was a lot deeper than this one
			# This can happen when we're returning out of a deep stack trace 
			# Solution is to traverse back up until we get to the shared parent
			while new_node.level < self.current_node.level:
				self.current_node = self.current_node.parent
			# We found a sibling with the previous loop, use the shared parent.
			new_node.parent = self.current_node.parent
			self.current_node.parent.attach(new_node)
		self.current_node = new_node

	def stackCollapse(self):
		self.top_node.computeExclusives()
		self.top_node.stackCollapse()


if __name__ == '__main__':
	filename = sys.argv[1]
	infile = open(filename,'r')

	# Find the start of the call graph output.
	start_text = "Call graph:"
	for line in infile:
		if start_text in line:
			break

	# Parse the call graph.
	tree = CallStackTree()
	for line in infile:
		if line.isspace():
			# The call graph ends with an empty line, so we are done parsing.
			break
		node = CallStackNode()
		node.setProfileData(line)
		tree.add(node)

	tree.stackCollapse()
