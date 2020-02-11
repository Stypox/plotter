#!/usr/bin/python3
#pylint: disable=no-member

from enum import Enum
import argparse
import sys
import re
import math

writeByte = b"w"
moveByte = b"m"


def _log_nothing(*args, **kwargs):
	pass


class AttrType(Enum):
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

	def parseAttribute(self, word, lineNr, log=_log_nothing):
		try:
			try: # attribute value is an integer
				value = int(word[1:])
			except ValueError: # attribute value is a floating point number
				value = float(word[1:])

			key = word[0].upper()
			if   key == "G" and self.useG:
				if value == 0 or value == 1:
					key = AttrType.pen
				else:
					raise ValueError()
			elif key == "F" and self.useFeed:
				key = AttrType.pen
				value = 1 if value < self.feedVisibleBelow else 0
			elif key == "S" and self.useSpeed:
				key = AttrType.pen
				value = 1 if value < self.speedVisibleBelow else 0
			elif key == "X":
				key = AttrType.x
			elif key == "Y":
				key = AttrType.y
			else:
				raise ValueError()

			return (key, value)
		except (ValueError, IndexError):
			if word != "":
				log(f"[WARNING {lineNr:>5}]: ignoring unknown attribute \"{word}\"")
			return None


class ParsedLine:
	@classmethod
	def fromRawCoordinates(cls, pen, x, y, lineNr=None):
		return cls({AttrType.pen: pen, AttrType.x: x, AttrType.y: y}, lineNr)

	@classmethod
	def fromGcodeLine(cls, attributeParser, line, lineNr, lastAttributes, log=_log_nothing):
		def removeComments(code):
			begin = code.find("(")
			if begin == -1:
				return code
			else:
				end = code.find(")")
				if end == -1:
					log(f"[WARNING {lineNr:>5}]: missing closing parenthesis on comment starting in position {begin+1}")
					return code[:begin]
				else:
					log(f"[comment {lineNr:>5}]: {code[begin+1:end]}")
					return code[:begin] + " " + removeComments(code[end+1:])

		attributes = {k: v for k, v in lastAttributes.items()}
		words = removeComments(line).split(" ")

		for word in words:
			attribute = attributeParser.parseAttribute(word, lineNr, log=log)
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


def detectParsingMode(data, log=_log_nothing):
	logLabel = "[info] parsing mode detection:"
	gRegex = r"(?:\s|\A)[Gg]([01])(?:\s|\Z)"
	feedRegex = r"(?:\s|\A)[Ff]([-+]?(?:[0-9]*\.[0-9]+|[0-9]+))(?:\s|\Z)"
	speedRegex = r"(?:\s|\A)[Ss]([-+]?(?:[0-9]*\.[0-9]+|[0-9]+))(?:\s|\Z)"

	gInvisibleCount, gVisibleCount = 0, 0
	for gMatch in re.finditer(gRegex, data):
		if gMatch.group(0) == "0": gInvisibleCount += 1
		else: gVisibleCount += 1
	log(logLabel, f"found {gInvisibleCount} invisible G attributes and {gVisibleCount} visible ones")

	def getVisibilityFeedOrSpeed(regex):
		foundValues, allCount = {}, 0
		for match in re.finditer(regex, data):
			allCount += 1
			if match.group(1) in foundValues:
				foundValues[match.group(1)] += 1
			else:
				foundValues[match.group(1)] = 1

		average = 0
		for value, count in foundValues.items():
			average += float(value) * count
		average /= allCount

		invisibleCount, visibleCount = 0, 0
		for value, count in foundValues.items():
			if float(value) > average:
				invisibleCount += count
			else:
				visibleCount += count

		return invisibleCount, visibleCount, average

	feedInvisibleCount, feedVisibleCount, feedThreshold = getVisibilityFeedOrSpeed(feedRegex)
	log(logLabel, f"found {feedInvisibleCount} invisible feed attributes and " +
		f"{feedVisibleCount} visible ones, with a feed threshold of {feedThreshold}")

	speedInvisibleCount, speedVisibleCount, speedThreshold = getVisibilityFeedOrSpeed(speedRegex)
	log(logLabel, f"found {speedInvisibleCount} invisible speed attributes and " +
		f"{speedVisibleCount} visible ones, with a feed threshold of {speedThreshold}")


	def score(invisible, visible): # higher is better
		return ((1.0 - abs(invisible - visible) / (invisible + visible))
			* (0.5 + 0.5 * visible / (invisible + visible))
			* math.log10(invisible + visible))

	gScore = score(gInvisibleCount, gVisibleCount)
	feedScore = score(feedInvisibleCount, feedVisibleCount)
	speedScore = score(speedInvisibleCount, speedVisibleCount)
	log(logLabel, f"gScore={gScore}, feedScore={feedScore}, speedScore={speedScore}")

	maxScore = max(gScore, feedScore, speedScore)
	if maxScore == gScore:
		log(logLabel, "chosen g mode")
		return  True,  None,          None
	elif maxScore == feedScore:
		log(logLabel, f"chosen feed mode with feed visible below {feedThreshold}")
		return  False, feedThreshold, None
	else:
		log(logLabel, f"chosen speed mode with speed visible below {speedThreshold}")
		return  False, None,          speedThreshold


def translateToFirstQuarter(parsedGcode, log=_log_nothing):
	translationX = -min([line[AttrType.x] for line in parsedGcode])
	translationY = -min([line[AttrType.y] for line in parsedGcode])

	for line in parsedGcode:
		line[AttrType.x] += translationX
		line[AttrType.y] += translationY

	log(f"[info] Translation vector: ({translationX}, {translationY})")
	return parsedGcode

def getDilationFactor(parsedGcode, xSize, ySize):
	xSizeReal = max([line[AttrType.x] for line in parsedGcode]) - min([line[AttrType.x] for line in parsedGcode])
	ySizeReal = max([line[AttrType.y] for line in parsedGcode]) - min([line[AttrType.y] for line in parsedGcode])

	return min([
		xSize / xSizeReal,
		ySize / ySizeReal,
	])

def dilate(parsedGcode, dilationFactor):
	for line in parsedGcode:
		line[AttrType.x] *= dilationFactor
		line[AttrType.y] *= dilationFactor
	return parsedGcode

def addEnd(parsedGcode, endHome=False, log=_log_nothing):
	if endHome:
		parsedGcode.append(ParsedLine.fromRawCoordinates(0, 0, 0))
		log("[info] The gcode path ends at (0, 0)")
	elif len(parsedGcode) > 0:
		parsedGcode.append(ParsedLine.fromRawCoordinates(0,
			parsedGcode[-1][AttrType.x], parsedGcode[-1][AttrType.y]))
		log(f"[info] Before dilating the gcode path ends at ({parsedGcode[-1][AttrType.x]}, {parsedGcode[-1][AttrType.y]})")
	return parsedGcode

def resize(parsedGcode, xSize, ySize, dilation=1.0, log=_log_nothing):
	dilationFactor = dilation * getDilationFactor(parsedGcode, xSize, ySize)
	parsedGcode = dilate(parsedGcode, dilationFactor)

	log("[info] Dilation factor:", dilationFactor)
	return parsedGcode

def toGcode(parsedGcode):
	return "\n".join([l.gcode() for l in parsedGcode], ) + "\n"

def toBinaryData(parsedGcode):
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

def parseGcode(data, useG=False, feedVisibleBelow=None, speedVisibleBelow=None, log=_log_nothing):
	attributeParser = AttributeParser(useG, feedVisibleBelow, speedVisibleBelow)
	lines = data.split("\n")
	# mostly safe: it should be overwritten by the first (move) command in data
	parsedGcode = [ParsedLine.fromRawCoordinates(0, 0, 0, 0)]

	for l in range(0, len(lines)):
		parsedLine = ParsedLine.fromGcodeLine(attributeParser, lines[l], l+1, parsedGcode[-1].attributes, log=log)
		if parsedLine.shouldOverwrite(parsedGcode[-1].attributes):
			parsedGcode[-1] = parsedLine
		else:
			parsedGcode.append(parsedLine)

	# remove trailing command that does not write anything
	if len(parsedGcode) > 0 and parsedGcode[-1][AttrType.pen] == 0:
		parsedGcode = parsedGcode[:-1]

	return parsedGcode


def parseArgs(namespace):
	argParser = argparse.ArgumentParser(fromfile_prefix_chars="@",
		description="Parse the gcode provided on stdin and apply transformations")
	ioGroup = argParser.add_argument_group("Input/output options")
	ioGroup.add_argument("-i", "--input", type=argparse.FileType('r'), default="-", metavar="FILE",
		help="File from which to read the gcode to parse")
	ioGroup.add_argument("-o", "--output", type=argparse.FileType('w'), required=False, metavar="FILE",
		help="File in which to save the generated gcode")
	ioGroup.add_argument("-b", "--binary-output", type=argparse.FileType('wb'), required=False, metavar="FILE",
		help="File in which to save the binary data ready to be fed to the plotter")
	ioGroup.add_argument("-l", "--log", type=argparse.FileType('w'), required=False, metavar="FILE",
		help="File in which to save logs, comments and warnings")

	parseGroup = argParser.add_argument_group("Gcode parsing options (detected automatically if not provided)")
	parseGroup.add_argument("-g", "--use-g", action="store_true",
		help="Consider `G0` as pen up and `G1` as pen down")
	parseGroup.add_argument("--feed-visible-below", type=float, metavar="VALUE",
		help="Consider `F` (feed) commands with a value above the provided as pen down, otherwise as pen up")
	parseGroup.add_argument("--speed-visible-below", type=float, metavar="VALUE",
		help="Consider `S` (speed) commands with a value above the provided as pen down, otherwise as pen up")

	genGroup = argParser.add_argument_group("Gcode generation options")
	genGroup.add_argument("--end-home", action="store_true",
		help="Add a trailing instruction to move to (0,0) instead of just taking the pen up")
	genGroup.add_argument("-s", "--size", type=str, default="1.0x1.0", metavar="XxY",
		help="The size of the print area in millimeters (e.g. 192.7x210.3)")
	genGroup.add_argument("-d", "--dilation", type=float, default=1.0, metavar="FACTOR",
		help="Dilation factor to apply (useful to convert mm to steps)")

	argParser.parse_args(namespace=namespace)


	if namespace.output is None and namespace.binary_output is None:
		argParser.error("at least one of --output, --binary-output should be provided")

	try:
		size = namespace.size.split("x")
		namespace.xSize = float(size[0])
		namespace.ySize = float(size[1])
	except:
		argParser.error(f"invalid formatting for --size: {namespace.size}")

	namespace.auto = (namespace.use_g == False and
		namespace.feed_visible_below is None and
		namespace.speed_visible_below is None)

def main():
	class Args: pass
	parseArgs(Args)

	def log(*args, **kwargs):
		if Args.log is not None:
			print(*args, **kwargs, file=Args.log)

	data = Args.input.read()

	if Args.auto:
		Args.use_g, Args.feed_visible_below, Args.speed_visible_below = \
			detectParsingMode(data, log=log)

	parsedGcode = parseGcode(data, log=log,
		useG=Args.use_g,
		feedVisibleBelow=Args.feed_visible_below,
		speedVisibleBelow=Args.speed_visible_below)

	parsedGcode = translateToFirstQuarter(parsedGcode, log=log)
	parsedGcode = addEnd(parsedGcode, Args.end_home, log=log)
	parsedGcode = resize(parsedGcode, Args.xSize, Args.ySize, Args.dilation, log=log)

	if Args.output is not None:
		Args.output.write(toGcode(parsedGcode))
	if Args.binary_output is not None:
		Args.binary_output.write(toBinaryData(parsedGcode))

if __name__ == '__main__':
	main()