#!/usr/bin/python3
#pylint: disable=no-member

import argparse
from enum import Enum
import text_to_gcode.text_to_gcode as text_to_gcode
import gcode_parser
import sender


def textToGcode(text):
	letters = text_to_gcode.readLetters(Args.gcode_directory)
	return text_to_gcode.textToGcode(letters, text, Args.line_length, Args.line_spacing, Args.padding)

def parseGcode(gcodeData):
	if Args.auto:
		Args.use_g, Args.feed_visible_below, Args.speed_visible_below = \
			gcode_parser.detectParsingMode(gcodeData, log=log)

	parsedGcode = gcode_parser.parseGcode(gcodeData, log=log,
		useG=Args.use_g,
		feedVisibleBelow=Args.feed_visible_below,
		speedVisibleBelow=Args.speed_visible_below)

	parsedGcode = gcode_parser.translateToFirstQuarter(parsedGcode, log=log)
	parsedGcode = gcode_parser.addEnd(parsedGcode, Args.end_home, log=log)
	parsedGcode = gcode_parser.resize(parsedGcode, Args.xSize, Args.ySize, Args.dilation, log=log)

	return parsedGcode


def parseArgs(namespace):
	argParser = argparse.ArgumentParser(fromfile_prefix_chars="@",
		description="Print something with the connected plotter")
	subparsers = argParser.add_subparsers(dest="subcommand",
		description="Format subcommands")

	ioGroup = argParser.add_argument_group("Output options")
	ioGroup.add_argument("-o", "--output", type=argparse.FileType('w'), required=False, metavar="FILE",
		help="File in which to save the generated gcode (will be ignored if using binary subcommand)")
	ioGroup.add_argument("-b", "--binary-output", type=argparse.FileType('wb'), required=False, metavar="FILE",
		help="File in which to save the binary data ready to be fed to the plotter")
	ioGroup.add_argument("-l", "--log", type=argparse.FileType('w'), required=False, metavar="FILE",
		help="File in which to save logs, comments and warnings")

	genGroup = argParser.add_argument_group("Gcode generation options")
	genGroup.add_argument("--end-home", action="store_true",
		help="Add a trailing instruction to move to (0,0) instead of just taking the pen up")
	genGroup.add_argument("-s", "--size", type=str, default="1.0x1.0", metavar="XxY",
		help="The size of the print area in millimeters (e.g. 192.7x210.3)")
	genGroup.add_argument("-d", "--dilation", type=float, default=1.0, metavar="FACTOR",
		help="Dilation factor to apply (useful to convert mm to steps)")

	connGroup = argParser.add_argument_group("Plotter connectivity options")
	connGroup.add_argument("--simulate", action="store_true",
		help="Simulate sending data to the plotter without really opening a connection. Useful with logging enabled to debug the commands sent.")
	connGroup.add_argument("--port", "--serial-port", type=str, metavar="PORT", dest="serial_port",
		help="The serial port the plotter is connected to (required unless there is --simulate)")
	connGroup.add_argument("--baud", "--baud-rate", type=int, metavar="RATE", dest="baud_rate",
		help="The baud rate to use for the connection with the plotter. It has to be equal to the plotter baud rate. (required unless there is --simulate)")


	binParser = subparsers.add_parser("binary", help="Send binary files directly to the plotter")
	bpDataGroup = binParser.add_argument_group("Data options")
	bpDataGroup.add_argument("-i", "--input", type=argparse.FileType('rb'), required=True, metavar="FILE",
		help="Binary file from which to read the raw data to send to the plotter")


	gcodeParser = subparsers.add_parser("gcode", help="Print gcode with the plotter")
	gpDataGroup = gcodeParser.add_argument_group("Data options")
	gpDataGroup.add_argument("-i", "--input", type=argparse.FileType('r'), default="-", metavar="FILE",
		help="File from which to read the gcode to print")

	gpParseGroup = gcodeParser.add_argument_group("Gcode parsing options (detected automatically if not provided)")
	gpParseGroup.add_argument("--use-g", action="store_true",
		help="Consider `G0` as pen up and `G1` as pen down")
	gpParseGroup.add_argument("--feed-visible-below", type=float, metavar="VALUE",
		help="Consider `F` (feed) commands with a value above the provided as pen down, otherwise as pen up")
	gpParseGroup.add_argument("--speed-visible-below", type=float, metavar="VALUE",
		help="Consider `S` (speed) commands with a value above the provided as pen down, otherwise as pen up")


	textParser = subparsers.add_parser("text", help="Print text with the plotter")
	tpDataGroup = textParser.add_argument_group("Data options")
	tpDataGroup.add_argument("-i", "--input", type=argparse.FileType('r'), default="-", metavar="FILE",
		help="File from which to read the characters to print")
	tpDataGroup.add_argument("--gcode-directory", type=str, default="./text_to_gcode/ascii_gcode/", metavar="DIR",
		help="Directory containing the gcode information for all used characters")

	tpTextGroup = textParser.add_argument_group("Text options")
	tpTextGroup.add_argument("--line-length", type=float, required=True,
		help="Maximum length of a line")
	tpTextGroup.add_argument("--line-spacing", type=float, default=8.0,
		help="Distance between two subsequent lines")
	tpTextGroup.add_argument("--padding", type=float, default=1.5,
		help="Empty space between characters")

	argParser.parse_args(namespace=namespace)


	try:
		size = namespace.size.split("x")
		namespace.xSize = float(size[0])
		namespace.ySize = float(size[1])
	except:
		argParser.error(f"invalid formatting for --size: {namespace.size}")

	if not namespace.simulate:
		if namespace.serial_port is None:
			argParser.error(f"--serial-port is required unless there is --simulate")
		if namespace.baud_rate is None:
			argParser.error(f"--baud-rate is required unless there is --simulate")

	# check that a subcommand was selected (required=True is buggy)
	if namespace.subcommand is None:
		argParser.error(f"exactly one subcommand from the following is required: binary, gcode, text")

	if Args.subcommand == "gcode":
		namespace.auto = (namespace.use_g == False and
			namespace.feed_visible_below is None and
			namespace.speed_visible_below is None)

class Args:
	pass

def log(*args, **kwargs):
	if Args.log is not None:
		kwargs["flush"] = True
		print(*args, **kwargs, file=Args.log)

def main():
	parseArgs(Args)

	binaryData = b""
	if Args.subcommand == "binary":
		binaryData = Args.input.read()
	else:
		gcodeData = ""
		if Args.subcommand == "gcode":
			gcodeData = Args.input.read()
		elif Args.subcommand == "text":
			gcodeData = textToGcode(Args.input.read())

			# settings for gcode parser
			Args.auto = False
			Args.use_g = True
			Args.feed_visible_below = None
			Args.speed_visible_below = None
		else:
			raise AssertionError()

		parsedGcode = parseGcode(gcodeData)
		binaryData = gcode_parser.toBinaryData(parsedGcode)
		if Args.output is not None:
			Args.output.write(gcode_parser.toGcode(parsedGcode))

	if Args.binary_output is not None:
		Args.binary_output.write(binaryData)


	sender.sendData(binaryData, Args.serial_port, Args.baud_rate, Args.simulate, log=log)


if __name__ == "__main__":
	main()
