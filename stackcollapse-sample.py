import csv
import sys
import re

class CallStackNode():
	"""CallStackNode recursively rebuilds the call stack from the output of the sample command"""
	def __init__(self, parent = None):

		self._parent = parent
		self._child_list = []

		self._level = -1
		self._name = ''
		self._inclusive_samples = 0
		self._exclusive_samples = 0
		self._module_name = ''

	def setProfileData(self,level,line): 
		self._level = level
		sampleLocation = re.search(r'\d+', line)
		if sampleLocation is not None: 
			self._inclusive_samples = int(sampleLocation.group())

		# self._name = (line.split('  ')[0]).split()[1]
		moduleLocation = re.search(r'(in.*)',line)
		if moduleLocation is not None: 
			modulestring = re.search(r'(in.*)',line).group()
			modulestring.replace('(in','')
			modulestring.replace(')','')
			self._module_name = modulestring
		if (sampleLocation is not None) and (moduleLocation is not None): 
			self._name = line[sampleLocation.end():moduleLocation.start()-1]
		# Decode the other shit here
		# (Level) (Function Name) (Inclusive Samples) (Exclusive Samples) (Inclusive Samples %) (Exclusive Samples %)	Module Name

	def attach(self, node): 
		self._child_list.append(node)

	def getParent(self): 
		return self._parent

	def getLevel(self): 
		return int(self._level)

	def getName(self): 
		return self._name

	def getInclusive(self): 
		return self._inclusive_samples

	def getExclusive(self): 
		return self._exclusive_samples

	def computeExclusives(self):
		# Calculates the number of exclusive samples based 
		# on the number of inclusive samples for each child 
		exclusive_samples = self._inclusive_samples 
		for child in self._child_list:
			exclusive_samples = exclusive_samples - child.getInclusive()

		self._exclusive_samples = exclusive_samples
		for child in self._child_list: 
			child.computeExclusives()


	def stackCollapse(self): 

		stacktrace = []
		stacktrace.append(self._name)
		stackwalker = self._parent # recursively go back up the stack trace 
		if stackwalker is not None: # if this is not the very top node, which we don't want anyway (it's the system call to the executable)
			while stackwalker.getParent() is not None: 
				stacktrace.append(stackwalker.getName())
				stackwalker = stackwalker.getParent()
			stacktrace.reverse()

			tracestring = ";".join(stacktrace)
			tracestring = tracestring.replace(' ','')
			print(tracestring,self._exclusive_samples)
		for child in self._child_list: 
			child.stackCollapse()

import sys

filename = sys.argv[1]

infile = open(filename,'r')

top_node = CallStackNode()
current_node = top_node

for line in infile:
	m = re.search(r'\d', line)
	if m is not None:
		levelstring = line[0:m.start()]
		level = len(levelstring)
		level = level//2-2

		if (level > current_node.getLevel()): # If the next node is deeper
			if (level == current_node.getLevel() + 1): # next node should only ever be 1 deeper than the last
				new_node = CallStackNode(current_node)
				new_node.setProfileData(level, line[m.start():])
				current_node.attach(new_node)
				current_node = new_node

		elif (level == current_node.getLevel()): # If the next node is at the same depth
			if (current_node.getParent() is not None): # if we aren't at the top
				current_node = current_node.getParent()
				new_node = CallStackNode(current_node)
				new_node.setProfileData(level, line[m.start():])
				current_node.attach(new_node)
				current_node = new_node
			else: # we're at the top
				new_node = CallStackNode(current_node)
				new_node.setProfileData(level, line[m.start():])
				current_node.attach(new_node)
				current_node = new_node
		elif (level < current_node.getLevel()): 
			# if the last node was a lot deeper than this one
			# This can happen when we're returning out of a deep stack trace 
			# Solution is to traverse back up until we get to the shared parent

			while (level < current_node.getLevel()): 
				current_node = current_node.getParent()
			current_node = current_node.getParent()
			new_node = CallStackNode(current_node)
			new_node.setProfileData(level, line[m.start():])
			current_node.attach(new_node)
			current_node = new_node


top_node.computeExclusives()
top_node.stackCollapse()

