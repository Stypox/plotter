#!/usr/bin/python3
# TODO optimization: remove useless moves next to each other
# TODO optimization: remove duplicate instructions

import struct
import enum

penAtBeginning = 0   # 0=up, 1=down

useG = True
useFeed = False
feedVisibleBelow = 500
useSpeed = False
speedVisibleBelow = 50

writeByte = b"w"
moveByte = b"m"
dilationCoefficient = 17
sizeXmm = 80
sizeYmm = 80
def mmToSteps(mm):
	return mm * 3000 / 52

class AttrType(enum.Enum):
	pen = 0,
	x   = 1,
	y   = 2


class Attribute:
	def __init__(self, word, lineNr):
		try:
			if word == "":
				self.type = ""
			else:
				self.type = word[0].upper()

				try:
					# attribute is an integer
					self.value = int(word[1:])
				except:
					# attribute is a floating point number
					self.value = float(word[1:])

				self.normalizeType()
		except:
			print("[%s,WARNING]: ignoring unknown attribute \"%s\"" % (lineNr, word))
			self.type = ""
	def __eq__(self, other):
		return self.type == other
	def __repr__(self):
		return repr(self.type) + ":" + repr(self.value)

	def normalizeType(self):
		if useFeed and self.type == "F":
			self.type = AttrType.pen
			self.value = 1 if self.value < feedVisibleBelow else 0
		elif useG and self.type == "G":
			if self.value == 0 or self.value == 1:
				self.type = AttrType.pen
			else:
				self.type = ""
		elif useSpeed and self.type == "S":
			self.type = AttrType.pen
			self.value = 1 if self.value < speedVisibleBelow else 0
		elif self.type == "X":
			self.type = AttrType.x
		elif self.type == "Y":
			self.type = AttrType.y
		else:
			self.type = ""

	def toBeIgnored(self):
		return self.type == ""

class ParsedLine:
	def __init__(self, line, lineNr, lastAttributes):
		self.originalLine = line
		self.lineNr = lineNr
		self.uncommentedLine = self.removeComments(line)
		self.attributes = {k: v for k, v in lastAttributes.items()}

		words = self.uncommentedLine.split(" ")

		i = 0
		while i < len(words):
			attribute = Attribute(words[i], lineNr)
			if not attribute.toBeIgnored():
				self.attributes[attribute.type] = attribute.value
			i += 1
	def __repr__(self):
		return ("[" + str(self.lineNr) + "," + " " * (5-len(str(self.lineNr))) + "data]" +
				"  pen=" + repr(self[AttrType.pen]) +
				("  x=%+.5f" % self[AttrType.x]) +
				("  y=%+.5f" % self[AttrType.y]))
	def __getitem__(self, key):
		return self.attributes[key]
	def __setitem__(self, key, value):
		self.attributes[key] = value

	def removeComments(self, line):
		begin = line.find("(")
		if begin == -1:
			return line
		else:
			end = line.find(")")
			if end == -1:
				print("[%s,WARNING]: missing closing parenthesis on comment starting in position %s" % (self.lineNr, begin+1))
				return line[:begin]
			else:
				print("[%s,comment] %s" % (self.lineNr, line[begin+1:end]))
				return line[:begin] + " " + self.removeComments(line[end+1:])
	
	def changedCoordinates(self, lastAttributes):
		# return True if the parsed line does nothing or only changes G or F values
		return (self[AttrType.x] != lastAttributes[AttrType.x] or
			self[AttrType.y] != lastAttributes[AttrType.y])

	def gcode(self):
		return "G%s X%.3f Y%.3f" % (repr(self[AttrType.pen]),
								self[AttrType.x],
								self[AttrType.y])

class EmptyLine:
	def __init__(self): pass
	def __repr__(self):
		return "[EOF,  data]  pen=0  x=0.00000f  y=0.00000f"
	def __getitem__(self, key):
		return 0
	
	def gcode(self):
		return "G0 X0.000 Y0.000"
	

def parse(data):
	lines = data.split("\n")
	parsedLines = []
	lastAttributes = {
		AttrType.pen: penAtBeginning,
		AttrType.x: None,
		AttrType.y: None
	}

	for lineIndex in range(0, len(lines)):
		parsedLine = ParsedLine(lines[lineIndex], lineIndex+1, lastAttributes)
		if parsedLine.changedCoordinates(lastAttributes):
			parsedLines.append(parsedLine)
		lastAttributes = {k: v for k, v in parsedLine.attributes.items()}
		pass
	
	return parsedLines

def translateToFirstQuadrant(lines):
	translationX = -min([line[AttrType.x] for line in lines])
	translationY = -min([line[AttrType.y] for line in lines])

	for line in lines:
		line[AttrType.x] += translationX
		line[AttrType.y] += translationY
	
	return lines

def maxX(lines):
	return max([line[AttrType.x] for line in lines])
def maxY(lines):
	return max([line[AttrType.y] for line in lines])

def arduinoData(lines):
	stepsX, stepsY = 0, 0
	data = b""

	for line in lines:
		x = line[AttrType.x] * dilationCoefficient
		y = line[AttrType.y] * dilationCoefficient

		currentStepsX = int(round(x-stepsX))
		currentStepsY = int(round(y-stepsY))
		stepsX += currentStepsX
		stepsY += currentStepsY
		

		if line[AttrType.pen]:
			data += writeByte
		else:
			data += moveByte

		bytesX = currentStepsX.to_bytes(2, byteorder="big", signed=True)
		bytesY = currentStepsY.to_bytes(2, byteorder="big", signed=True)
		
		if len(bytesX) == 1:
			data += b'\x00'
		data += bytesX
		if len(bytesY) == 1:
			data += b'\x00'
		data += bytesY
	
	return data


def main():
	parsedLines = parse(open("input.nc").read())
	#print(*parsedLines[:100], sep="\n")

	parsedLines = translateToFirstQuadrant(parsedLines)
	global dilationCoefficient
	dilationCoefficient = min([
		mmToSteps(sizeXmm) / maxX(parsedLines),
		mmToSteps(sizeYmm) / maxY(parsedLines),
	])
	print("Dilatation coefficient:", dilationCoefficient)

	parsedLines.append(EmptyLine())
	open("gcode.nc", "w").write("\n".join([l.gcode() for l in parsedLines]))
	open("arduino.txt", "wb").write(arduinoData(parsedLines))

if __name__ == '__main__':
	main()