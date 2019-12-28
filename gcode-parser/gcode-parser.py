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

sizeXMm = 80
sizeYMm = 80
stepsToMmFactor = 3000 / 52
addHomeAtTheEnd = True

writeByte = b"w"
moveByte = b"m"


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
	@classmethod
	def fromRawCoordinates(cls, pen, x, y, lineNr=None):
		return cls({AttrType.pen: pen, AttrType.x: x, AttrType.y: y}, lineNr)
	
	@classmethod
	def fromGcodeLine(cls, attributeParser, line, lineNr, lastAttributes):
		def removeComments(code):
			begin = code.find("(")
			if begin == -1:
				return code
			else:
				end = code.find(")")
				if end == -1:
					print(f"[{lineNr},WARNING]: missing closing parenthesis on comment starting in position {begin+1}")
					return code[:begin]
				else:
					print(f"[{lineNr},comment]: {code[begin+1:end]}")
					return code[:begin] + " " + removeComments(code[end+1:])

		attributes = {k: v for k, v in lastAttributes.items()}
		words = removeComments(line).split(" ")

		for word in words:
			attribute = attributeParser.parseAttribute(word, lineNr)
			if attribute is not None:
				attributes[attribute[0]] = attribute[1]
	
		return cls(attributes, lineNr)


	def __init__(self, attributes, lineNr):
		self.attributes = attributes
		self.lineNr = lineNr

	def __repr__(self):
		lineRepr = "EOF" if self.lineNr is None else self.lineNr
		return f"[{lineRepr:>5} data]:   pen={self[AttrType.pen]}   x={self[AttrType.x]:>12.5f}   y={self[AttrType.y]:>12.5f}"

	def __getitem__(self, key):
		return self.attributes[key]

	def __setitem__(self, key, value):
		self.attributes[key] = value

	
	def shouldOverwrite(self, lastAttributes):
		return 	((self[AttrType.x] == lastAttributes[AttrType.x]
						and self[AttrType.y] == lastAttributes[AttrType.y]
						and self[AttrType.pen] == lastAttributes[AttrType.pen])
					or (self[AttrType.pen] == 0
						and lastAttributes[AttrType.pen] == 0))
	
	def gcode(self):
		return f"G{self[AttrType.pen]} X{self[AttrType.x]:.3f} Y{self[AttrType.y]:.3f}"


def translateToFirstQuarter(parsedGcode):
	translationX = -min([line[AttrType.x] for line in parsedGcode])
	translationY = -min([line[AttrType.y] for line in parsedGcode])

	for line in parsedGcode:
		line[AttrType.x] += translationX
		line[AttrType.y] += translationY
	
	return parsedGcode

def getDilationFactor(parsedGcode, sizeX, sizeY):
	"""
	parsedGcode must be first translated to the first quarter
	"""

	maxX = max([line[AttrType.x] for line in parsedGcode])
	maxY = max([line[AttrType.y] for line in parsedGcode])

	return min([
		sizeX / maxX,
		sizeY / maxY,
	])

def dilate(parsedGcode, dilationFactor):
	for line in parsedGcode:
		line[AttrType.x] *= dilationFactor
		line[AttrType.y] *= dilationFactor
	return parsedGcode


def arduinoData(parsedGcode):
	stepsX, stepsY = 0, 0
	data = b""

	for line in parsedGcode:
		currentStepsX = int(round(line[AttrType.x]-stepsX))
		currentStepsY = int(round(line[AttrType.y]-stepsY))
		stepsX += currentStepsX
		stepsY += currentStepsY		

		if line[AttrType.pen]:
			data += writeByte
		else:
			data += moveByte

		data += currentStepsX.to_bytes(2, byteorder="big", signed=True)
		data += currentStepsY.to_bytes(2, byteorder="big", signed=True)
	
	return data


def parseGcode(data, useG=False, feedVisibleBelow=None, speedVisibleBelow=None):
	attributeParser = AttributeParser(useG, feedVisibleBelow, speedVisibleBelow)
	lines = data.split("\n")
	# mostly safe: it should be overwritten by the first (move) command in data
	parsedGcode = [ParsedLine.fromRawCoordinates(0, 0, 0, 0)]

	for l in range(0, len(lines)):
		parsedLine = ParsedLine.fromGcodeLine(attributeParser, lines[l], l+1, parsedGcode[-1].attributes)
		if parsedLine.shouldOverwrite(parsedGcode[-1].attributes):
			print("overwriting", parsedLine, parsedGcode[-1])
			parsedGcode[-1] = parsedLine
		else:
			parsedGcode.append(parsedLine)

	# remove trailing command that does not write anything
	if len(parsedGcode) > 0 and parsedGcode[-1][AttrType.pen] == 0:
		parsedGcode = parsedGcode[:-1]

	return parsedGcode


def main():
	parsedGcode = parseGcode(open("input.nc").read(), useG=useG,
		feedVisibleBelow=(feedVisibleBelow if useFeed else None),
		speedVisibleBelow=(speedVisibleBelow if useSpeed else None))
	#print(*parsedGcode[:100], sep="\n")

	parsedGcode = translateToFirstQuarter(parsedGcode)
	if addHomeAtTheEnd:
		parsedGcode.append(ParsedLine.fromRawCoordinates(0, 0, 0))

	parsedGcode = dilate(parsedGcode, .1)
	open("gcode.nc", "w").write("\n".join([l.gcode() for l in parsedGcode]))

	dilationFactor = stepsToMmFactor * getDilationFactor(parsedGcode, sizeXMm, sizeYMm)
	parsedGcode = dilate(parsedGcode, dilationFactor)
	print("Dilatation coefficient:", dilationFactor)

	open("arduino.txt", "wb").write(arduinoData(parsedGcode))

if __name__ == '__main__':
	main()