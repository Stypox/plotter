#!/usr/bin/python3
# TODO optimization: remove useless moves next to each other
# TODO optimization: remove duplicate instructions

import struct
import enum

useG = True
useFeed = False
feedVisibleBelow = 500
useSpeed = False
speedVisibleBelow = 50

writeByte = b"w"
moveByte = b"m"
dilationCoefficient = 1 # placeholder value
sizeXmm = 80
sizeYmm = 80

def mmToSteps(mm):
	return mm * 3000 / 52


class AttrType(enum.Enum):
	pen = 0,
	x   = 1,
	y   = 2

class AttributeParser:
	def __init__(self, useG, feedVisibleBelow, speedVisibleBelow):
		self.useG = useG
		self.useFeed = feedVisibleBelow is not None
		self.feedVisibleBelow = feedVisibleBelow
		self.useSpeed = speedVisibleBelow is not None
		self.speedVisibleBelow = speedVisibleBelow

		if not self.useG and not self.useFeed and not self.useSpeed:
			raise ValueError("At least a method (G, feed or speed) has to be specified to parse gcode")
	
	def parseAttribute(self, word, lineNr):
		try:
			if word == "":
				key = ""
			else:
				try: # attribute value is an integer
					value = int(word[1:])
				except: # attribute value is a floating point number
					value = float(word[1:])

				key = word[0].upper()
				if   key == "F" and self.useFeed:
					key = AttrType.pen
					value = 1 if value < feedVisibleBelow else 0
				elif key == "G" and self.useG:
					if value == 0 or value == 1:
						key = AttrType.pen
					else:
						raise ValueError()
				elif key == "S" and self.useSpeed:
					key = AttrType.pen
					value = 1 if value < speedVisibleBelow else 0
				elif key == "X":
					key = AttrType.x
				elif key == "Y":
					key = AttrType.y
				else:
					raise ValueError()

			return (key, value)
		except:
			print(f"[{lineNr},WARNING]: ignoring unknown attribute \"{word}\"")
			return None
		

class ParsedLine:
	def __init__(self, attributeParser, line, lineNr, lastAttributes):
		self.lineNr = lineNr
		self.line = self.removeComments(line)
		self.attributes = {k: v for k, v in lastAttributes.items()}

		words = self.line.split(" ")
		for word in words:
			attribute = attributeParser.parseAttribute(word, lineNr)
			if attribute is not None:
				self.attributes[attribute[0]] = attribute[1]

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
				print(f"[{self.lineNr},WARNING]: missing closing parenthesis on comment starting in position {begin+1}")
				return line[:begin]
			else:
				print(f"[{self.lineNr},comment]: {line[begin+1:end]}")
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
	def __repr__(self):
		return "[EOF,  data]  pen=0  x=0.00000f  y=0.00000f"
	def __getitem__(self, key):
		return 0
	
	def gcode(self):
		return "G0 X0.000 Y0.000"


def translateToFirstQuarter(lines):
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


def parseGcode(data, useG=False, feedVisibleBelow=None, speedVisibleBelow=None):
	attributeParser = AttributeParser(useG, feedVisibleBelow, speedVisibleBelow)
	lines = data.split("\n")
	parsedLines = []
	lastAttributes = {
		AttrType.pen: None,
		AttrType.x: None,
		AttrType.y: None
	}

	for l in range(0, len(lines)):
		parsedLine = ParsedLine(attributeParser, lines[l], l+1, lastAttributes)
		if parsedLine.changedCoordinates(lastAttributes):
			parsedLines.append(parsedLine)
		lastAttributes = {k: v for k, v in parsedLine.attributes.items()}
	
	return parsedLines


def main():
	parsedLines = parseGcode(open("input.nc").read(), useG=useG,
		feedVisibleBelow=(feedVisibleBelow if useFeed else None),
		speedVisibleBelow=(speedVisibleBelow if useSpeed else None))
	#print(*parsedLines[:100], sep="\n")

	parsedLines = translateToFirstQuarter(parsedLines)
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